const cacheName = 'puzzle-dynamic-cache-v1';

// Install service worker and cache core files
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(cacheName).then(cache =>
      cache.addAll([
        '/',
        '/index.html',
        '/renderer.js',
        '/manifest.json'
      ])
    ).then(() => self.skipWaiting())
  );
});

// Activate service worker and clean up old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => key !== cacheName).map(key => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch & cache everything on demand
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(cached => {
      return (
        cached ||
        fetch(event.request).then(response => {
          if (!response || response.status !== 200) {
            return response;
          }
          return caches.open(cacheName).then(cache => {
            cache.put(event.request, response.clone());
            return response;
          });
        }).catch(error => {
          console.error('Fetch failed:', error);
          if (event.request.mode === 'navigate') {
            return new Response('Offline - content unavailable', {
              status: 503,
              statusText: 'Service Unavailable'
            });
          }
          throw error;
        })
      );
    }).catch(error => {
      console.error('Cache match failed:', error);
      throw error;
    })
  );
});