const CACHE='frio-austral-static-v6';
const ASSETS=['/static/app.css','/static/thermal.js','/static/app.js','/static/shop.js','/static/icon.svg','/static/icon-192.png','/static/icon-512.png','/static/manifest.webmanifest'];
const PRIVATE='frio-austral-current-session';
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS.map(path=>new Request(new URL(path,self.location.origin),{cache:'reload'})))).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('frio-austral-static-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('message',event=>{if(event.data?.type==='logout')event.waitUntil(caches.delete(PRIVATE))});
self.addEventListener('fetch',event=>{
 if(event.request.method!=='GET'||new URL(event.request.url).origin!==location.origin)return;
 const url=new URL(event.request.url);
 // No guardar respuestas privadas de la API ni páginas personales en las cachés compartidas.
 // Actualizar los recursos desde la red y usar la caché actual como respaldo sin conexión.
 if(ASSETS.includes(url.pathname)){
  const network=fetch(new Request(event.request,{cache:'no-cache'}));
  const update=network.then(async response=>{
   if(response.ok){const copy=response.clone();const cache=await caches.open(CACHE);await cache.put(event.request,copy)}
  }).catch(()=>{});
  event.waitUntil(update);
  event.respondWith(network.then(async response=>{
   if(response.ok)return response;
   const cache=await caches.open(CACHE);
   return await cache.match(event.request)||await cache.match(url.pathname)||response;
  }).catch(async()=>{
   const cache=await caches.open(CACHE);
   return await cache.match(event.request)||await cache.match(url.pathname)||Response.error();
  }));
  return;
 }
 if(event.request.mode==='navigate')event.respondWith(fetch(event.request).then(async response=>{
  if(url.pathname==='/conductor/'&&response.ok&&!response.redirected){const cache=await caches.open(PRIVATE);await cache.put('/conductor/',response.clone())}
  return response;
 }).catch(async()=>{
  if(url.pathname==='/conductor/'){const cached=await caches.match('/conductor/',{cacheName:PRIVATE});if(cached)return cached}
  return new Response('<!doctype html><html lang="es"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sin conexión</title><body style="font:16px system-ui;padding:32px;background:#f1f5f8;color:#102d45"><h1>Tu ruta está a salvo</h1><p>Abre la pantalla del conductor si ya la cargaste en este dispositivo. Para iniciar una sesión nueva, recupera la conexión.</p><a href="/conductor/">Volver a mi ruta</a><p><button onclick="location.reload()">Reintentar</button></p></body></html>',{headers:{'Content-Type':'text/html; charset=utf-8'}});
 }));
});
