// Read-only diagnosis of the exact Context composition used by the Redis source.
// This is a lifetime assertion, never a substitute for generated-service timing.
import {getEventListeners, setMaxListeners} from 'node:events';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const {Context} = await import(pathToFileURL(process.argv[2] ?? '/app/.tsservicelib/dist/runtime/context.js').href);
const ownerController = new AbortController();
const generation = new AbortController();
setMaxListeners(0, ownerController.signal, generation.signal);
const owner = new Context(ownerController.signal);
const samples = [];
for (let i = 1; i <= 1024; i++) {
  // datasource/redisstreams/index.ts: the per-record generation context.
  const delivery = owner.withExternalCancellation(generation.signal);
  const requestCancel = new AbortController();
  delivery.withExternalCancellation(requestCancel.signal);
  requestCancel.abort(new Error('request finalized'));
  if (i === 1 || i === 128 || i === 1024) samples.push({completedRequests:i,
    ownerListeners:getEventListeners(ownerController.signal,'abort').length,
    generationListeners:getEventListeners(generation.signal,'abort').length});
}
assert.equal(samples.at(-1).ownerListeners,1024);
assert.equal(samples.at(-1).generationListeners,1024);
generation.abort();
const afterGenerationStop = {ownerListeners:getEventListeners(ownerController.signal,'abort').length,
  generationListeners:getEventListeners(generation.signal,'abort').length};
assert.deepEqual(afterGenerationStop,{ownerListeners:0,generationListeners:0});
console.log(JSON.stringify({runtime:process.version,samples,afterGenerationStop,
  finding:'Per-record intermediate generation contexts retain parent listeners after request finalization until generation stop.'},null,2));
