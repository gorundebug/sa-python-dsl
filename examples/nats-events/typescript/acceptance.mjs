import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {setTimeout as pause} from 'node:timers/promises';
import {connect} from '@nats-io/transport-node';
import {jetstream,jetstreamManager} from '@nats-io/jetstream';
const directory=await mkdtemp(join(tmpdir(),'sa-nats-ts-'));
const broker=spawn(process.env.NATS_SERVER_BINARY,['-a','127.0.0.1','-p','-1','-js','-sd',directory],{stdio:['ignore','ignore','pipe']});
let brokerLog='',serviceLog='',service,client;
broker.stderr.on('data',b=>brokerLog+=b.toString());
async function until(check) {
 const end=Date.now()+12000;
 while(Date.now()<end) {
  if(service && service.exitCode!==null) throw new Error(`service exited: ${serviceLog}`);
  if(await check()) return;
  await pause(25);
 }
 throw new Error(`deadline exceeded\nservice: ${serviceLog}\nbroker: ${brokerLog}`);
}
async function stop(child) {
 if(!child || child.exitCode!==null || child.signalCode!==null) return;
 const stopped=new Promise(resolve=>child.once('exit',resolve));
 child.kill('SIGTERM');
 const timer=setTimeout(()=>child.kill('SIGKILL'),5000);
 try {await stopped;} finally {clearTimeout(timer);}
}
try {
 await until(()=>brokerLog.includes('Server is ready'));
 const port=/Listening for client connections on 127\.0\.0\.1:(\d+)/u.exec(brokerLog)?.[1];
 assert.ok(port);
 const address=`nats://127.0.0.1:${port}`;
 client=await connect({servers:address});
 const core=client.subscribe('example.core.processed');
 const received=[];
 const collecting=(async()=>{for await(const message of core) received.push(message.json());})();
 await client.flush();
 service=spawn(process.execPath,['dist/main.generated.js'],{env:{...process.env,
  CORE_EVENTS_SERVERS:address,DURABLE_EVENTS_SERVERS:address,
  EVENT_PROCESSOR_HTTP_PORT:'0',EVENT_PROCESSOR_GRPC_PORT:'0',
  SERVICELIB_NOOP_METRICS:'1',SERVICELIB_NOOP_LOGS:'1',SERVICELIB_NOOP_TRACING:'1'},stdio:['ignore','pipe','pipe']});
 service.stdout.on('data',b=>serviceLog+=b.toString());
 service.stderr.on('data',b=>serviceLog+=b.toString());
 const manager=await jetstreamManager(client);
 await until(async()=>{try {await manager.consumers.info('EXAMPLE_IN','event_processor');await manager.streams.info('EXAMPLE_OUT');return true;} catch{return false;}});
 const encode=value=>new TextEncoder().encode(JSON.stringify(value));
 client.publish('example.core.incoming',encode({ID:'core-1',Value:'  hello core  '}));
 await client.flush();
 await jetstream(client).publish('example.durable.incoming',encode({ID:'durable-1',Value:'  hello durable  '}));
 await until(()=>received.length===1 && serviceLog.includes('"EventID":"core-1","Accepted":true') && serviceLog.includes('"EventID":"durable-1","Accepted":true'));
 assert.deepEqual(received,[{ID:'core-1',Value:'HELLO CORE'}]);
 const durable=await manager.streams.getMessage('EXAMPLE_OUT',{last_by_subj:'example.durable.processed'});
 assert.deepEqual(durable.json(),{ID:'durable-1',Value:'HELLO DURABLE'});
 await until(async()=>{const info=await manager.consumers.info('EXAMPLE_IN','event_processor');return info.num_ack_pending===0 && info.ack_floor.stream_seq>=1;});
 core.unsubscribe();await collecting;
 await stop(service);assert.equal(service.exitCode,0,serviceLog);
 console.log('PASS: generated TypeScript Core/JetStream pipelines, normalized output, correlated publication results, explicit ACK and shutdown');
} finally {
 await stop(service);await client?.close();await stop(broker);await rm(directory,{recursive:true,force:true});
}
