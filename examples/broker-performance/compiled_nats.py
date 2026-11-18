#!/usr/bin/env python3
"""Bounded native-runtime broker load through actual generated services."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
import time
from run import PROFILES

ROOT = Path(__file__).resolve().parents[3]
IMAGES = {'rust': 'rustservicelib-toolchain:local', 'userver': 'cppservicelib-build:latest', 'coro': 'cppcoroservicelib-build:latest'}
VOLUMES = {'userver': 'cppservicelib_cppservicelib-conan2', 'coro': 'dependency-conan2'}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--runtime',choices=IMAGES,required=True)
 p.add_argument('--broker',choices=['nats','pulsar','redis-streams'],default='nats')
 p.add_argument('--native-prefix',type=Path,help='Official Pulsar or hiredis installation used by the built project')
 p.add_argument('--project',type=Path,required=True)
 p.add_argument('--artifacts',type=Path,required=True)
 p.add_argument('--go',default='go')
 p.add_argument('--count',type=int,default=5000)
 p.add_argument('--warmup',type=int,default=500)
 p.add_argument('--inflight',type=int,default=8)
 p.add_argument('--timeout',type=int,default=180)
 a=p.parse_args()
 assert 1<=a.count<=1000000 and 1<=a.warmup<=100000 and 1<=a.inflight<=32 and 1<=a.timeout<=300
 if a.broker!='nats' and (a.runtime=='rust' or (a.broker=='redis-streams' and a.runtime!='coro') or not a.native_prefix):p.error('unsupported runtime/broker or missing --native-prefix')
 root=a.artifacts.resolve();root.mkdir(parents=True,exist_ok=False)
 project=a.project.resolve();binary=project/('event_processor' if a.runtime=='rust' else 'build/eventprocessor/'+{'nats':'nats_events','pulsar':'pulsar_events','redis-streams':'redis_streams_events'}[a.broker]+'_event_processor')
 report={'runtime':a.runtime,'status':'running','parameters':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'shared_broker':True,'capacity_claim':False,'phases':[]}
 def save():(root/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 def run(command,timeout=300,log=None,env=None,cwd=None):
  r=subprocess.run(list(map(str,command)),capture_output=True,timeout=timeout,env=env,cwd=cwd)
  if log:(root/log).write_bytes(r.stdout+b'\n'+r.stderr)
  if r.returncode:raise RuntimeError(f'{command[:3]} exit {r.returncode}: {r.stderr.decode(errors="replace")[-1500:]}')
  return r.stdout
 def docker(*args,**kw):return run(['docker',*args],**kw)
 identity='sa-native-load-'+uuid.uuid4().hex[:12];service=identity+'-service';peer=identity+'-peer';broker='cppservicelib-nats-acceptance' if a.broker=='nats' else PROFILES[a.broker][2];started=False;prepared=False
 streams=[identity.replace('-','_').upper()+'_'+suffix for suffix in ['IN','OUT']]
 env={'NATS_URL':'nats://127.0.0.1:4222','WIRE_UPPER':'1','SUBJECT_PREFIX':identity,'INPUT_STREAM':streams[0],'OUTPUT_STREAM':streams[1],'METRICS_PORT':'8080'}
 if a.broker!='nats':env.update(MODE=a.broker,RUN_ID=identity,ADMIN_URL=PROFILES[a.broker][4],BROKER_PASSWORD='adapter-test')
 def invoke(*args,log=None,total=0):
  peerargs=[x for key,value in (env|{'EXPECTED_TOTAL':str(total)}).items() for x in ['-e',key+'='+value]]
  return docker('run','--rm','--name',peer,'--network','container:'+broker,'--cpus','1','-v',str(root)+':/perf:ro',*peerargs,'--entrypoint','/perf/peer',report['image_id'],*args,timeout=a.timeout+20,log=log)
 save()
 try:
  run([a.go,'build','-p','2','-o',root/'peer',ROOT/('sa-python-dsl/examples/nats-events/performance/peer.go' if a.broker=='nats' else 'sa-python-dsl/examples/broker-performance/peer.go')],cwd=ROOT/'servicelib',env=os.environ|{'GOOS':'linux','GOARCH':'arm64','CGO_ENABLED':'0'},log='peer-build.log')
  run([a.go,'version','-m',root/'peer'],log='peer-identity.log')
  report['image_id']=docker('image','inspect',IMAGES[a.runtime],'--format','{{.Id}}').decode().strip()
  report['broker_image_id']=json.loads(docker('inspect',broker))[0]['Image']
  if a.broker!='nats':
   prepared=True;invoke('prepare',log='prepare.log')
  variables={'CORE_EVENTS_SERVERS':env['NATS_URL'],'DURABLE_EVENTS_SERVERS':env['NATS_URL'],'RECEIVE_CORE_EVENT_SUBJECT':identity+'.core.incoming','PUBLISH_CORE_EVENT_SUBJECT':identity+'.core.processed','RECEIVE_DURABLE_EVENT_SUBJECT':identity+'.durable.incoming','PUBLISH_DURABLE_EVENT_SUBJECT':identity+'.durable.processed','RECEIVE_DURABLE_EVENT_STREAM_NAME':streams[0],'PUBLISH_DURABLE_EVENT_STREAM_NAME':streams[1],'RECEIVE_DURABLE_EVENT_DURABLE_NAME':'event_processor','SERVICELIB_NOOP_LOGS':'1','SERVICELIB_NOOP_TRACING':'1'}
  if a.broker!='nats':
   variables={'EVENTS_SERVERS':PROFILES[a.broker][3],'SERVICELIB_NOOP_LOGS':'1','SERVICELIB_NOOP_TRACING':'1'}
   if a.broker=='pulsar':variables.update(EVENTS_ADMIN_URL=PROFILES[a.broker][4],RECEIVE_EVENT_TOPIC=f'persistent://public/{identity}/incoming',PUBLISH_EVENT_TOPIC=f'persistent://public/{identity}/processed')
   else:variables.update(EVENTS_PASSWORD='adapter-test',RECEIVE_EVENT_STREAM_KEY=identity+'.incoming',PUBLISH_EVENT_STREAM_KEY=identity+'.processed')
  if a.runtime=='rust':
   for key in ('CORE_EVENTS_SERVERS','DURABLE_EVENTS_SERVERS'):variables[key]=json.dumps([variables[key]])
  args=['run','-d','--name',service,'--network','container:'+broker,'--cpus','1','--memory','512m','-v',str(project)+':/generated:ro','-v',str(root)+':/perf:ro','-w','/generated' if a.runtime=='rust' else '/generated/eventprocessor']
  if a.runtime in VOLUMES:args+=['-v',VOLUMES[a.runtime]+':/conan:ro']
  if a.native_prefix:args+=['-v',str(a.native_prefix.resolve())+(':/pulsar:ro' if a.broker=='pulsar' else ':/hiredis:ro')]
  args += [x for key,value in variables.items() for x in ['-e',key+'='+value]]
  args+=['--entrypoint','/generated/'+str(binary.relative_to(project)),report['image_id']]
  if a.runtime=='userver':args+=['--config','static_config.yaml','--config_vars','config/config_vars.yaml']
  docker(*args);started=True;prepared=True
  limits=json.loads(docker('inspect',service))[0]['HostConfig'];assert limits['NanoCpus']==1000000000
  report['limits']={k:limits[k] for k in ('NanoCpus','Memory','NetworkMode')}
  if a.broker!='nats':
   for _ in range(80):
    if json.loads(docker('exec','-e','METRICS_PORT=8080',service,'/perf/peer','ready')):break
    time.sleep(.25)
   else:raise RuntimeError('metrics endpoint did not become ready')
  cumulative=0
  for profile in (('core','jetstream') if a.broker=='nats' else (a.broker,)):
   for phase,count in [('warmup',a.warmup),('measure',a.count)]:
    before=json.loads(docker('exec',service,'/perf/peer','resources'))
    cumulative+=count
    peer_command=[profile,str(count),str(a.inflight),str(a.timeout),identity+'-'+phase] if a.broker=='nats' else [phase,str(count),str(a.inflight),str(a.timeout)]
    sample=json.loads(invoke(*peer_command,total=cumulative,log=profile+'-'+phase+'.log'))
    after=json.loads(docker('exec',service,'/perf/peer','resources'))
    assert after['cpu.max'].strip()=='100000 100000'
    def cpu(v):return int(dict(line.split() for line in v['cpu.stat'].splitlines())['usage_usec'])
    sample.update(phase=phase,cgroup_before=before,cgroup_after=after,cpu_seconds=(cpu(after)-cpu(before))/1e6,allocation_count=None,allocation_note='No comparable allocation counter; not estimated.')
    report['phases'].append(sample);save()
  docker('stop','--time','15',service,timeout=25)
  state=json.loads(docker('inspect',service))[0]['State'];report['service_exit']=state
  assert state['ExitCode']==0 and not state['OOMKilled'],state
  report['status']='passed'
 except BaseException as error:
  report['status']='failed';report['error']=str(error);raise
 finally:
  if started:
   try:docker('logs',service,log='service.log')
   finally:docker('rm','-f',service)
  # A timed-out docker CLI may leave its owned container running.
  inspected=subprocess.run(['docker','inspect',peer],capture_output=True,timeout=10)
  if inspected.returncode==0:docker('rm','-f',peer)
  if prepared and 'image_id' in report:
   try:invoke('cleanup',log='cleanup.log')
   except Exception as error:report['status']='failed';report['cleanup_error']=str(error);save();raise
  save()
 print(root/'results.json')

if __name__=='__main__':main()
