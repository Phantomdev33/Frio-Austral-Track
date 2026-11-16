// Pruebas de regresión de los manejadores reales de peticiones, instalación y activación del worker.
import assert from 'node:assert/strict';
const handlers=new Map(), stores=new Map();
const origin='https://frio.test';
const keyOf=r=>new URL(typeof r==='string'?r:r.url,origin).href;
const opened=[];
const storage={
 async open(name){
  opened.push(name);
  if(!stores.has(name))stores.set(name,new Map());
  const entries=stores.get(name);
  return {
   async match(r){return entries.get(keyOf(r))?.clone()},
   async put(r,response){entries.set(keyOf(r),response)},
   async addAll(requests){assert.ok(requests.every(r=>r.cache==='reload'));for(const r of requests)entries.set(keyOf(r),new Response('installed-current'))}
  };
 },
 async keys(){return [...stores.keys()]},
 async delete(name){return stores.delete(name)}
};
globalThis.self={location:{origin},addEventListener:(name,fn)=>handlers.set(name,fn),skipWaiting:async()=>{},clients:{claim:async()=>{}}};
globalThis.location={origin};
globalThis.caches=storage;
await import(new URL('../static/sw.js',import.meta.url).href+'?regression='+Date.now());
const active='frio-austral-static-v6';
const cache=await storage.open(active);
await cache.put('/static/app.css?v=new',new Response('old-mobile'));
await (await storage.open('frio-austral-static-v1')).put('/static/app.css?v=new',new Response('obsolete-mobile'));
await storage.open('another-app-cache');

async function fetchAsset(fetchImpl,path='/static/app.css?v=new'){
 globalThis.fetch=fetchImpl;
 let responsePromise;const tasks=[];
 handlers.get('fetch')({request:new Request(origin+path),respondWith:p=>{responsePromise=p},waitUntil:p=>tasks.push(p)});
 const response=await responsePromise;const text=await response.text();await Promise.all(tasks);return text;
}
const online=async request=>{assert.equal(request.cache,'no-cache');return new Response('new-desktop')};
assert.equal(await fetchAsset(online),'new-desktop');
assert.equal(await fetchAsset(online),'new-desktop','Repeated refresh must keep the desktop styles');
assert.equal(await fetchAsset(async()=>{throw new TypeError('offline')}),'new-desktop','Offline fallback must use the updated active cache');
await cache.put('/static/app.css',new Response('installed-current'));
assert.equal(await fetchAsset(async()=>{throw new TypeError('offline')},'/static/app.css?v=uncached'),'installed-current');
const lifecycle=async name=>{let done;handlers.get(name)({waitUntil:p=>{done=p}});await done};
await lifecycle('install');
await lifecycle('activate');
assert.ok(!stores.has('frio-austral-static-v1'));
assert.ok(stores.has('another-app-cache'),'Do not delete caches belonging to other apps');
console.log('PASS: online refresh, repeated refresh, offline fallback, version fallback, reload installation and scoped cache cleanup.');
