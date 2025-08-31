// Service Worker pour Conference Flow
const CACHE_NAME = 'conference-flow-v1.0.0';
const STATIC_CACHE = 'static-v1.0';
const DYNAMIC_CACHE = 'dynamic-v1.0';
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

// Installation du Service Worker
self.addEventListener('install', (event) => {
  console.log('📱 Service Worker: Installation Conference Flow...');
  
  event.waitUntil(
    Promise.all([
      caches.open(STATIC_CACHE).then((cache) => {
        console.log('📱 Cache statique créé');
        return cache.addAll(STATIC_FILES.filter(url => url !== '/offline.html'));
      }),
      
      caches.open(STATIC_CACHE).then((cache) => {
        return cache.add('/offline.html').catch(() => {
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
      self.clients.claim()
    ]).then(() => {
      console.log('✅ Service Worker Conference Flow activé');
    })
  );
});

// **GESTION COMPLÈTE DES NOTIFICATIONS PUSH**
self.addEventListener('push', (event) => {
  console.log('🔔 Notification push reçue dans SW');
  
  let notificationData = {
    title: 'Conference Flow',
    body: 'Nouvelle notification',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge-72x72.png',
    url: '/'
  };
  
  // Traiter les données de la notification
  try {
    if (event.data) {
      const payload = event.data.json();
      console.log('📨 Données reçues:', payload);
      
      notificationData = {
        title: payload.title || 'Conference Flow',
        body: payload.body || 'Nouvelle notification',
        icon: payload.icon || '/static/icons/icon-192x192.png',
        badge: payload.badge || '/static/icons/badge-72x72.png',
        url: payload.url || '/',
        tag: payload.tag || 'conference-flow',
        requireInteraction: payload.priority === 'high',
        actions: payload.actions || []
      };
    }
  } catch (error) {
    console.error('❌ Erreur parsing notification:', error);
  }
  
  // Afficher la notification
  event.waitUntil(
    self.registration.showNotification(notificationData.title, {
      body: notificationData.body,
      icon: notificationData.icon,
      badge: notificationData.badge,
      tag: notificationData.tag,
      requireInteraction: notificationData.requireInteraction,
      actions: notificationData.actions,
      data: {
        url: notificationData.url,
        timestamp: new Date().getTime()
      }
    }).then(() => {
      console.log('✅ Notification affichée');
    }).catch((error) => {
      console.error('❌ Erreur affichage notification:', error);
    })
  );
});

// Gestion des clics sur les notifications
self.addEventListener('notificationclick', (event) => {
  console.log('👆 Clic sur notification');
  
  event.notification.close();
  
  const targetUrl = event.notification.data?.url || '/';
  
  event.waitUntil(
    clients.matchAll({
      type: 'window',
      includeUncontrolled: true
    }).then((clientList) => {
      // Chercher si une fenêtre est déjà ouverte avec l'URL cible
      for (const client of clientList) {
        if (client.url === targetUrl && 'focus' in client) {
          console.log('🎯 Focus sur fenêtre existante');
          return client.focus();
        }
      }
      
      // Ouvrir une nouvelle fenêtre si aucune n'est trouvée
      if (clients.openWindow) {
        console.log('🆕 Ouverture nouvelle fenêtre');
        return clients.openWindow(targetUrl);
      }
    })
  );
});

// Fermeture de notification
self.addEventListener('notificationclose', (event) => {
  console.log('❌ Notification fermée:', event.notification.tag);
});

// Gestion des requêtes réseau (cache)
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  
  if (!request.url.startsWith('http') || 
      (request.method !== 'GET' && !isApiRequest(url.pathname))) {
    return;
  }
  
  if (isStaticResource(url.pathname)) {
    event.respondWith(cacheFirst(request));
    return;
  }
  
  if (isApiRequest(url.pathname)) {
    event.respondWith(networkFirstWithCache(request, API_CACHE));
    return;
  }
  
  event.respondWith(networkFirstWithFallback(request));
});

// Fonctions utilitaires pour le cache
function isStaticResource(pathname) {
  return pathname.startsWith('/static/') || 
         pathname.endsWith('.css') || 
         pathname.endsWith('.js') || 
         pathname.endsWith('.png') ||
         pathname.endsWith('.ico') ||
         pathname === '/manifest.json';
}

function isApiRequest(pathname) {
  return pathname.startsWith('/api/');
}

async function cacheFirst(request) {
  try {
    const cache = await caches.open(STATIC_CACHE);
    const cached = await cache.match(request);
    
    if (cached) {
      return cached;
    }
    
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
    
  } catch (error) {
    const cached = await caches.match(request);
    return cached || new Response('Ressource non disponible', { status: 503 });
  }
}

async function networkFirstWithCache(request, cacheName) {
  try {
    const response = await fetch(request);
    
    if (response.ok && request.method === 'GET') {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    
    return response;
    
  } catch (error) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    return cached || new Response('API non disponible', { 
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

async function networkFirstWithFallback(request) {
  try {
    const response = await fetch(request);
    
    if (response.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
    }
    
    return response;
    
  } catch (error) {
    const cache = await caches.open(DYNAMIC_CACHE);
    const cached = await cache.match(request);
    
    if (cached) {
      return cached;
    }
    
    // Fallback vers la page offline pour les pages HTML
    if (request.headers.get('accept').includes('text/html')) {
      const offlineCache = await caches.open(STATIC_CACHE);
      return offlineCache.match('/offline.html');
    }
    
    return new Response('Contenu non disponible', { status: 503 });
  }
}
