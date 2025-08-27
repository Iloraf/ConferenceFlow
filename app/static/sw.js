const CACHE_NAME = 'conference-flow-v1.1.0';
const STATIC_CACHE = 'static-v1.1';
const DYNAMIC_CACHE = 'dynamic-v1.1';
const API_CACHE = 'api-v1';

// Fichiers à mettre en cache immédiatement
const STATIC_FILES = [
  '/',
  '/static/css/bootstrap.min.css',
  '/static/css/style.css',
  '/static/css/mobile.css',
  '/static/js/bootstrap.bundle.min.js',
  '/static/js/app.js',
  '/static/js/pwa.js',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/icons/badge-72x72.png',
  '/static/manifest.json',
  '/auth/login',
  '/profile',
  '/offline.html'
];

// URLs à mettre en cache dynamiquement
const DYNAMIC_URLS = [
  '/mes-communications',
  '/conference/programme',
  '/conference/communications',
  '/conference/contacts'
];

// APIs à mettre en cache avec stratégie Network First
const API_URLS = [
  '/api/program-events',
  '/api/vapid-public-key'
];

// Installation du Service Worker
self.addEventListener('install', (event) => {
  console.log('📱 Service Worker: Installation Conference Flow...');
  
  event.waitUntil(
    Promise.all([
      // Cache statique
      caches.open(STATIC_CACHE).then((cache) => {
        console.log('📱 Cache statique créé');
        return cache.addAll(STATIC_FILES.filter(url => url !== '/offline.html'));
      }),
      
      // Page offline séparée
      caches.open(STATIC_CACHE).then((cache) => {
        return cache.add('/offline.html').catch(() => {
          // Si la page offline n'existe pas, créer une version de base
          const offlineResponse = new Response(`
            <!DOCTYPE html>
            <html>
            <head>
              <title>Conference Flow - Hors ligne</title>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 2rem; }
                .offline { color: #666; }
                .logo { font-size: 2rem; margin: 2rem 0; color: #007bff; }
              </style>
            </head>
            <body>
              <div class="logo">📱 Conference Flow</div>
              <h1>Hors ligne</h1>
              <p class="offline">Vous êtes actuellement hors ligne. Reconnectez-vous pour accéder au contenu.</p>
              <button onclick="window.location.reload()">Réessayer</button>
            </body>
            </html>
          `, {
            headers: { 'Content-Type': 'text/html' }
          });
          return cache.put('/offline.html', offlineResponse);
        });
      })
    ]).then(() => {
      console.log('✅ Service Worker Conference Flow installé');
      return self.skipWaiting();
    }).catch((error) => {
      console.error('❌ Erreur installation SW:', error);
    })
  );
});

// Activation du Service Worker
self.addEventListener('activate', (event) => {
  console.log('📱 Service Worker: Activation Conference Flow...');
  
  event.waitUntil(
    Promise.all([
      // Nettoyer les anciens caches
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (![STATIC_CACHE, DYNAMIC_CACHE, API_CACHE].includes(cacheName)) {
              console.log('🗑️ Suppression ancien cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      }),
      
      // Prendre le contrôle de tous les clients
      self.clients.claim()
    ]).then(() => {
      console.log('✅ Service Worker Conference Flow activé');
    })
  );
});

// Interception des requêtes réseau
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  
  // Ignorer les requêtes non-HTTP et les requêtes POST/PUT/DELETE par défaut
  if (!request.url.startsWith('http') || 
      (request.method !== 'GET' && !isApiRequest(url.pathname))) {
    return;
  }
  
  // Stratégie Cache First pour les ressources statiques
  if (isStaticResource(url.pathname)) {
    event.respondWith(cacheFirst(request));
    return;
  }
  
  // Stratégie Network First pour les APIs
  if (isApiRequest(url.pathname)) {
    event.respondWith(networkFirstWithCache(request, API_CACHE));
    return;
  }
  
  // Stratégie Network First pour le contenu dynamique
  event.respondWith(networkFirstWithFallback(request));
});

