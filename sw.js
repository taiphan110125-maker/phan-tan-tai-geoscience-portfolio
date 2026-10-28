'use strict';

const CACHE_NAME='ptt-static-v24-20261028';
const PRECACHE=[
  '/',
  '/index.html',
  '/assignment-viewer.html',
  '/public-content.json',
  '/assets/ptt-brand.svg',
  '/assets/ptt-emblem.svg',
  '/assets/about-fieldwork.svg',
  '/assets/assignments-review.svg',
  '/assets/geo-ai.svg',
  '/assets/vendor/supabase-js-2.117.2.js?v=2.117.2',
  '/assets/site-language.js?v=20261028-perf2'
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
      const fallback=(await cache.match(request))
        || (await cache.match(url.pathname==='/assignment-viewer.html'?'/assignment-viewer.html':'/index.html'));
      const controller=new AbortController();
      const network=fetch(request,{cache:'no-store',signal:controller.signal})
        .then(async response=>{
          if(response&&response.ok)await cache.put(request,response.clone());
          return response;
        });
      // First navigation prefers fresh HTML; slow reloads can show a cached page.
      if(!fallback){
        try{return await network}catch{return Response.error()}
      }
      let timeoutId;
      const timeout=new Promise(resolve=>{timeoutId=setTimeout(()=>resolve(null),1200)});
      try{
        const response=await Promise.race([network,timeout]);
        if(response){clearTimeout(timeoutId);return response}
      }catch{}
      clearTimeout(timeoutId);
      // Keep updating in background for the next navigation.
      event.waitUntil(network.catch(()=>undefined));
      return fallback;
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
        // Versioned assets are immutable for this URL; avoid repeated refresh requests.
        if(url.searchParams.has('v'))return cached;
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
