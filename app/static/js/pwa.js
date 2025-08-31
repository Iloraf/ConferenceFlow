// Conference Flow PWA - Gestion complète PWA et notifications push
class ConferenceFlowPWA {
  constructor() {
    this.isOnline = navigator.onLine;
    this.installPrompt = null;
    this.registration = null;
    this.vapidPublicKey = null;
    this.notificationPermission = Notification.permission;
    
    // Remplacer localStorage par variables en mémoire
    this.userPreferences = {
      eventReminders: true,
      sessionReminders: true,
      adminBroadcasts: true
    };
    this.cachedEvents = [];
    this.lastEventSync = null;
    
    this.init();
  }
  
  async init() {
    console.log('📱 Initialisation Conference Flow PWA');
    
    // Récupérer la clé publique VAPID depuis le serveur
    await this.loadVapidPublicKey();
    
    // Enregistrer le Service Worker
    if ('serviceWorker' in navigator) {
      try {
        this.registration = await navigator.serviceWorker.register('/static/sw.js');
        console.log('✅ Service Worker enregistré');
        
        // Écouter les mises à jour
        this.registration.addEventListener('updatefound', () => {
          this.showUpdateAvailable();
        });
        
        // Écouter les messages du Service Worker
        navigator.serviceWorker.addEventListener('message', (event) => {
          this.handleServiceWorkerMessage(event);
        });
        
      } catch (error) {
        console.error('❌ Erreur Service Worker:', error);
      }
    }
    
    // Gérer l'installation
    this.setupInstallPrompt();
    
    // Gérer le statut réseau
    this.setupNetworkStatus();
    
    // Initialiser les notifications
    await this.setupNotifications();
    
    // Initialiser l'interface utilisateur
    this.setupUI();
    
    // Synchroniser les événements du programme
    await this.syncProgramEvents();
  }

  // === GESTION CLÉS VAPID ===
  async loadVapidPublicKey() {
    console.log('🔑 Chargement clé VAPID publique...');
    
    try {
      const response = await fetch('/api/vapid-public-key', {
        method: 'GET',
        headers: {
          'Accept': 'application/json'
        }
      });
      
      console.log('📨 Réponse API VAPID:', response.status, response.statusText);
      
      if (!response.ok) {
        if (response.status === 503) {
          console.warn('⚠️ Notifications push non configurées sur le serveur');
          this.showNotificationStatus('Notifications push non configurées', 'warning');
        } else {
          console.error('❌ Erreur serveur clé VAPID:', response.status);
          this.showNotificationStatus('Erreur chargement configuration notifications', 'danger');
        }
        return;
      }
      
      const data = await response.json();
      console.log('📨 Données reçues:', {
        hasPublicKey: !!data.public_key,
        hasPublicKeyAlt: !!data.publicKey,
        status: data.status,
        error: data.error
      });
      
      if (data.error) {
        console.warn('⚠️ Erreur dans réponse VAPID:', data.error);
        this.showNotificationStatus(data.error, 'warning');
        return;
      }
      
      // Utiliser public_key en priorité, puis publicKey pour compatibilité
      this.vapidPublicKey = data.public_key || data.publicKey;
      
      if (this.vapidPublicKey) {
        console.log('✅ Clé VAPID publique chargée');
        console.log('🔑 Longueur clé:', this.vapidPublicKey.length);
        
        // Valider le format de la clé
        if (this.isValidVapidKey(this.vapidPublicKey)) {
          console.log('✅ Format clé VAPID valide');
        } else {
          console.error('❌ Format clé VAPID invalide');
          this.vapidPublicKey = null;
          this.showNotificationStatus('Format clé VAPID invalide', 'danger');
        }
      } else {
        console.warn('⚠️ Aucune clé VAPID publique reçue');
        this.showNotificationStatus('Clé VAPID manquante', 'warning');
      }
      
    } catch (error) {
      console.error('❌ Erreur chargement clé VAPID:', error);
      this.showNotificationStatus('Erreur connexion serveur pour notifications', 'danger');
    }
  }

