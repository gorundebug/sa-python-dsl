#!/usr/bin/env python3
"""Fresh generated Go canonical services; bounded official peers, one service CPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROFILES = {
    'pulsar': ('pulsar-events', 'pulsarevents', 'servicelib-pulsar-acceptance', 'pulsar://127.0.0.1:16650', 'http://127.0.0.1:18080'),
    'redis-streams': ('redis-streams-events', 'redisstreamsevents', 'servicelib-redis-streams-acceptance', 'redis://127.0.0.1:6379', ''),
    'rabbitmq': ('rabbitmq-events', 'rabbitmqevents', 'servicelib-rabbitmq-amqp-acceptance', 'amqp://127.0.0.1:5672', 'http://127.0.0.1:15692'),
}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--count', type=int, default=10000)
    p.add_argument('--warmup', type=int, default=1000)
    p.add_argument('--inflight', type=int, default=16)
    p.add_argument('--phase-timeout', type=int, default=120)
    p.add_argument('--brokers', nargs='+', choices=list(PROFILES), default=list(PROFILES))
    p.add_argument('--go', default=os.getenv('GO', 'go'))
    p.add_argument('--platform', choices=['linux/arm64', 'linux/amd64'], default='linux/arm64')
    a = p.parse_args()
    assert 1 <= a.count <= 1000000 and 1 <= a.warmup <= 100000
    assert 1 <= a.inflight <= 32 and 1 <= a.phase_timeout <= 300
    root = a.artifacts.resolve(); root.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'shared_brokers': True, 'capacity_claim': False, 'profiles': []}
    def save(): (root/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    def command(args, *, cwd=ROOT, env=None, timeout=300, log=None):
        r = subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True,timeout=timeout)
        if log: Path(log).write_bytes(r.stdout+b'\n--- stderr ---\n'+r.stderr)
        if r.returncode: raise RuntimeError(f'{args[:3]} failed {r.returncode}: {r.stderr.decode(errors="replace")[-1500:]}')
        return r.stdout
    def docker(*args,**kwargs): return command(['docker',*args],**kwargs)
    try:
        report['go_version']=command([a.go,'version']).decode().strip()
        host=json.loads(docker('info','--format','{{json .}}'))
        report['docker_host']={k:host.get(k) for k in ('Architecture','NCPU','MemTotal','ServerVersion','KernelVersion','OperatingSystem')}
        report['parameters']={'count':a.count,'warmup':a.warmup,'inflight':a.inflight,'phase_timeout_seconds':a.phase_timeout}
        report['peer_sha256']=hashlib.sha256((HERE/'peer.go').read_bytes()).hexdigest()
        for mode in a.brokers:
            example_name, project_name, broker, url, admin = PROFILES[mode]
            example = HERE.parent/example_name
            dest = root/mode;dest.mkdir()
            identity='sa-perf-'+uuid.uuid4().hex[:12];service=identity+'-service';peer=identity+'-peer';image=identity+':local'
            port=20000+int(identity[-4:],16)%20000
            data={'mode':mode,'identity':identity,'status':'running','platform':a.platform,'shared_broker':broker,'runs':[]}
            report['profiles'].append(data);save()
            started=False;prepared=False
            peer_env=['-e','MODE='+mode,'-e','RUN_ID='+identity,'-e','METRICS_PORT='+str(port),'-e','ADMIN_URL='+admin]
            if mode!='pulsar':peer_env+=['-e','BROKER_PASSWORD=adapter-test']
            def peer_run(action,*args,total=0,log=None):
                return docker('run','--rm','--name',peer,'--platform',a.platform,'--network','container:'+broker,'--cpus','2','--memory','256m',*peer_env,'-e','EXPECTED_TOTAL='+str(total),'--entrypoint','/app/peer',image,action,*args,timeout=a.phase_timeout+30,log=log)
            try:
                env={**os.environ,'PYTHONPATH':str(ROOT/'sa-python-dsl/src')}
                model=command([ROOT/'sa-python-dsl/.venv/bin/python','-c',"import runpy,sys;p=runpy.run_path(sys.argv[1])['project'];assert not p.validate(),p.validate();sys.stdout.write(p.to_yaml())",example/'project.py'],env=env,log=dest/'export.log')
                (dest/'model.yaml').write_bytes(model)
                command([a.go,'run','./scripts/nats-performance-generate',dest/'model.yaml',dest/'generated.zip'],cwd=ROOT/'servicegen',log=dest/'generate.log')
                generated=dest/'generated';generated.mkdir()
                with zipfile.ZipFile(dest/'generated.zip') as archive:
                    for entry in archive.infolist():
                        target=generated/entry.filename;assert target.resolve().is_relative_to(generated)
                        if entry.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(entry));target.chmod((entry.external_attr>>16)&0o777 or 0o644)
                project=generated/project_name;app=project/'eventprocessor'
                for source in (example/'go').rglob('*'):
                    if source.is_file():
                        target=app/source.relative_to(example/'go');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
                (project/'go.work').write_text('go 1.26.4\nuse (\n ./eventprocessor\n '+json.dumps(str(ROOT/'servicelib'))+'\n)\n')
                buildenv={**os.environ,'GOWORK':str(project/'go.work'),'GOOS':'linux','GOARCH':a.platform.split('/')[1],'CGO_ENABLED':'0'}
                context=dest/'image';context.mkdir();shutil.copytree(app/'config',context/'config')
                command([a.go,'build','-p','2','-o',context/'service','./cmd/service'],cwd=app,env=buildenv,log=dest/'service-build.log')
                command([a.go,'build','-p','2','-o',context/'peer',HERE/'peer.go'],cwd=ROOT/'servicelib',env=buildenv,log=dest/'peer-build.log')
                command([a.go,'version','-m',context/'service'],log=dest/'service-build-info.log')
                command([a.go,'version','-m',context/'peer'],log=dest/'peer-build-info.log')
                (context/'Dockerfile').write_text('FROM scratch\nWORKDIR /app\nCOPY service peer /app/\nCOPY config /app/config/\nENTRYPOINT ["/app/service"]\n')
                docker('build','--platform',a.platform,'-t',image,context,log=dest/'image-build.log')
                data['service_sha256']=hashlib.sha256((context/'service').read_bytes()).hexdigest();data['model_sha256']=hashlib.sha256(model).hexdigest()
                data['image_id']=docker('image','inspect',image,'--format','{{.Id}}').decode().strip()
                broker_info=json.loads(docker('inspect',broker))[0];data['broker_image_id']=broker_info['Image'];data['broker_limits']={k:broker_info['HostConfig'][k] for k in ('NanoCpus','Memory')}
                prepared=True;peer_run('prepare',log=dest/'prepare.log')
                service_env={'GOMAXPROCS':'1','EVENTS_SERVERS':url,'EVENT_PROCESSOR_HTTP_PORT':str(port),'EVENT_PROCESSOR_GRPC_PORT':str(port+1),'SERVICELIB_NOOP_LOGS':'1','SERVICELIB_NOOP_TRACING':'1'}
                if mode=='pulsar':service_env.update(EVENTS_ADMIN_URL=admin,RECEIVE_EVENT_TOPIC=f'persistent://public/{identity}/incoming',PUBLISH_EVENT_TOPIC=f'persistent://public/{identity}/processed')
                elif mode=='redis-streams':service_env.update(EVENTS_PASSWORD='adapter-test',RECEIVE_EVENT_STREAM_KEY=identity+'.incoming',PUBLISH_EVENT_STREAM_KEY=identity+'.processed')
                else:service_env.update(EVENTS_USERNAME='adapter',EVENTS_PASSWORD='adapter-test',RECEIVE_EVENT_QUEUE_NAME=identity+'.incoming',PUBLISH_EVENT_QUEUE_NAME=identity+'.processed',PUBLISH_EVENT_EXCHANGE_NAME=identity+'.events')
                envargs=[item for k,v in service_env.items() for item in ('-e',k+'='+v)]
                docker('run','-d','--name',service,'--platform',a.platform,'--network','container:'+broker,'--cpus','1','--memory','512m',*envargs,image);started=True
                inspection=json.loads(docker('inspect',service))[0];data['service_limits']={k:inspection['HostConfig'][k] for k in ('NanoCpus','CpuQuota','CpuPeriod','Memory','NetworkMode')};assert data['service_limits']['NanoCpus']==1000000000
                for _ in range(60):
                    m=json.loads(docker('exec','-e','METRICS_PORT='+str(port),service,'/app/peer','metrics'))
                    if m:break
                    time.sleep(.25)
                else:raise RuntimeError('generated service metrics startup timeout')
                cumulative=0
                for phase,count in [('warmup',a.warmup),('measure',a.count)]:
                    cumulative+=count
                    before=json.loads(docker('exec',service,'/app/peer','resources'));begin=time.monotonic()
                    sample=json.loads(peer_run(phase,str(count),str(a.inflight),str(a.phase_timeout),total=cumulative,log=dest/(phase+'.log')))
                    after=json.loads(docker('exec',service,'/app/peer','resources'));sample.update(cgroup_before=before,cgroup_after=after,resource_window_seconds=time.monotonic()-begin)
                    assert after['cpu.max'].strip()=='100000 100000',after
                    def usage(s):return int(dict(line.split() for line in s['cpu.stat'].splitlines())['usage_usec'])
                    sample['cgroup_cpu_seconds']=(usage(after)-usage(before))/1e6
                    sample['cgroup_average_cpu_percent']=100*sample['cgroup_cpu_seconds']/sample['resource_window_seconds']
                    for metric,label in [('go_memstats_mallocs_total','allocations_per_message'),('go_memstats_alloc_bytes_total','allocated_bytes_per_message')]:
                        v=sample['metric_deltas'][metric];sample[label]=None if v is None else v/count
                    cpu=sample['metric_deltas']['process_cpu_seconds_total'];sample['process_cpu_percent']=None if cpu is None else 100*cpu/sample['settled_seconds']
                    sample['docker_stats']=json.loads(docker('stats','--no-stream','--format','{{json .}}',service))
                    data['runs'].append(sample);save()
                docker('stop','--time','10',service,timeout=20);state=json.loads(docker('inspect',service))[0]['State'];data['service_exit']=state;assert state['ExitCode']==0 and not state['OOMKilled'],state
                data['status']='passed';save()
            finally:
                original_failure=sys.exc_info()[0]
                if started:
                    logs=subprocess.run(['docker','logs',service],capture_output=True,timeout=10);(dest/'service.log').write_bytes(logs.stdout+logs.stderr)
                    subprocess.run(['docker','rm','-f',service],capture_output=True,timeout=20)
                subprocess.run(['docker','rm','-f',peer],capture_output=True,timeout=20)
                if prepared:
                    try:peer_run('cleanup',log=dest/'cleanup.log')
                    except Exception as cleanup_error:
                        data['cleanup_error']=str(cleanup_error)
                        if original_failure is None:raise
            save()
        report['status']='passed';save()
    except BaseException as e:report['status']='failed';report['error']=str(e);save();raise
    print(root/'results.json')

if __name__=='__main__':main()
