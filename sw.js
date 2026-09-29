'use strict';

const CACHE_NAME='ptt-static-v4-20260930';
const PRECACHE=[
  '/',
  '/index.html',
  '/assignment-viewer.html',
  '/assets/ptt-brand.svg',
  '/assets/ptt-emblem.svg',
  '/assets/hero-oil-geology-exact.webp',
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
      .then(keys=>Promise.all(keys.filter(key=>key.startsWith('ptt-static-')&&key!==CACHE_NAME).map(key=>caches.delete(key))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;

  if(request.mode==='navigate'){
    event.respondWith((async()=>{
      const cache=await caches.open(CACHE_NAME);
      try{
        const response=await fetch(request);
        if(response&&response.ok)cache.put(request,response.clone());
        return response;
      }catch{
        return (await cache.match(request)) || (await cache.match('/index.html'));
      }
    })());
    return;
  }

  if(/\.(?:svg|webp|png|jpe?g|gif|ico|css|js)$/i.test(url.pathname)){
    event.respondWith((async()=>{
      const cache=await caches.open(CACHE_NAME);
      const cached=await cache.match(request);
      const update=fetch(request).then(response=>{
        if(response&&response.ok)cache.put(request,response.clone());
        return response;
      }).catch(()=>cached);
      return cached || update;
    })());
  }
});