  // Validation format clé VAPID
  isValidVapidKey(key) {
    if (!key || typeof key !== 'string') {
      return false;
    }
    
    // Une clé VAPID publique en base64url fait généralement 87 caractères
    const base64urlPattern = /^[A-Za-z0-9_-]+$/;
    return key.length >= 80 && key.length <= 90 && base64urlPattern.test(key);
  }
  
  // === GESTION INSTALLATION PWA ===
  setupInstallPrompt() {
    console.log('🔧 Configuration du prompt d\'installation...');
    
    window.addEventListener('beforeinstallprompt', (event) => {
      console.log('🎯 beforeinstallprompt événement déclenché !');
      event.preventDefault();
      this.installPrompt = event;
      this.showInstallButton();
      
      console.log('📱 Prompt d\'installation sauvegardé:', !!this.installPrompt);
    });
    
    window.addEventListener('appinstalled', (event) => {
      console.log('✅ Application installée !');
      this.hideInstallButton();
      this.showNotificationStatus('Conference Flow installée avec succès !', 'success');
      this.installPrompt = null;
    });
  }

  async installApp() {
    if (!this.installPrompt) {
      console.warn('⚠️ Pas de prompt d\'installation disponible');
      return;
    }

    try {
      const result = await this.installPrompt.prompt();
      console.log('📱 Résultat installation:', result.outcome);
      
      if (result.outcome === 'accepted') {
        console.log('✅ Utilisateur a accepté l\'installation');
      } else {
        console.log('❌ Utilisateur a refusé l\'installation');
      }
      
      this.installPrompt = null;
      this.hideInstallButton();
      
    } catch (error) {
      console.error('❌ Erreur installation:', error);
    }
  }

