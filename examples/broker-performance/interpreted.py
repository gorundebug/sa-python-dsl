#!/usr/bin/env python3
"""Generated Python/TypeScript one-CPU profiles using the existing official Go peers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
from run import ROOT, HERE, PROFILES

SOURCES = {
 'nats': '/private/tmp/sa-nats-interop-20261118/{language}/natsevents/eventprocessor',
 'pulsar': '/private/tmp/sa-rabbit-pulsar-interop-20261118/pulsar-{language}/pulsarevents/eventprocessor',
 'redis-streams': '/private/tmp/sa-redis-interop-20261118/{language}/redisstreamsevents/eventprocessor',
}
BASE = {'python':'sa-rabbit-python-canonical:local','typescript':'sa-rabbit-typescript-canonical:local'}

def manifest(path):
 return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--artifacts',type=Path,required=True)
 p.add_argument('--go',default=os.getenv('GO','go'))
 p.add_argument('--rebuild-typescript-sdk',action='store_true',help='Rebuild SDK JS and replace source/dist in the pinned dependency image; application unchanged')
 p.add_argument('--languages',nargs='+',choices=list(BASE),default=list(BASE))
 p.add_argument('--brokers',nargs='+',choices=['nats',*PROFILES],default=['nats',*PROFILES])
 p.add_argument('--count',type=int,default=5000);p.add_argument('--warmup',type=int,default=500)
 p.add_argument('--fast-count',type=int,help='Optional Core/Redis measured count; other profiles retain --count')
 p.add_argument('--inflight',type=int,default=8);p.add_argument('--timeout',type=int,default=120)
 a=p.parse_args();assert a.fast_count is None or 1<=a.fast_count<=1000000
 assert 1<=a.count<=1000000 and 1<=a.warmup<=100000 and 1<=a.inflight<=32 and 1<=a.timeout<=300
 root=a.artifacts.resolve();root.mkdir(parents=True,exist_ok=False)
 report={'status':'running','shared_brokers':True,'capacity_claim':False,'runs':[],'parameters':{'count':a.count,'warmup':a.warmup,'inflight':a.inflight,'timeout':a.timeout,'fast_count':a.fast_count}}
 def save():(root/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 def command(args,*,cwd=ROOT,env=None,timeout=300,log=None):
  r=subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True,timeout=timeout)
  if log:Path(log).write_bytes(r.stdout+b'\n--- stderr ---\n'+r.stderr)
  if r.returncode:raise RuntimeError(f'{args[:3]} failed {r.returncode}: {r.stderr.decode(errors="replace")[-1600:]}')
  return r.stdout
 def docker(*args,**kwargs):return command(['docker',*args],**kwargs)
 try:
  peers=root/'peers';peers.mkdir()
  buildenv={**os.environ,'GOOS':'linux','GOARCH':'arm64','CGO_ENABLED':'0'}
  for name,source in [('broker',HERE/'peer.go'),('nats',HERE.parent/'nats-events/performance/peer.go')]:
   command([a.go,'build','-p','2','-o',peers/name,source],cwd=ROOT/'servicelib',env=buildenv,log=root/(name+'-peer-build.log'))
   command([a.go,'version','-m',peers/name],log=root/(name+'-peer-identity.log'))
  (peers/'Dockerfile').write_text('FROM scratch\nCOPY broker nats /perf/\n')
  peerimage='sa-interpreted-peer-'+uuid.uuid4().hex[:10]+':local';docker('build','-t',peerimage,peers,log=root/'peer-image.log')
  report['peer_image_id']=docker('image','inspect',peerimage,'--format','{{.Id}}').decode().strip()
  host=json.loads(docker('info','--format','{{json .}}'));report['docker_host']={k:host.get(k) for k in ('Architecture','NCPU','MemTotal','ServerVersion','KernelVersion','OperatingSystem')}
  for language in a.languages:
   baseinfo=json.loads(docker('image','inspect',BASE[language]))[0]
   # Pin by immutable ID throughout; mutable local tags are only initial selectors.
   base=baseinfo['Id']
   if language=='typescript' and a.rebuild_typescript_sdk:
    sdkroot=ROOT/'tsservicelib'
    command(['node',sdkroot/'node_modules/typescript/bin/tsc','--build',sdkroot/'tsconfig.build.json'],log=root/'typescript-sdk-build.log')
    rebuild=root/'typescript-sdk-image';rebuild.mkdir()
    for folder in ('src','dist'):shutil.copytree(sdkroot/folder,rebuild/folder)
    pinned='sa-perf-sdk-parent:'+base.split(':')[1][:16];docker('tag',base,pinned)
    (rebuild/'Dockerfile').write_text(f'FROM {pinned}\nUSER root\nRUN rm -rf /app/.tsservicelib/src /app/.tsservicelib/dist\nCOPY src /app/.tsservicelib/src\nCOPY dist /app/.tsservicelib/dist\n')
    tag='sa-perf-sdk-rebuilt:'+uuid.uuid4().hex[:12]
    docker('build','-t',tag,rebuild,log=root/'typescript-sdk-image-build.log')
    report['typescript_sdk_parent_image']=base
    report['typescript_sdk_dist_manifest']=manifest(sdkroot/'dist')
    base=docker('image','inspect',tag,'--format','{{.Id}}').decode().strip()
   report.setdefault('base_images',{})[language]=base
   basetag='sa-perf-base-'+language+':'+base.split(':')[1][:16];docker('tag',base,basetag)
   sdk=ROOT/('pyservicelib' if language=='python' else 'tsservicelib')
   (root/(language+'-sdk-source-manifest.json')).write_text(json.dumps(manifest(sdk/'src'),indent=2)+'\n')
   # Verify the SDK source in the selected dependency/runtime image really is current.
   if language=='python':
    code='import pathlib,json,pyservicelib_gorundebug as m; a=pathlib.Path("/current/pyservicelib_gorundebug");b=pathlib.Path(next(iter(m.__path__)));d=[str(x.relative_to(a)) for x in a.rglob("*.py") if not (b/x.relative_to(a)).exists() or x.read_bytes()!=(b/x.relative_to(a)).read_bytes()];print(json.dumps(d));assert not d'
    docker('run','--rm','-v',str(sdk/'src')+':/current:ro','--entrypoint','python',base,'-c',code,log=root/(language+'-sdk-verified.log'))
   else:
    code='const fs=require("fs"),p=require("path");let d=[];function w(a,r=""){for(let x of fs.readdirSync(a,{withFileTypes:true})){let n=p.join(r,x.name);if(x.isDirectory())w(p.join(a,x.name),n);else {let b=p.join("/app/.tsservicelib/src",n);if(!fs.existsSync(b)||!fs.readFileSync(p.join(a,x.name)).equals(fs.readFileSync(b)))d.push(n)}}}w("/current");console.log(JSON.stringify(d));if(d.length)process.exit(1)'
    docker('run','--rm','-v',str(sdk/'src')+':/current:ro','--entrypoint','node',base,'-e',code,log=root/(language+'-sdk-verified.log'))
   if language=='python':
    content='import sys,pathlib,hashlib,json;print(json.dumps({"runtime":sys.version,"files":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for d in ["/workspace/src","/workspace/config"] for p in pathlib.Path(d).rglob("*") if p.is_file() and "__pycache__" not in p.parts}},sort_keys=True))'
    docker('run','--rm','--entrypoint','python',base,'-c',content,log=root/(language+'-base-application-identity.log'))
   else:
    content='const fs=require("fs"),p=require("path"),c=require("crypto");let files={};function walk(d){for(let x of fs.readdirSync(d,{withFileTypes:true})){let n=p.join(d,x.name);if(x.isDirectory())walk(n);else files[n]=c.createHash("sha256").update(fs.readFileSync(n)).digest("hex")}}walk("/app/dist");walk("/app/config");console.log(JSON.stringify({runtime:process.version,files}))'
    docker('run','--rm','--entrypoint','node',base,'-e',content,log=root/(language+'-base-application-identity.log'))
    command(['node',ROOT/'tsservicelib/node_modules/typescript/bin/tsc','--version'],log=root/'typescript-compiler-version.log')
   for mode in a.brokers:
    dest=root/(language+'-'+mode);dest.mkdir();identity='sa-perf-'+uuid.uuid4().hex[:12];service=identity+'-service';peer=identity+'-peer';port=20000+int(identity[-4:],16)%20000
    data={'language':language,'broker':mode,'identity':identity,'status':'running','phases':[]};report['runs'].append(data);save()
    image=base;started=False;prepared=False
    if mode!='rabbitmq':
     source=Path(SOURCES[mode].format(language=language));app=dest/'app';app.mkdir()
     # Source/config only: no existing node_modules, distributions or SDK stubs.
     for name in ('src','config','package.json','tsconfig.json','pyproject.toml'):
      x=source/name
      if x.is_dir():shutil.copytree(x,app/name)
      elif x.is_file():shutil.copy2(x,app/name)
     data['generated_source_root']=str(source);data['generated_source_manifest']=manifest(app)
     overlay=HERE.parent/('nats-events' if mode=='nats' else PROFILES[mode][0])/language/'src'
     shutil.copytree(overlay,app/'src',dirs_exist_ok=True)
     data['implemented_source_manifest']=manifest(app)
     if language=='typescript':
      modules=app/'node_modules';modules.mkdir();hostmodules=ROOT/'tsservicelib/node_modules'
      for x in hostmodules.iterdir():
       if x.name!='@gorundebug':(modules/x.name).symlink_to(x,target_is_directory=x.is_dir())
      (modules/'@gorundebug').mkdir();(modules/'@gorundebug/tsservicelib').symlink_to(ROOT/'tsservicelib',target_is_directory=True)
      command(['node',hostmodules/'typescript/bin/tsc','--build','--pretty','false'],cwd=app,log=dest/'compile.log')
      data['compiled_manifest']=manifest(app/'dist')
      text=f'FROM {basetag}\nUSER root\nRUN rm -rf /app/dist /app/config\nCOPY app/dist /app/dist\nCOPY app/config /app/config\nCOPY app/package.json /app/package.json\nWORKDIR /app\nENTRYPOINT ["node","--enable-source-maps","dist/main.generated.js"]\n'
     else:
      text=f'FROM {basetag}\nUSER root\nRUN rm -rf /workspace/src /workspace/config\nCOPY app/src /workspace/src\nCOPY app/config /workspace/config\nENV PYTHONPATH=/workspace/src\nWORKDIR /workspace\nENTRYPOINT ["python","-m","event_processor.main"]\nCMD ["--config","config/config.yaml","--values","config/overrides.yaml","--overrides","config/docker_overrides.yaml"]\n'
     (dest/'Dockerfile').write_text(text);(dest/'.dockerignore').write_text('app/node_modules\napp/src/**/__pycache__\n')
     image=identity+':local';docker('build','-t',image,dest,log=dest/'image-build.log')
    data['image_id']=docker('image','inspect',image,'--format','{{.Id}}').decode().strip()
    if mode=='nats':broker='cppservicelib-nats-acceptance';url='nats://127.0.0.1:4222';admin='';binary='nats'
    else:_,_,broker,url,admin=PROFILES[mode];binary='broker'
    data['shared_broker']=broker;data['broker_image_id']=json.loads(docker('inspect',broker))[0]['Image']
    streams=[identity.replace('-','_').upper()+'_'+s for s in ('IN','OUT')]
    penv={'MODE':mode,'RUN_ID':identity,'METRICS_PORT':str(port),'ADMIN_URL':admin,'BROKER_PASSWORD':'adapter-test','WIRE_UPPER':'1','SUBJECT_PREFIX':identity,'INPUT_STREAM':streams[0],'OUTPUT_STREAM':streams[1]}
    pargs=[v for k,val in penv.items() for v in ('-e',k+'='+val)]
    def peer_run(action,*args,total=0,log=None):return docker('run','--rm','--name',peer,'--network','container:'+broker,'--cpus','2','--memory','256m',*pargs,'-e','EXPECTED_TOTAL='+str(total),'--entrypoint','/perf/'+binary,peerimage,action,*args,timeout=a.timeout+30,log=log)
    try:
     if mode!='nats':prepared=True;peer_run('prepare',log=dest/'prepare.log')
     env={'EVENT_PROCESSOR_HTTP_PORT':str(port),'EVENT_PROCESSOR_GRPC_PORT':str(port+1),'SERVICELIB_NOOP_LOGS':'1','SERVICELIB_NOOP_TRACING':'1'}
     if mode=='nats':
      env.update(CORE_EVENTS_SERVERS=url,DURABLE_EVENTS_SERVERS=url,RECEIVE_CORE_EVENT_SUBJECT=identity+'.core.incoming',PUBLISH_CORE_EVENT_SUBJECT=identity+'.core.processed',RECEIVE_DURABLE_EVENT_SUBJECT=identity+'.durable.incoming',PUBLISH_DURABLE_EVENT_SUBJECT=identity+'.durable.processed',RECEIVE_DURABLE_EVENT_STREAM_NAME=streams[0],PUBLISH_DURABLE_EVENT_STREAM_NAME=streams[1])
     else:
      env['EVENTS_SERVERS']=url
      if mode=='pulsar':env.update(EVENTS_ADMIN_URL=admin,RECEIVE_EVENT_TOPIC=f'persistent://public/{identity}/incoming',PUBLISH_EVENT_TOPIC=f'persistent://public/{identity}/processed')
      elif mode=='redis-streams':env.update(EVENTS_PASSWORD='adapter-test',RECEIVE_EVENT_STREAM_KEY=identity+'.incoming',PUBLISH_EVENT_STREAM_KEY=identity+'.processed')
      else:env.update(EVENTS_USERNAME='adapter',EVENTS_PASSWORD='adapter-test',RECEIVE_EVENT_QUEUE_NAME=identity+'.incoming',PUBLISH_EVENT_QUEUE_NAME=identity+'.processed',PUBLISH_EVENT_EXCHANGE_NAME=identity+'.events')
     envargs=[v for k,val in env.items() for v in ('-e',k+'='+val)]
     docker('run','-d','--name',service,'--network','container:'+broker,'--cpus','1','--memory','512m','-v',str(peers)+':/perf:ro',*envargs,image);started=True
     inspection=json.loads(docker('inspect',service))[0];data['service_limits']={k:inspection['HostConfig'][k] for k in ('NanoCpus','CpuQuota','CpuPeriod','Memory','NetworkMode')};assert data['service_limits']['NanoCpus']==1000000000
     for _ in range(60):
      m=json.loads(docker('exec','-e','METRICS_PORT='+str(port),service,'/perf/'+binary,'metrics'))
      if m:break
      time.sleep(.25)
     else:raise RuntimeError('metrics startup timeout')
     if mode=='nats':prepared=True
     cumulative=0
     for profile in (['core','jetstream'] if mode=='nats' else [mode]):
      for phase,count in [('warmup',a.warmup),('measure',(a.fast_count if a.fast_count and profile in ('core','redis-streams') else a.count))]:
       cumulative+=count;before=json.loads(docker('exec',service,'/perf/'+binary,'resources'));begin=time.monotonic()
       if mode=='nats':raw=peer_run(profile,str(count),str(a.inflight),str(a.timeout),identity+'-'+phase,log=dest/(profile+'-'+phase+'.log'))
       else:raw=peer_run(phase,str(count),str(a.inflight),str(a.timeout),total=cumulative,log=dest/(phase+'.log'))
       sample=json.loads(raw);sample['phase']=phase;sample['profile']=profile
       after=json.loads(docker('exec',service,'/perf/'+binary,'resources'));sample.update(cgroup_before=before,cgroup_after=after,resource_window_seconds=time.monotonic()-begin)
       assert after['cpu.max'].strip()=='100000 100000'
       def usage(s):return int(dict(x.split() for x in s['cpu.stat'].splitlines())['usage_usec'])
       sample['cgroup_cpu_seconds']=(usage(after)-usage(before))/1e6;sample['cgroup_average_cpu_percent']=100*sample['cgroup_cpu_seconds']/sample['resource_window_seconds']
       cpu=sample['metric_deltas']['process_cpu_seconds_total'];sample['process_cpu_percent']=None if cpu is None else 100*cpu/sample['settled_seconds'];sample['allocations_per_message']=None;sample['allocation_note']='No comparable allocation-count counter exported by this runtime; not estimated.'
       sample['docker_stats']=json.loads(docker('stats','--no-stream','--format','{{json .}}',service));data['phases'].append(sample);save()
     docker('stop','--time','15',service,timeout=25);state=json.loads(docker('inspect',service))[0]['State'];data['service_exit']=state;assert state['ExitCode']==0 and not state['OOMKilled'],state;data['status']='passed'
    finally:
     if started:
      state=subprocess.run(['docker','inspect',service,'--format','{{json .State}}'],capture_output=True,text=True,timeout=10)
      if state.returncode==0:data['final_observed_state']=json.loads(state.stdout)
      resource=subprocess.run(['docker','exec',service,'/perf/'+binary,'resources'],capture_output=True,text=True,timeout=10)
      if resource.returncode==0:data['final_observed_resources']=json.loads(resource.stdout)
      logs=subprocess.run(['docker','logs',service],capture_output=True,timeout=10);(dest/'service.log').write_bytes(logs.stdout+logs.stderr);subprocess.run(['docker','rm','-f',service],capture_output=True,timeout=20)
     subprocess.run(['docker','rm','-f',peer],capture_output=True,timeout=20)
     if prepared:peer_run('cleanup',log=dest/'cleanup.log')
    save()
  report['status']='passed';save()
 except BaseException as e:
  report['status']='failed';report['error']=str(e)
  for item in report['runs']:
   if item['status']=='running':item['status']='failed'
  save();raise
 print(root/'results.json')

if __name__=='__main__':main()