// Gestion des notifications push
self.addEventListener('push', (event) => {
  console.log('🔔 Notification push reçue');
  
  let notificationData = {};
  
  try {
    notificationData = event.data ? JSON.parse(event.data.text()) : {};
  } catch (error) {
    console.error('❌ Erreur parsing notification:', error);
    notificationData = {
      title: 'Conference Flow',
      body: 'Nouvelle notification'
    };
  }
  
  const options = {
    body: notificationData.body || 'Nouvelle notification Conference Flow',
    icon: notificationData.icon || '/static/icons/icon-192x192.png',
    badge: notificationData.badge || '/static/icons/badge-72x72.png',
    vibrate: notificationData.vibrate || [100, 50, 100],
    data: {
      url: notificationData.data?.url || '/',
      type: notificationData.data?.type || 'general',
      event_id: notificationData.data?.event_id,
      timestamp: Date.now(),
      ...notificationData.data
    },
    actions: notificationData.actions || [
      {
        action: 'view',
        title: 'Voir',
        icon: '/static/icons/view.png'
      },
      {
        action: 'dismiss',
        title: 'Ignorer',
        icon: '/static/icons/close.png'
      }
    ],
    requireInteraction: notificationData.requireInteraction || false,
    tag: notificationData.tag || 'conference-flow',
    renotify: true,
    timestamp: notificationData.timestamp || Date.now()
  };
  
  const title = notificationData.title || 'Conference Flow';
  
  event.waitUntil(
    self.registration.showNotification(title, options).then(() => {
      console.log('✅ Notification affichée:', title);
    }).catch((error) => {
      console.error('❌ Erreur affichage notification:', error);
    })
  );
});

// Gestion des clics sur les notifications
self.addEventListener('notificationclick', (event) => {
  console.log('🔔 Clic sur notification:', event.action);
  
  const notification = event.notification;
  const data = notification.data || {};
  
  notification.close();
  
  // Gestion des actions
  if (event.action === 'dismiss') {
    console.log('🔔 Notification ignorée');
    return;
  }
  
  let targetUrl = data.url || '/';
  
  // URLs spécifiques selon le type de notification
  if (event.action === 'view' || !event.action) {
    switch (data.type) {
      case 'event_reminder':
        targetUrl = data.event_id ? 
          `/conference/programme#event-${data.event_id}` : 
          '/conference/programme';
        break;
      case 'admin_broadcast':
        targetUrl = '/';
        break;
      default:
        targetUrl = data.url || '/';
    }
  }
  
  // Ouvrir ou focuser la fenêtre
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Chercher une fenêtre existante avec l'URL cible
      const existingClient = clientList.find(client => {
        return client.url.includes(self.location.origin) && client.visibilityState === 'visible';
      });
      
      if (existingClient) {
        // Focuser et naviguer dans la fenêtre existante
        return existingClient.focus().then(() => {
          if (existingClient.navigate) {
            return existingClient.navigate(targetUrl);
          } else {
            // Envoyer un message pour navigation
            existingClient.postMessage({
              type: 'notification-clicked',
              data: { url: targetUrl, ...data }
            });
          }
        });
      } else {
        // Ouvrir une nouvelle fenêtre
        return clients.openWindow(targetUrl);
      }
    }).catch((error) => {
      console.error('❌ Erreur ouverture fenêtre:', error);
      // Fallback: essayer d'ouvrir quand même
      return clients.openWindow(targetUrl);
    })
  );
});

// Synchronisation en arrière-plan
self.addEventListener('sync', (event) => {
  console.log('🔄 Synchronisation en arrière-plan:', event.tag);
  
  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

// Fonctions utilitaires pour les stratégies de cache

function isStaticResource(pathname) {
  return pathname.startsWith('/static/') || 
         STATIC_FILES.some(file => pathname === file || pathname.endsWith(file));
}

function isApiRequest(pathname) {
  return pathname.startsWith('/api/') || 
         API_URLS.some(api => pathname.startsWith(api));
}

async function cacheFirst(request) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.error('❌ Erreur cache first:', error);
    // Fallback vers le cache même si expiré
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    // Si pas de cache, retourner page offline pour les pages HTML
    if (request.headers.get('accept').includes('text/html')) {
      return caches.match('/offline.html');
    }
    throw error;
  }
}

async function networkFirstWithCache(request, cacheName) {
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('🔄 Fallback vers cache pour:', request.url);
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    throw error;
  }
}