  // === GESTION SERVICE WORKER ===
  async waitForServiceWorkerReady() {
    console.log('⏳ Attente service worker...');
    
    if (!this.registration) {
      throw new Error('Aucun service worker enregistré');
    }
    
    // Attendre que le SW soit dans l'état correct
    if (this.registration.installing) {
      console.log('📦 Service worker en cours d\'installation...');
      await new Promise((resolve) => {
        this.registration.installing.addEventListener('statechange', () => {
          if (this.registration.installing.state === 'installed') {
            console.log('✅ Service worker installé');
            resolve();
          }
        });
      });
    }
    
    if (this.registration.waiting) {
      console.log('⏳ Service worker en attente...');
      // Activer le nouveau service worker
      this.registration.waiting.postMessage({ action: 'skipWaiting' });
      await new Promise((resolve) => {
        navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true });
      });
    }
    
    // S'assurer qu'on a un service worker actif
    await navigator.serviceWorker.ready;
    
    if (!this.registration.active) {
      throw new Error('Service worker non actif');
    }
    
    console.log('✅ Service worker prêt pour abonnement push');
    return true;
  }

  // === GESTION NOTIFICATIONS ===
  async setupNotifications() {
    console.log('🔔 Configuration des notifications...');
    
    if (!('Notification' in window)) {
      console.warn('⚠️ Notifications non supportées');
      return;
    }

    // Vérifier si l'utilisateur a déjà donné la permission
    if (this.notificationPermission === 'granted') {
      console.log('✅ Permission notifications déjà accordée');
      // Configurer l'abonnement push si pas encore fait
      if (this.registration && this.vapidPublicKey) {
        await this.ensurePushSubscription();
      }
    } else if (this.notificationPermission === 'default') {
      console.log('❔ Permission notifications pas encore demandée');
      this.showNotificationPrompt();
    } else {
      console.log('❌ Notifications refusées');
    }
  }

  async requestNotificationPermission() {
    console.log('🔔 === DÉMARRAGE DEMANDE PERMISSION ===');
    
    // Faire un diagnostic complet d'abord
    await this.diagnosticPushState();
    
    // Vérifier le support du navigateur
    if (!('Notification' in window)) {
      console.warn('⚠️ Notifications non supportées');
      this.showNotificationStatus('Notifications non supportées par ce navigateur', 'warning');
      return false;
    }

    try {
      console.log('🔔 Demande de permission pour les notifications...');
      const permission = await Notification.requestPermission();
      this.notificationPermission = permission;
      
      console.log('📋 Permission obtenue:', permission);
      
      if (permission === 'granted') {
        console.log('✅ Notifications autorisées par l\'utilisateur');
        
        // Montrer une notification de test
        this.showNotification('Notifications activées ! Vous recevrez des rappels pour les sessions.');
        
        // S'assurer que le service worker est prêt
        try {
          await this.waitForServiceWorkerReady();
          console.log('✅ Service worker validé');
        } catch (error) {
          console.error('❌ Service worker non prêt:', error);
          this.showNotificationStatus(`Service worker: ${error.message}`, 'danger');
          return false;
        }
        
        // Créer l'abonnement push
        console.log('🚀 Création abonnement push...');
        const subscriptionSuccess = await this.ensurePushSubscription();
        
        if (subscriptionSuccess) {
          this.hideNotificationPrompt();
          console.log('✅ === CONFIGURATION PUSH TERMINÉE AVEC SUCCÈS ===');
          return true;
        } else {
          console.error('❌ Échec configuration abonnement push');
          return false;
        }
        
      } else if (permission === 'denied') {
        console.log('❌ Notifications refusées par l\'utilisateur');
        this.showNotificationStatus(
          'Notifications désactivées. Vous pouvez les réactiver dans les paramètres du navigateur.', 
          'warning'
        );
        return false;
        
      } else {
        console.log('⏸️ Permission en attente');
        this.showNotificationStatus('Permission en attente. Cliquez sur "Autoriser" dans la barre d\'adresse.', 'info');
        return false;
      }
      
    } catch (error) {
      console.error('❌ Erreur demande permission:', error);
      this.showNotificationStatus(`Erreur: ${error.message}`, 'danger');
      return false;
    }
  }

  async ensurePushSubscription() {
    console.log('🔔 Démarrage ensurePushSubscription...');
    
    // Vérifications préalables plus robustes
    if (!this.registration) {
      console.error('❌ Aucun service worker enregistré');
      this.showNotificationStatus('Service Worker non disponible', 'danger');
      return false;
    }
    
    if (!this.vapidPublicKey) {
      console.error('❌ Clé VAPID publique non disponible');
      this.showNotificationStatus('Configuration VAPID manquante', 'danger');
      return false;
    }
    
    // Attendre que le service worker soit prêt
    await navigator.serviceWorker.ready;
    console.log('✅ Service Worker prêt');

    try {
      // Vérifier l'état actuel de l'abonnement
      let subscription = await this.registration.pushManager.getSubscription();
      console.log('📱 État abonnement existant:', !!subscription);
      
      if (subscription) {
        // Vérifier que l'abonnement est encore valide
        console.log('🔍 Vérification validité abonnement existant...');
        try {
          // Test de validité en tentant une requête vers l'endpoint
          const testResponse = await fetch(subscription.endpoint, { method: 'HEAD' });
          console.log('🔍 Test endpoint:', testResponse.status);
        } catch (error) {
          console.warn('⚠️ Abonnement peut-être invalide:', error.message);
          // Si l'endpoint ne répond pas, on peut garder l'abonnement quand même
        }
      }
      
      if (!subscription) {
        console.log('📱 Création d\'un nouvel abonnement push...');
        
        // S'assurer que le service worker est actif
        if (this.registration.installing) {
          console.log('⏳ Attente installation SW...');
          await new Promise((resolve) => {
            this.registration.installing.onstatechange = () => {
              if (this.registration.installing.state === 'installed') {
                resolve();
              }
            };
          });
        }
        
        // Créer l'abonnement
        subscription = await this.registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: this.urlB64ToUint8Array(this.vapidPublicKey)
        });
        console.log('✅ Nouvel abonnement push créé');
      } else {
        console.log('✅ Abonnement push existant validé');
      }
      
      // Sauvegarder l'abonnement sur le serveur
      const saveSuccess = await this.savePushSubscription(subscription);
      
      if (saveSuccess) {
        console.log('✅ Abonnement sauvegardé sur le serveur');
        this.showNotificationStatus('Notifications configurées avec succès', 'success');
        return true;
      } else {
        throw new Error('Échec sauvegarde serveur');
      }
      
    } catch (error) {
      console.error('❌ Erreur abonnement push:', error);
      
      let errorMessage = 'Erreur configuration des notifications';
      if (error.name === 'NotSupportedError') {
        errorMessage = 'Notifications push non supportées sur cet appareil';
      } else if (error.name === 'NotAllowedError') {
        errorMessage = 'Permission requise pour les notifications';
      } else if (error.message.includes('network')) {
        errorMessage = 'Problème de connexion réseau';
      }
      
      this.showNotificationStatus(errorMessage, 'danger');
      return false;
    }
  }

  async savePushSubscription(subscription) {
    console.log('💾 Sauvegarde abonnement push...');
    
    if (!subscription) {
      console.error('❌ Pas d\'abonnement à sauvegarder');
      return false;
    }
    
    try {
      // Préparer les données à envoyer
      const subscriptionData = {
        subscription: subscription.toJSON(),
        userAgent: navigator.userAgent,
        preferences: this.userPreferences,
        timestamp: new Date().toISOString()
      };
      
      console.log('📤 Envoi données abonnement...', {
        endpoint: subscription.endpoint ? 'OK' : 'MANQUANT',
        keys: subscription.toJSON().keys ? 'OK' : 'MANQUANT'
      });
      
      const response = await fetch('/api/push-subscription', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(subscriptionData)
      });
      
      console.log('📨 Réponse serveur:', response.status, response.statusText);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Erreur serveur:', response.status, errorText);
        
        // Messages d'erreur spécifiques
        if (response.status === 401) {
          throw new Error('Non authentifié - reconnectez-vous');
        } else if (response.status === 400) {
          throw new Error('Données d\'abonnement invalides');
        } else if (response.status === 503) {
          throw new Error('Service de notifications non configuré');
        } else {
          throw new Error(`Erreur serveur: ${response.status} - ${errorText}`);
        }
      }
      
      const responseData = await response.json();
      console.log('✅ Réponse serveur:', responseData);
      
      if (responseData.success) {
        console.log('✅ Abonnement push sauvegardé avec succès');
        return true;
      } else {
        throw new Error(responseData.message || 'Échec sauvegarde inconnue');
      }
      
    } catch (error) {
      console.error('❌ Erreur sauvegarde abonnement:', error);
      
      // Afficher l'erreur à l'utilisateur
      this.showNotificationStatus(`Erreur sauvegarde: ${error.message}`, 'danger');
      
      return false;
    }
  }

  // === DIAGNOSTIC ET DEBUG ===
  async diagnosticPushState() {
    console.log('🔍 === DIAGNOSTIC ÉTAT PUSH ===');
    
    // Vérifier le support du navigateur
    const browserSupport = {
      serviceWorker: 'serviceWorker' in navigator,
      pushManager: 'PushManager' in window,
      notification: 'Notification' in window
    };
    console.log('🌐 Support navigateur:', browserSupport);
    
    // État des permissions
    const permission = Notification.permission;
    console.log('🔐 Permission notifications:', permission);
    
    // État du service worker
    if (this.registration) {
      console.log('📱 Service Worker:', {
        installing: !!this.registration.installing,
        waiting: !!this.registration.waiting,
        active: !!this.registration.active,
        scope: this.registration.scope
      });
      
      // État de l'abonnement push
      try {
        const subscription = await this.registration.pushManager.getSubscription();
        console.log('📡 Abonnement actuel:', {
          exists: !!subscription,
          endpoint: subscription ? subscription.endpoint.substring(0, 50) + '...' : null,
          hasKeys: subscription ? !!(subscription.toJSON().keys) : false
        });
      } catch (error) {
        console.error('❌ Erreur lecture abonnement:', error);
      }
    } else {
      console.log('❌ Aucun service worker enregistré');
    }
    
    // État de la clé VAPID
    console.log('🔑 Clé VAPID:', {
      loaded: !!this.vapidPublicKey,
      length: this.vapidPublicKey ? this.vapidPublicKey.length : 0,
      valid: this.vapidPublicKey ? this.isValidVapidKey(this.vapidPublicKey) : false
    });
    
    console.log('🔍 === FIN DIAGNOSTIC ===');
  }

  // === GESTION RÉSEAU ===
  setupNetworkStatus() {
    console.log('🌐 Configuration statut réseau...');
    
    // Écouter les changements de connectivité
    window.addEventListener('online', () => {
      console.log('🌐 Connexion rétablie');
      this.isOnline = true;
      this.showNetworkStatus('Connexion rétablie', 'success', 3000);
      this.syncProgramEvents();
    });

    window.addEventListener('offline', () => {
      console.log('📱 Mode hors ligne');
      this.isOnline = false;
      this.showNetworkStatus('Mode hors ligne', 'warning');
    });

    // Afficher le statut initial si hors ligne
    if (!this.isOnline) {
      this.showNetworkStatus('Mode hors ligne', 'warning');
    }
  }

  // === SYNCHRONISATION DONNÉES ===
  async syncProgramEvents() {
    if (!this.isOnline) {
      console.log('⚠️ Hors ligne - synchronisation des événements reportée');
      return;
    }

    try {
      const response = await fetch('/api/program-events');
      if (response.ok) {
        const events = await response.json();
        this.storeEventsInMemory(events);
        console.log(`✅ ${events.length} événements du programme synchronisés`);
      } else {
        console.warn('⚠️ Erreur synchronisation événements:', response.status);
      }
    } catch (error) {
      console.error('❌ Erreur synchronisation événements:', error);
    }
  }

  storeEventsInMemory(events) {
    // Remplacer localStorage par stockage en mémoire
    this.cachedEvents = events;
    this.lastEventSync = Date.now();
    console.log('💾 Événements stockés en mémoire:', events.length);
  }

  getStoredEvents() {
    return this.cachedEvents || [];
  }

  // === INTERFACE UTILISATEUR ===
  setupUI() {
    this.createUIElements();
    this.attachEventListeners();
    this.updateUI();
  }

  createUIElements() {
    // Bouton d'installation
    let installBtn = document.getElementById('install-btn');
    if (!installBtn) {
      installBtn = document.createElement('button');
      installBtn.id = 'install-btn';
      installBtn.className = 'btn btn-primary pwa-install-btn';
      installBtn.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 1050;
        display: none;
        border-radius: 25px;
        padding: 12px 20px;
        box-shadow: 0 4px 12px rgba(0,123,255,0.4);
        font-size: 14px;
        font-weight: 500;
      `;
      installBtn.innerHTML = '<i class="fas fa-download"></i> Installer Conference Flow';
      document.body.appendChild(installBtn);
      console.log('🔧 Bouton d\'installation créé');
    }

    // Bouton de mise à jour
    let updateBtn = document.getElementById('update-btn');
    if (!updateBtn) {
      updateBtn = document.createElement('button');
      updateBtn.id = 'update-btn';
      updateBtn.className = 'btn btn-warning pwa-update-btn';
      updateBtn.style.cssText = `
        position: fixed;
        bottom: 20px;
        left: 20px;
        z-index: 1050;
        display: none;
        border-radius: 25px;
        padding: 12px 20px;
        box-shadow: 0 4px 12px rgba(255,193,7,0.4);
      `;
      updateBtn.innerHTML = '<i class="fas fa-sync"></i> Mettre à jour';
      document.body.appendChild(updateBtn);
    }

    // Status réseau
    let networkStatus = document.getElementById('network-status');
    if (!networkStatus) {
      networkStatus = document.createElement('div');
      networkStatus.id = 'network-status';
      networkStatus.className = 'network-status alert';
      networkStatus.style.cssText = `
        position: fixed;
        top: 1rem;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1052;
        display: none;
        min-width: 200px;
        text-align: center;
        border-radius: 0.5rem;
        padding: 0.75rem 1rem;
        font-weight: 500;
      `;
      document.body.appendChild(networkStatus);
    }
  }

  attachEventListeners() {
    // Installation
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.addEventListener('click', () => {
        this.installApp();
      });
    }

    // Mise à jour
    const updateBtn = document.getElementById('update-btn');
    if (updateBtn) {
      updateBtn.addEventListener('click', () => {
        window.location.reload();
      });
    }
  }

  updateUI() {
    // Mettre à jour l'affichage basé sur l'état actuel
    if (!this.isOnline) {
      this.showNetworkStatus('Mode hors ligne', 'warning');
    }
  }

  // === MÉTHODES UTILITAIRES UI ===
  showInstallButton() {
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.style.display = 'block';
      console.log('📱 Bouton d\'installation affiché');
    }
  }

  hideInstallButton() {
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.style.display = 'none';
    }
  }

  showUpdateAvailable() {
    const updateBtn = document.getElementById('update-btn');
    if (updateBtn) {
      updateBtn.style.display = 'block';
      this.showNotificationStatus('Mise à jour disponible !', 'info');
    }
  }

  showNotificationPrompt() {
    // Simple prompt intégré
    const hasPrompt = document.getElementById('notification-prompt');
    if (!hasPrompt) {
      const promptDiv = document.createElement('div');
      promptDiv.id = 'notification-prompt';
      promptDiv.className = 'notification-prompt';
      promptDiv.style.cssText = `
        position: fixed;
        bottom: 1rem;
        left: 1rem;
        right: 1rem;
        z-index: 1049;
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      `;
      
      promptDiv.innerHTML = `
        <h6><i class="fas fa-bell"></i> Activer les notifications</h6>
        <p class="mb-3">Recevez des rappels pour vos sessions et événements.</p>
        <button class="btn btn-primary btn-sm me-2" onclick="window.conferenceFlowPWA.requestNotificationPermission()">
          Activer
        </button>
        <button class="btn btn-secondary btn-sm" onclick="this.parentElement.remove()">
          Plus tard
        </button>
      `;
      
      document.body.appendChild(promptDiv);
      console.log('🔔 Prompt de notification affiché');
    }
  }

  hideNotificationPrompt() {
    const prompt = document.getElementById('notification-prompt');
    if (prompt) {
      prompt.remove();
    }
  }

  showNetworkStatus(message, type = 'info', timeout = 0) {
    const statusEl = document.getElementById('network-status');
    if (!statusEl) return;

    statusEl.className = `network-status alert alert-${type}`;
    statusEl.textContent = message;
    statusEl.style.display = 'block';

    if (timeout > 0) {
      setTimeout(() => {
        statusEl.style.display = 'none';
      }, timeout);
    }
  }

  showNotificationStatus(message, type = 'info', timeout = 5000) {
    console.log(`📢 Status: ${message} (${type})`);
    this.showNetworkStatus(message, type, timeout);
  }

  handleServiceWorkerMessage(event) {
    console.log('📨 Message du Service Worker:', event.data);
    
    if (event.data?.action === 'update-available') {
      this.showUpdateAvailable();
    }
  }

  // === UTILITAIRES ===
  urlB64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  showNotification(message, options = {}) {
    if (this.notificationPermission === 'granted') {
      new Notification('Conference Flow', {
        body: message,
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/badge-72x72.png',
        ...options
      });
    }
  }

  // Méthodes publiques pour l'interaction avec l'interface
  async updateNotificationPreferences(preferences) {
    this.userPreferences = { ...this.userPreferences, ...preferences };
    
    // Mettre à jour l'abonnement sur le serveur
    if (this.registration) {
      const subscription = await this.registration.pushManager.getSubscription();
      if (subscription) {
        await this.savePushSubscription(subscription);
      }
    }
  }

  getNotificationStatus() {
    return {
      permission: this.notificationPermission,
      supported: 'Notification' in window,
      pushSupported: 'serviceWorker' in navigator && 'PushManager' in window,
      preferences: this.userPreferences
    };
  }
}

// Initialiser la PWA au chargement
document.addEventListener('DOMContentLoaded', () => {
  console.log('🚀 Chargement de Conference Flow PWA...');
  window.conferenceFlowPWA = new ConferenceFlowPWA();
});

// === FONCTIONS DEBUG GLOBALES AMÉLIORÉES ===
window.debugPWA = {
  // Debug état général
  async checkState() {
    if (window.conferenceFlowPWA) {
      await window.conferenceFlowPWA.diagnosticPushState();
    } else {
      console.error('❌ ConferenceFlowPWA non initialisée');
    }
  },
  
  // Tester l'abonnement complet
  async testFullSubscription() {
    if (!window.conferenceFlowPWA) {
      console.error('❌ PWA non initialisée');
      return;
    }
    
    console.log('🧪 === TEST ABONNEMENT COMPLET ===');
    
    try {
      // 1. Vérifier la clé VAPID
      await window.conferenceFlowPWA.loadVapidPublicKey();
      
      // 2. Demander permission
      const permissionSuccess = await window.conferenceFlowPWA.requestNotificationPermission();
      
      console.log('🧪 Résultat test:', permissionSuccess ? 'SUCCÈS' : 'ÉCHEC');
      
    } catch (error) {
      console.error('🧪 Erreur test:', error);
    }
  },
  
  // Forcer un nouvel abonnement
  async forceNewSubscription() {
    if (!window.conferenceFlowPWA || !window.conferenceFlowPWA.registration) {
      console.error('❌ Service worker non disponible');
      return;
    }
    
    try {
      console.log('🔄 Suppression ancien abonnement...');
      const oldSubscription = await window.conferenceFlowPWA.registration.pushManager.getSubscription();
      if (oldSubscription) {
        await oldSubscription.unsubscribe();
        console.log('✅ Ancien abonnement supprimé');
      }
      
      console.log('🆕 Création nouvel abonnement...');
      const success = await window.conferenceFlowPWA.ensurePushSubscription();
      console.log('🔄 Résultat:', success ? 'SUCCÈS' : 'ÉCHEC');
      
    } catch (error) {
      console.error('❌ Erreur force subscription:', error);
    }
  },
  
  // Vérifier la connectivité API
  async testApiConnection() {
    console.log('🌐 Test connexion API...');
    
    try {
      const vapidResponse = await fetch('/api/vapid-public-key');
      console.log('🔑 API VAPID:', vapidResponse.status, vapidResponse.statusText);
      
      const subscriptionResponse = await fetch('/api/push-subscription', {
        method: 'OPTIONS'  // Test CORS/disponibilité
      });
      console.log('📡 API Subscription:', subscriptionResponse.status, subscriptionResponse.statusText);
      
    } catch (error) {
      console.error('❌ Erreur test API:', error);
    }
  },
  
  // Test notification locale
  testLocalNotification() {
    if (window.conferenceFlowPWA) {
      window.conferenceFlowPWA.showNotification('🧪 Test notification locale', {
        body: 'Ceci est un test depuis la console',
        tag: 'debug-test'
      });
    }
  },
  
  // Réinitialiser complètement
  async reset() {
    if (window.conferenceFlowPWA) {
      console.log('🔄 Réinitialisation complète...');
      
      // Supprimer l'abonnement existant
      if (window.conferenceFlowPWA.registration) {
        const subscription = await window.conferenceFlowPWA.registration.pushManager.getSubscription();
        if (subscription) {
          await subscription.unsubscribe();
          console.log('✅ Abonnement supprimé');
        }
      }
      
      // Recharger la clé VAPID
      await window.conferenceFlowPWA.loadVapidPublicKey();
      
      console.log('✅ Réinitialisation terminée');
    }
  },
  
  checkInstallPrompt: () => {
    console.log('🔍 Install prompt disponible:', !!window.conferenceFlowPWA?.installPrompt);
    console.log('🔍 Service Worker enregistré:', !!window.conferenceFlowPWA?.registration);
    console.log('🔍 Clé VAPID chargée:', !!window.conferenceFlowPWA?.vapidPublicKey);
  },
  
  forceInstall: () => {
    if (window.conferenceFlowPWA?.installPrompt) {
      window.conferenceFlowPWA.installApp();
    } else {
      console.log('❌ Pas de prompt d\'installation disponible');
    }
  },
  
  testNotification: () => {
    if (window.conferenceFlowPWA) {
      window.conferenceFlowPWA.showNotification('Test de notification !');
    }
  }
};

// Exposer les méthodes de notification améliorées
window.ConferenceFlowNotifications = {
  requestPermission: () => window.conferenceFlowPWA?.requestNotificationPermission(),
  getStatus: () => window.conferenceFlowPWA?.getNotificationStatus(),
  updatePreferences: (prefs) => window.conferenceFlowPWA?.updateNotificationPreferences(prefs),
  
  // Nouvelles méthodes de debug
  diagnostic: () => window.conferenceFlowPWA?.diagnosticPushState(),
  test: () => window.debugPWA.testFullSubscription(),
  reset: () => window.debugPWA.reset()
};

