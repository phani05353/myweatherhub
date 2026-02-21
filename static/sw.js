const CACHE_NAME = 'weather-hub-v1';
// Only include files we are 100% sure exist
const ASSETS = [
    '/',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/weather-icons/2.0.12/css/weather-icons.min.css',
    'https://cdn.jsdelivr.net/npm/chart.js'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            // Using map + Promise.allSettled ensures one 404 won't kill the SW
            return Promise.allSettled(
                ASSETS.map(url => cache.add(url).catch(err => console.log("Failed to cache:", url)))
            );
        })
    );
});

self.addEventListener('fetch', (event) => {
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});