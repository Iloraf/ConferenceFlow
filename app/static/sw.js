
const CACHE_NAME = 'conference-flow-v1.0.0';
const STATIC_CACHE = 'static-v1';
const DYNAMIC_CACHE = 'dynamic-v1';

// Fichiers à mettre en cache immédiatement
const STATIC_FILES = [
  '/',
  '/static/css/bootstrap.min.css',
  '/static/css/style.css',
  '/static/js/bootstrap.bundle.min.js',
  '/static/js/app.js',
  '/static/icons/icon-192x192.png',
  '/static/manifest.json',
  '/auth/login',
  '/profile'
];

// URLs à mettre en cache dynamiquement
const DYNAMIC_URLS = [
  '/mes-communications',
  '/conference/programme',
  '/conference/communications',
  '/conference/contacts'
];

// Installation du Service Worker
self.addEventListener('install', (event) => {
  console.log('📱 Service Worker: Installation...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('📱 Cache statique créé');
        return cache.addAll(STATIC_FILES);
      })
      .then(() => {
        console.log('✅ Service Worker installé');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('❌ Erreur installation SW:', error);
      })
  );
});

// Activation du Service Worker
self.addEventListener('activate', (event) => {
  console.log('📱 Service Worker: Activation...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('🗑️ Suppression ancien cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('✅ Service Worker activé');
        return self.clients.claim();
      })
  );
});

// Interception des requêtes réseau
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  
  // Ignorer les requêtes non-HTTP
  if (!request.url.startsWith('http')) {
    return;
  }
  
  // Stratégie Cache First pour les ressources statiques
  if (STATIC_FILES.includes(url.pathname) || 
      request.url.includes('/static/')) {
    
    event.respondWith(
      caches.match(request)
        .then((response) => {
          return response || fetch(request);
        })
    );
    return;
  }
  
  // Stratégie Network First pour le contenu dynamique
  event.respondWith(
    fetch(request)
      .then((response) => {
        // Mettre en cache les réponses réussies
        if (response.status === 200) {
          const responseClone = response.clone();
          caches.open(DYNAMIC_CACHE)
            .then((cache) => {
              cache.put(request, responseClone);
            });
        }
        return response;
      })
      .catch(() => {
        // Fallback vers le cache en cas d'échec réseau
        return caches.match(request)
          .then((response) => {
            if (response) {
              return response;
            }
            
            // Page offline de fallback
            if (request.headers.get('accept').includes('text/html')) {
              return caches.match('/offline.html');
            }
          });
      })
  );
});

// Synchronisation en arrière-plan
self.addEventListener('sync', (event) => {
  if (event.tag === 'background-sync') {
    console.log('🔄 Synchronisation en arrière-plan');
    event.waitUntil(doBackgroundSync());
  }
});

// Notifications Push
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'Nouvelle notification Conference Flow',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'Voir',
        icon: '/static/icons/checkmark.png'
      },
      {
        action: 'close',
        title: 'Fermer',
        icon: '/static/icons/xmark.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('Conference Flow', options)
  );
});

// Fonction de synchronisation
async function doBackgroundSync() {
  try {
    // Synchroniser les données locales avec le serveur
    const pendingData = await getStoredData('pending-submissions');
    
    if (pendingData.length > 0) {
      for (const item of pendingData) {
        await submitToServer(item);
        await removeStoredData('pending-submissions', item.id);
      }
    }
    
    console.log('✅ Synchronisation terminée');
  } catch (error) {
    console.error('❌ Erreur synchronisation:', error);
  }
}

// Utilitaires pour le stockage local
async function getStoredData(key) {
  // Implémentation du stockage IndexedDB
  return [];
}

async function removeStoredData(store, id) {
  // Implémentation de suppression
}

async function submitToServer(data) {
  // Implémentation de soumission
}
