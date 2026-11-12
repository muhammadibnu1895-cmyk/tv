// INU TV testing PWA. Cache only the app shell; never cache playlists, scanner data, or video segments.
const CACHE='inu-tv-test-shell-v411';
const SHELL=['./main39.html','./inu-tv-manifest.webmanifest','./inu-tv-icon-192.png','./inu-tv-icon-512.png'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('inu-tv-test-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',event=>{
 const req=event.request;
 if(req.method!=='GET'||req.mode!=='navigate')return;
 const u=new URL(req.url);
 if(u.origin!==self.location.origin||!u.pathname.endsWith('/main39.html'))return;
 event.respondWith(fetch(req).then(res=>{if(res.ok){const clone=res.clone();caches.open(CACHE).then(cache=>cache.put('./main39.html',clone)).catch(()=>{})}return res}).catch(()=>caches.match('./main39.html')));
});
