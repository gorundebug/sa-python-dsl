#!/usr/bin/env python3
"""Bounded, one-CPU performance acceptance of a freshly generated Go service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import zipfile

EXAMPLE = Path(__file__).resolve().parents[1]
ROOT = EXAMPLE.parents[2]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--count', type=int, default=5000)
    p.add_argument('--warmup', type=int, default=500)
    p.add_argument('--core-count', type=int, help='Override measured Core count')
    p.add_argument('--jetstream-count', type=int, help='Override measured JetStream count')
    p.add_argument('--inflight', type=int, default=32)
    p.add_argument('--phase-timeout', type=int, default=60)
    p.add_argument('--go', default=os.getenv('GO', 'go'))
    p.add_argument('--python', default=str(ROOT / 'sa-python-dsl/.venv/bin/python'))
    p.add_argument('--broker-image', default='nats:2.15.3-alpine')
    p.add_argument('--platform', choices=['linux/arm64', 'linux/amd64'], default='linux/arm64')
    a=p.parse_args()
    assert 1 <= a.count <= 1000000 and 1 <= a.warmup <= 100000
    assert all(value is None or 1 <= value <= 1000000 for value in (a.core_count,a.jetstream_count))
    assert 1 <= a.inflight <= 256 and 1 <= a.phase_timeout <= 300
    dest=a.artifacts.resolve(); dest.mkdir(parents=True, exist_ok=False)
    suffix=uuid.uuid4().hex[:12]; broker='sa-nats-perf-'+suffix; service=broker+'-service'; peer=broker+'-peer'; image=broker+':local'
    report={'run_id':suffix,'platform':a.platform,'count':a.count,'core_count':a.core_count or a.count,'jetstream_count':a.jetstream_count or a.count,'warmup':a.warmup,'inflight':a.inflight,'phase_timeout_seconds':a.phase_timeout,'runs':[]}
    def command(args, *, cwd=ROOT, env=None, timeout=300, log=None):
        result=subprocess.run(list(map(str,args)),cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        if log:(dest/log).write_bytes(result.stdout+b'\n--- stderr ---\n'+result.stderr)
        if result.returncode:raise RuntimeError(f'command failed ({result.returncode}): {args[0:4]}\n{result.stderr.decode(errors="replace")[-3000:]}')
        return result.stdout
    def docker(*args, **kwargs):return command(['docker',*args],**kwargs)
    def save(): (dest/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    owned=[]
    try:
        env={**os.environ,'PYTHONPATH':str(ROOT/'sa-python-dsl/src')}
        model=command([a.python,'-c',"import runpy,sys; p=runpy.run_path(sys.argv[1])['project']; assert not p.validate(),p.validate(); sys.stdout.write(p.to_yaml())",EXAMPLE/'project.py'],env=env,log='model-export.log')
        (dest/'model.yaml').write_bytes(model)
        command([a.go,'run','./scripts/nats-performance-generate',dest/'model.yaml',dest/'generated.zip'],cwd=ROOT/'servicegen',timeout=180,log='generate.log')
        generated=dest/'generated';generated.mkdir()
        with zipfile.ZipFile(dest/'generated.zip') as archive:
            for entry in archive.infolist():
                target=generated/entry.filename
                assert target.resolve().is_relative_to(generated)
                if entry.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(entry))
                target.chmod((entry.external_attr>>16)&0o777 or 0o644)
        project=generated/'natsevents';app=project/'eventprocessor'
        for source in (EXAMPLE/'go').rglob('*'):
            if source.is_file():
                target=app/source.relative_to(EXAMPLE/'go');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        (project/'go.work').write_text('go 1.26.4\nuse (\n ./eventprocessor\n '+json.dumps(str(ROOT/'servicelib'))+'\n)\n')
        buildenv={**os.environ,'GOWORK':str(project/'go.work'),'GOOS':'linux','GOARCH':a.platform.split('/')[1],'CGO_ENABLED':'0'}
        context=dest/'image';context.mkdir();shutil.copytree(app/'config',context/'config')
        command([a.go,'build','-p','2','-o',context/'service','./cmd/service'],cwd=app,env=buildenv,timeout=300,log='service-build.log')
        command([a.go,'build','-p','2','-o',context/'peer',EXAMPLE/'performance/peer.go'],cwd=ROOT/'servicelib',env=buildenv,timeout=180,log='peer-build.log')
        (context/'Dockerfile').write_text('FROM scratch\nWORKDIR /app\nCOPY service peer /app/\nCOPY config /app/config/\nENTRYPOINT ["/app/service"]\n')
        docker('build','--platform',a.platform,'-t',image,context,log='image-build.log')
        report['go_version']=command([a.go,'version']).decode().strip()
        report['service_sha256']=hashlib.sha256((context/'service').read_bytes()).hexdigest()
        report['model_sha256']=hashlib.sha256(model).hexdigest()
        report['image_id']=docker('image','inspect',image,'--format','{{.Id}}').decode().strip()
        report['broker_image_id']=docker('image','inspect',a.broker_image,'--format','{{.Id}}').decode().strip()
        host=json.loads(docker('info','--format','{{json .}}'))
        report['host_docker']={k:host.get(k) for k in ('Architecture','NCPU','MemTotal','ServerVersion','KernelVersion','OperatingSystem')}
        # No shared network or host ports. All three containers share only this
        # test-owned broker network namespace; their CPU/memory cgroups differ.
        docker('run','-d','--name',broker,'--platform',a.platform,'--network','none','--hostname','localhost','--cpus','2','--memory','512m',a.broker_image,'-js','-a','127.0.0.1','-sd','/data','-m','8222');owned.append(broker)
        docker('run','-d','--name',service,'--platform',a.platform,'--network','container:'+broker,'--cpus','1','--memory','512m',
               '-e','GOMAXPROCS=1','-e','CORE_EVENTS_SERVERS=nats://127.0.0.1:4222','-e','DURABLE_EVENTS_SERVERS=nats://127.0.0.1:4222',
               '-e','SERVICELIB_NOOP_LOGS=1','-e','SERVICELIB_NOOP_TRACING=1',image);owned.append(service)
        inspect=json.loads(docker('inspect',service))[0]
        report['service_limits']={k:inspect['HostConfig'][k] for k in ('NanoCpus','CpuQuota','CpuPeriod','Memory','NetworkMode')}
        assert report['service_limits']['NanoCpus']==1000000000
        for mode in ('core','jetstream'):
            measured_count=(a.core_count if mode=='core' else a.jetstream_count) or a.count
            for phase,count in [('warmup',a.warmup),('measure',measured_count)]:
                before=json.loads(docker('exec',service,'/app/peer','resources'));resource_start=time.monotonic()
                output=docker('run','--rm','--name',peer,'--platform',a.platform,'--network','container:'+broker,'--cpus','2','--memory','256m','--entrypoint','/app/peer',image,mode,str(count),str(a.inflight),str(a.phase_timeout),suffix+'-'+phase,timeout=a.phase_timeout+20,log=f'{mode}-{phase}.log')
                data=json.loads(output);data['phase']=phase;data['cgroup_before']=before;data['cgroup_after']=json.loads(docker('exec',service,'/app/peer','resources'))
                data['resource_window_seconds']=time.monotonic()-resource_start
                def cpu_usec(sample):
                    return int(dict(line.split() for line in sample['cpu.stat'].splitlines())['usage_usec'])
                data['cgroup_cpu_seconds']=(cpu_usec(data['cgroup_after'])-cpu_usec(before))/1e6
                data['cgroup_average_cpu_percent']=100*data['cgroup_cpu_seconds']/data['resource_window_seconds']
                assert data['cgroup_after'].get('cpu.max','').strip()=='100000 100000',data['cgroup_after']
                for metric,label in [('go_memstats_mallocs_total','allocations_per_message'),('go_memstats_alloc_bytes_total','allocated_bytes_per_message')]:
                    value=data['metric_deltas'][metric]
                    data[label]=None if value is None else value/count
                cpu=data['metric_deltas']['process_cpu_seconds_total']
                data['process_cpu_percent']=None if cpu is None else 100*cpu/data['settled_seconds']
                data['docker_stats']=json.loads(docker('stats','--no-stream','--format','{{json .}}',service,timeout=15))
                report['runs'].append(data);save()
        docker('stop','--time','10',service,timeout=20)
        state=json.loads(docker('inspect',service))[0]['State'];report['service_exit']=state
        assert state['ExitCode']==0 and not state['OOMKilled'],state
        report['status']='passed';save()
    except BaseException as error:
        report['status']='failed';report['error']=str(error);save();raise
    finally:
        for name in [service,broker]:
            if name in owned:
                result=subprocess.run(['docker','logs',name],capture_output=True,timeout=10)
                (dest/(name+'.log')).write_bytes(result.stdout+result.stderr)
        subprocess.run(['docker','rm','-f',peer,*reversed(owned)],capture_output=True,timeout=30)
        # Retain the local image and complete generated/build artifacts for review.
        print(dest/'results.json',flush=True)

if __name__=='__main__':main()
