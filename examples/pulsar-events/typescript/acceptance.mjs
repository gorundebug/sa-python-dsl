import Pulsar from 'pulsar-client';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
const exec = promisify(execFile);
import { readFile, mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import assert from 'node:assert/strict';

const auth=process.env.PULSAR_AUTH_MANIFEST ? JSON.parse(await readFile(process.env.PULSAR_AUTH_MANIFEST,'utf8')) : undefined;
const adminUrl=auth?.adminUrl??process.env.PULSAR_TEST_ADMIN_URL;
assert.ok(adminUrl,'PULSAR_TEST_ADMIN_URL required');
const serviceUrl=auth?.url??process.env.PULSAR_TEST_URL??'pulsar://127.0.0.1:16650';
const tenant=auth ? `sa-canonical-${randomUUID()}` : 'public';
const namespace=`${tenant}/sa-ts-canonical-${randomUUID()}`;
const image=process.env.PULSAR_ACCEPTANCE_IMAGE;
const compose=process.env.PULSAR_ACCEPTANCE_COMPOSE==='1';
assert.ok(!compose||image,'Compose acceptance requires an image');
const container=`sa-pulsar-canonical-${randomUUID()}`;
const incoming=`persistent://${namespace}/incoming`,outgoing=`persistent://${namespace}/processed`;
const watchdog=setTimeout(()=>{
 console.error(`canonical exceeded 45s\n${logs}`);
 if(image)execFile('docker',['rm','--force',container],{timeout:8000},()=>process.exit(1));
 else {child?.kill('SIGKILL');process.exit(1);}
},45000);
let logs='',child,exited,client,producer,reader,envDir;
async function admin(method,path,value){
 const response=await fetch(adminUrl+path,{method,headers:{'content-type':'application/json',...(auth?{authorization:`Bearer ${auth.tokens.admin}`}:{})},...(value===undefined?{}:{body:JSON.stringify(value)}),signal:AbortSignal.timeout(5000)});
 if(response.status===404&&(method==='DELETE'||method==='GET'))return;
 const body=await response.text();assert.ok(response.ok,`${method} ${path}: ${response.status} ${body}`);
 return body?JSON.parse(body):undefined;
}
const deadline=Date.now()+30000;
async function wait(predicate){
 while(!(await predicate())){
  if(Date.now()>deadline)throw new Error(`canonical deadline exceeded\n${logs}`);
  if(child&&(child.exitCode!==null||child.signalCode!==null))throw new Error(`service exited early\n${logs}`);
  await new Promise(resolve=>setTimeout(resolve,25));
 }
}
try{
 if(auth)await admin('PUT',`/admin/v2/tenants/${tenant}`,{adminRoles:['tenant-admin'],allowedClusters:['standalone']});
 await admin('PUT',`/admin/v2/namespaces/${namespace}`,{});
 if(auth)await admin('POST',`/admin/v2/namespaces/${namespace}/permissions/producer`,['produce','consume']);
 await admin('POST',`/admin/v2/namespaces/${namespace}/autoTopicCreation`,{allowAutoTopicCreation:false});
 await admin('POST',`/admin/v2/namespaces/${namespace}/autoSubscriptionCreation`,{allowAutoSubscriptionCreation:false});
 const settings={EVENTS_SERVERS:serviceUrl,EVENTS_ADMIN_URL:adminUrl,
  ...(auth?{EVENTS_TOKEN:auth.tokens.producer,EVENTS_ADMIN_TOKEN:auth.tokens['tenant-admin']} : {}),
  RECEIVE_EVENT_TOPIC:incoming,PUBLISH_EVENT_TOPIC:outgoing,
  EVENT_PROCESSOR_HTTP_PORT:compose?'8080':'0',EVENT_PROCESSOR_GRPC_PORT:compose?'9090':'0',
  SERVICELIB_NOOP_METRICS:'1',SERVICELIB_NOOP_LOGS:'1',SERVICELIB_NOOP_TRACING:'1'};
 if(image){envDir=await mkdtemp(join(tmpdir(),'sa-pulsar-image-env-'));await writeFile(join(envDir,'runtime.env'),Object.entries(settings).map(([k,v])=>`${k}=${v}`).join('\n')+'\n',{mode:0o600});}
 let composeArgs;
 if(compose){
  // Only test endpoint names/diagnostics are added here. Connector credentials
  // and addresses must arrive through the GENERATED Compose environment list.
  const endpointNames=Object.keys(settings).filter(k=>!k.startsWith('EVENTS_'));
  const override=`services:\n  eventprocessor:\n    image: ${JSON.stringify(image)}\n    network_mode: ${JSON.stringify('container:'+(auth?.name??process.env.PULSAR_BROKER_CONTAINER??'servicelib-pulsar-acceptance'))}\n    networks: !reset []\n    ports: !reset []\n    cpus: 1\n    mem_limit: 1g\n    environment:\n${endpointNames.map(k=>'      - '+k).join('\n')}\n`;
  await writeFile(join(envDir,'compose.yaml'),override,{mode:0o600});
  composeArgs=['compose','--project-name','sa-canonical-'+randomUUID(),'-f',resolve('..','docker-compose.yml'),'-f',join(envDir,'compose.yaml'),'run','--rm','--no-deps','--name',container,'eventprocessor'];
 }
 child=compose
  ? spawn('docker',composeArgs,{env:{...process.env,...settings},stdio:['ignore','pipe','pipe']})
  : image
  ? spawn('docker',['run','--rm','--name',container,'--network',`container:${auth?.name??process.env.PULSAR_BROKER_CONTAINER??'servicelib-pulsar-acceptance'}`,
    '--cpus','1','--memory','1g','--env-file',join(envDir,'runtime.env'),image],{stdio:['ignore','pipe','pipe']})
  : spawn(process.execPath,['dist/main.generated.js'],{env:{...process.env,...settings},stdio:['ignore','pipe','pipe']});
 child.stdout.on('data',chunk=>logs+=chunk);child.stderr.on('data',chunk=>logs+=chunk);
 exited=new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',(code,signal)=>resolve({code,signal}));});
 await wait(async()=> (await admin('GET',`/admin/v2/persistent/${namespace}/incoming/subscriptions`))?.includes('event_processors') && await admin('GET',`/admin/v2/persistent/${namespace}/processed/stats`));
 client=new Pulsar.Client({serviceUrl,...(auth?{authentication:new Pulsar.AuthenticationToken({token:auth.tokens.producer})}:{}),operationTimeoutSeconds:3,connectionTimeoutMs:1000,log:()=>{}});
 if(auth){
  await admin('PUT',`/admin/v2/namespaces/${tenant}/forbidden`,{});
  await admin('PUT',`/admin/v2/persistent/${tenant}/forbidden/denied`,{});
  await assert.rejects(client.createProducer({topic:`persistent://${tenant}/forbidden/denied`,sendTimeoutMs:1000}));
 }
 producer=await client.createProducer({topic:incoming,batchingEnabled:false,sendTimeoutMs:3000});
 reader=await client.createReader({topic:outgoing,startMessageId:Pulsar.MessageId.earliest()});
 for(let i=0;i<3;i++)await producer.send({data:Buffer.from(JSON.stringify({ID:`event-${i}`,Value:' hello '}))});
 const records=new Map();
 for(let i=0;i<3;i++){
  const message=await reader.readNext();const event=JSON.parse(message.getData().toString('utf8'));
  assert.equal(event.Value,'HELLO');assert.equal(message.getPartitionKey(),event.ID);assert.ok(!records.has(event.ID));
  records.set(event.ID,message.getMessageId().serialize().toString('base64'));
 }
 await wait(async()=>{const stats=(await admin('GET',`/admin/v2/persistent/${namespace}/incoming/stats`)).subscriptions.event_processors;return stats.msgBacklog===0&&stats.unackedMessages===0;});
 const outcomes=()=>logs.split('\n').filter(line=>line.startsWith('{')&&line.includes('"Accepted":')).map(JSON.parse);
 await wait(()=>outcomes().length===3);
 for(const outcome of outcomes()){assert.equal(outcome.Accepted,true);assert.equal(outcome.MessageID,records.get(outcome.EventID));}
 assert.deepEqual([...records.keys()].sort(),['event-0','event-1','event-2']);
 if(image)await exec('docker',['stop','--time','5',container],{timeout:8000});else child.kill('SIGTERM');
 const result=await Promise.race([exited,new Promise((_,reject)=>{const timer=setTimeout(()=>reject(new Error(`shutdown timed out\n${logs}`)),5000);timer.unref();})]);
 assert.equal(result.code,0,logs);
 if(auth)for(const token of Object.values(auth.tokens))assert.ok(!logs.includes(token),'service logs must not contain credentials');
 console.log(`Canonical Pulsar TypeScript: 3 normalized outputs, native MessageID correlation, explicit ACK, environment overrides, clean shutdown${auth?', scoped native token, separate tenant-admin token, cross-namespace denial, secret-free logs':''}`);
}finally{
 try {
 if(child&&child.exitCode===null&&child.signalCode===null){if(image)await exec('docker',['rm','--force',container],{timeout:8000}).catch(()=>{});else child.kill('SIGKILL');await exited;}
 if(reader)await reader.close();if(producer)await producer.close();if(client)await client.close();
 for(const name of ['incoming','processed'])await admin('DELETE',`/admin/v2/persistent/${namespace}/${name}?force=true`);
 await admin('DELETE',`/admin/v2/namespaces/${namespace}`);
 if(auth){await admin('DELETE',`/admin/v2/persistent/${tenant}/forbidden/denied?force=true`);await admin('DELETE',`/admin/v2/namespaces/${tenant}/forbidden`);await admin('DELETE',`/admin/v2/tenants/${tenant}`);}
 } finally {
 clearTimeout(watchdog);
 if(envDir)await rm(envDir,{recursive:true,force:true});
 }
}