async function networkFirstWithFallback(request) {
  try {
    const networkResponse = await fetch(request);
    
    // Mettre en cache les réponses réussies
    if (networkResponse.ok && networkResponse.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('🔄 Fallback vers cache pour:', request.url);
    
    // Essayer le cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Page offline pour les requêtes HTML
    if (request.headers.get('accept').includes('text/html')) {
      return caches.match('/offline.html');
    }
    
    // Réponse générique pour les autres types
    return new Response('Contenu non disponible hors ligne', {
      status: 503,
      statusText: 'Service Unavailable'
    });
  }
}

// Fonction de synchronisation en arrière-plan
async function doBackgroundSync() {
  console.log('🔄 Démarrage synchronisation en arrière-plan');
  
  try {
    // Synchroniser les événements du programme
    await syncProgramEvents();
    
    // Synchroniser les données en attente
    await syncPendingData();
    
    console.log('✅ Synchronisation en arrière-plan terminée');
  } catch (error) {
    console.error('❌ Erreur synchronisation en arrière-plan:', error);
  }
}

async function syncProgramEvents() {
  try {
    const response = await fetch('/api/program-events');
    if (response.ok) {
      const events = await response.json();
      
      // Stocker dans le cache API
      const cache = await caches.open(API_CACHE);
      cache.put('/api/program-events', response.clone());
      
      console.log(`✅ ${events.length} événements synchronisés`);
    }
  } catch (error) {
    console.error('❌ Erreur sync événements:', error);
  }
}

async function syncPendingData() {
  try {
    // Ici on pourrait synchroniser des données en attente
    // Par exemple des soumissions faites hors ligne
    
    // Récupérer les données en attente depuis IndexedDB
    const pendingData = await getStoredData('pending-submissions');
    
    for (const item of pendingData) {
      try {
        await submitToServer(item);
        await removeStoredData('pending-submissions', item.id);
        console.log('✅ Donnée synchronisée:', item.id);
      } catch (error) {
        console.error('❌ Erreur sync donnée:', item.id, error);
      }
    }
    
  } catch (error) {
    console.error('❌ Erreur sync données en attente:', error);
  }
}

// Utilitaires pour le stockage IndexedDB (version simplifiée)
async function getStoredData(storeName) {
  // Implémentation simplifiée - en production utiliser IndexedDB
  try {
    const data = await caches.match(`/offline-data/${storeName}`);
    if (data) {
      return await data.json();
    }
  } catch (error) {
    console.error('❌ Erreur lecture données stockées:', error);
  }
  return [];
}

async function removeStoredData(storeName, id) {
  // Implémentation simplifiée
  try {
    const cache = await caches.open('offline-data');
    await cache.delete(`/offline-data/${storeName}/${id}`);
  } catch (error) {
    console.error('❌ Erreur suppression données:', error);
  }
}

async function submitToServer(data) {
  // Soumettre les données au serveur
  const response = await fetch(data.endpoint, {
    method: data.method || 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...data.headers
    },
    body: JSON.stringify(data.payload)
  });
  
  if (!response.ok) {
    throw new Error(`Erreur serveur: ${response.status}`);
  }
  
  return response;
}

// Gestion des messages depuis la page principale
self.addEventListener('message', (event) => {
  const message = event.data;
  
  switch (message.type) {
    case 'skip-waiting':
      self.skipWaiting();
      break;
      
    case 'cache-clear':
      clearCaches().then(() => {
        event.ports[0].postMessage({ success: true });
      }).catch((error) => {
        event.ports[0].postMessage({ success: false, error: error.message });
      });
      break;
      
    case 'cache-program':
      if (message.events) {
        cacheEventsData(message.events);
      }
      break;
  }
});

async function clearCaches() {
  const cacheNames = await caches.keys();
  await Promise.all(
    cacheNames.map(cacheName => caches.delete(cacheName))
  );
  console.log('✅ Tous les caches supprimés');
}

async function cacheEventsData(events) {
  try {
    const cache = await caches.open(API_CACHE);
    const response = new Response(JSON.stringify(events), {
      headers: { 'Content-Type': 'application/json' }
    });
    await cache.put('/api/program-events', response);
    console.log('✅ Événements mis en cache');
  } catch (error) {
    console.error('❌ Erreur cache événements:', error);
  }
}

console.log('📱 Service Worker Conference Flow chargé');

