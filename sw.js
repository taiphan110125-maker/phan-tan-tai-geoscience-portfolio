'use strict';

const CACHE_NAME='ptt-static-v16-20261001';
const PRECACHE=[
  '/',
  '/index.html',
  '/assignment-viewer.html',
  '/public-content.json',
  '/assets/ptt-brand.svg',
  '/assets/ptt-emblem.svg',
  '/assets/about-fieldwork.svg',
  '/assets/assignments-review.svg',
  '/assets/geo-ai.svg'
];

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache=>cache.addAll(PRECACHE))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(
        keys
          .filter(key=>key.startsWith('ptt-static-')&&key!==CACHE_NAME)
          .map(key=>caches.delete(key))
      ))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;

  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;

  // Admin pages must always come directly from the network.
  if(url.pathname==='/admin.html'||url.pathname==='/admin-login.html')return;

  if(url.pathname==='/public-content.json'){
    event.respondWith((async()=>{
      const cache=await caches.open(CACHE_NAME);
      try{
        const response=await fetch(request,{cache:'no-store'});
        if(response&&response.ok)await cache.put(request,response.clone());
        return response;
      }catch{
        return (await cache.match(request))
          || (await cache.match('/public-content.json'))
          || Response.error();
      }
    })());
    return;
  }

  if(request.mode==='navigate'){
    event.respondWith((async()=>{
      const cache=await caches.open(CACHE_NAME);
      try{
        const response=await fetch(request,{cache:'no-store'});
        if(response&&response.ok)await cache.put(request,response.clone());
        return response;
      }catch{
        if(url.pathname==='/assignment-viewer.html'){
          return (await cache.match('/assignment-viewer.html'))
            || Response.error();
        }
        return (await cache.match(request))
          || (await cache.match('/index.html'))
          || Response.error();
      }
    })());
    return;
  }

  if(/\.(?:svg|webp|png|jpe?g|gif|ico|css|js|json|txt)$/i.test(url.pathname)){
    event.respondWith((async()=>{
      const cache=await caches.open(CACHE_NAME);
      const cached=await cache.match(request);

      const update=fetch(request)
        .then(async response=>{
          if(response&&response.ok)await cache.put(request,response.clone());
          return response;
        });

      if(cached){
        event.waitUntil(update.catch(()=>undefined));
        return cached;
      }

      try{
        return await update;
      }catch{
        return Response.error();
      }
    })());
  }
});
