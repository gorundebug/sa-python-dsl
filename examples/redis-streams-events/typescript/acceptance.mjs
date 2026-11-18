import { createClient } from 'redis';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import assert from 'node:assert/strict';

const url = process.env.REDIS_STREAMS_TEST_URL;
assert.ok(url, 'REDIS_STREAMS_TEST_URL required');
const client = createClient({url, password: process.env.REDIS_STREAMS_TEST_PASSWORD, socket:{connectTimeout:2000,reconnectStrategy:false}});
client.on('error',()=>{});
const prefix = `sa-ts-canonical-${randomUUID()}`;
const incoming=prefix+'-in', outgoing=prefix+'-out';
let logs='',child,exited;
const deadline=Date.now()+20000;
const wait=async(predicate)=>{
 while(!(await predicate())){
  if(Date.now()>deadline)throw new Error(`canonical deadline exceeded\n${logs}`);
  if(child && (child.exitCode!==null||child.signalCode!==null))throw new Error(`service exited early\n${logs}`);
  await new Promise(resolve=>setTimeout(resolve,25));
 }
};
try {
 await client.connect();
 child=spawn(process.execPath,['dist/main.generated.js'],{env:{...process.env,
  EVENTS_SERVERS:url,EVENTS_PASSWORD:process.env.REDIS_STREAMS_TEST_PASSWORD??'',
  RECEIVE_EVENT_STREAM_KEY:incoming,PUBLISH_EVENT_STREAM_KEY:outgoing,
  EVENT_PROCESSOR_HTTP_PORT:'0',EVENT_PROCESSOR_GRPC_PORT:'0',
  SERVICELIB_NOOP_METRICS:'1',SERVICELIB_NOOP_LOGS:'1',SERVICELIB_NOOP_TRACING:'1'},stdio:['ignore','pipe','pipe']});
 child.stdout.on('data',chunk=>logs+=chunk);child.stderr.on('data',chunk=>logs+=chunk);
 exited=new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',(code,signal)=>resolve({code,signal}));});
 await wait(async()=>await client.exists(incoming)===1);
 for(let i=0;i<3;i++)await client.xAdd(incoming,'*',{ID:`event-${i}`,Value:' hello '});
 await wait(async()=>await client.xLen(outgoing)===3 && (await client.xPending(incoming,'event_processors')).pending===0);
 const records=await client.xRange(outgoing,'-','+');
 for(let i=0;i<3;i++)assert.deepEqual({ID:records[i].message.ID,Value:records[i].message.Value},{ID:`event-${i}`,Value:'HELLO'});
 await wait(()=>logs.split('\n').filter(line=>line.includes('"Accepted":true')).length===3);
 const outcomes=logs.split('\n').filter(line=>line.startsWith('{')&&line.includes('"Accepted":')).map(JSON.parse);
 assert.equal(outcomes.length,3);
 for(let i=0;i<3;i++){assert.equal(outcomes[i].EventID,`event-${i}`);assert.equal(outcomes[i].EntryID,records[i].id);}
 child.kill('SIGTERM');
 const result=await Promise.race([exited,new Promise((_,reject)=>{const timer=setTimeout(()=>reject(new Error('shutdown timed out')),5000);timer.unref();})]);
 assert.equal(result.code,0,logs);
 process.stdout.write('Canonical Redis TypeScript: 3 normalized outputs, correlated IDs, explicit ACK, clean shutdown\n');
} finally {
 if(child && child.exitCode===null && child.signalCode===null){child.kill('SIGKILL');await exited;}
 if(client.isReady){await client.del([incoming,outgoing]);await client.quit();}
 else if(client.isOpen){client.destroy();}
}
