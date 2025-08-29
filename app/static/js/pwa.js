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

  async loadVapidPublicKey() {
    try {
      const response = await fetch('/api/vapid-public-key');
      if (response.ok) {
        const data = await response.json();
        // Correction : utiliser 'public_key' au lieu de 'publicKey'
        this.vapidPublicKey = data.public_key || data.publicKey;
        console.log('✅ Clé VAPID publique chargée');
        console.log('🔑 Clé VAPID:', this.vapidPublicKey ? 'OK' : 'MANQUANTE');
      } else {
        console.warn('⚠️ Impossible de charger la clé VAPID publique:', response.status);
      }
    } catch (error) {
      console.error('❌ Erreur chargement clé VAPID:', error);
    }
  }
  
  setupInstallPrompt() {
    console.log('🔧 Configuration du prompt d\'installation...');
    
    window.addEventListener('beforeinstallprompt', (event) => {
      console.log('🎯 beforeinstallprompt événement déclenché !');
      event.preventDefault();
      this.installPrompt = event;
      this.showInstallButton();
      
      // Debug : vérifier que l'événement est bien capturé
      console.log('📱 Prompt d\'installation sauvegardé:', !!this.installPrompt);
    });
    
    window.addEventListener('appinstalled', () => {
      console.log('✅ App installée avec succès');
      this.hideInstallButton();
      this.showNotification('Conference Flow installé avec succès!');
      
      // Demander les notifications après installation
      setTimeout(() => {
        this.requestNotificationPermission();
      }, 2000);
    });
    
    // Debug : vérifier l'état au chargement
    console.log('🔍 État initial - installPrompt:', !!this.installPrompt);
    console.log('🔍 beforeinstallprompt supporté:', 'onbeforeinstallprompt' in window);
  }
  
  async installApp() {
    console.log('🚀 Tentative d\'installation...');
    console.log('🔍 installPrompt disponible:', !!this.installPrompt);
    
    if (!this.installPrompt) {
      console.warn('❌ Pas de prompt d\'installation disponible');
      alert('Installation PWA non disponible pour le moment. Essayez d\'ajouter le site aux favoris ou à l\'écran d\'accueil.');
      return;
    }
    
    try {
      const result = await this.installPrompt.prompt();
      console.log('📱 Résultat installation:', result.outcome);
      
      if (result.outcome === 'accepted') {
        console.log('✅ Installation acceptée par l\'utilisateur');
      } else {
        console.log('❌ Installation refusée par l\'utilisateur');
      }
      
      this.installPrompt = null;
      this.hideInstallButton();
    } catch (error) {
      console.error('❌ Erreur lors de l\'installation:', error);
    }
  }
  
  setupNetworkStatus() {
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.showNetworkStatus('En ligne', 'success');
      this.syncPendingData();
      this.syncProgramEvents(); // Resynchroniser les événements
    });
    
    window.addEventListener('offline', () => {
      this.isOnline = false;
      this.showNetworkStatus('Hors ligne', 'warning');
    });
  }
  
  async setupNotifications() {
    if (!('Notification' in window)) {
      console.warn('⚠️ Notifications non supportées par ce navigateur');
      return;
    }

    // Vérifier le statut des permissions
    this.notificationPermission = Notification.permission;
    console.log('🔔 Statut notifications:', this.notificationPermission);
    
    if (this.notificationPermission === 'granted') {
      console.log('✅ Notifications déjà autorisées');
      await this.ensurePushSubscription();
    } else if (this.notificationPermission === 'default') {
      // Attendre avant de demander les permissions (meilleure UX)
      setTimeout(() => {
        this.showNotificationPrompt();
      }, 5000);
    }
  }

  async requestNotificationPermission() {
    if (!('Notification' in window)) {
      console.warn('⚠️ Notifications non supportées');
      return false;
    }

    try {
      console.log('🔔 Demande de permission pour les notifications...');
      const permission = await Notification.requestPermission();
      this.notificationPermission = permission;
      
      if (permission === 'granted') {
        console.log('✅ Notifications autorisées');
        this.showNotification('Notifications activées ! Vous recevrez des rappels pour les sessions.');
        await this.ensurePushSubscription();
        this.hideNotificationPrompt();
        return true;
      } else {
        console.log('❌ Notifications refusées');
        this.showNotificationStatus('Notifications désactivées. Vous pouvez les réactiver dans les paramètres.', 'warning');
        return false;
      }
    } catch (error) {
      console.error('❌ Erreur demande permission:', error);
      return false;
    }
  }

  async ensurePushSubscription() {
    if (!this.registration || !this.vapidPublicKey) {
      console.warn('⚠️ Service Worker ou clé VAPID non disponible');
      console.log('🔍 Registration:', !!this.registration);
      console.log('🔍 VAPID Key:', !!this.vapidPublicKey);
      return;
    }

    try {
      // Vérifier s'il existe déjà un abonnement
      let subscription = await this.registration.pushManager.getSubscription();
      
      if (!subscription) {
        // Créer un nouvel abonnement
        console.log('📱 Création d\'un nouvel abonnement push...');
        subscription = await this.registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: this.urlB64ToUint8Array(this.vapidPublicKey)
        });
        console.log('📱 Nouvel abonnement push créé');
      } else {
        console.log('📱 Abonnement push existant trouvé');
      }
      
      // Envoyer l'abonnement au serveur
      await this.savePushSubscription(subscription);
      
    } catch (error) {
      console.error('❌ Erreur abonnement push:', error);
      this.showNotificationStatus('Erreur lors de la configuration des notifications.', 'danger');
    }
  }

  async savePushSubscription(subscription) {
    try {
      // Simplifier la requête - pas de CSRF pour le moment
      const response = await fetch('/api/push-subscription', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          subscription: subscription.toJSON(),
          userAgent: navigator.userAgent,
          preferences: this.userPreferences
        })
      });
      
      if (response.ok) {
        console.log('✅ Abonnement push sauvegardé');
      } else {
        const errorText = await response.text();
        throw new Error(`Erreur serveur: ${response.status} - ${errorText}`);
      }
      
    } catch (error) {
      console.error('❌ Erreur sauvegarde abonnement:', error);
      throw error;
    }
  }

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

  setupUI() {
    // Créer les boutons d'interface si ils n'existent pas
    this.createUIElements();
    
    // Attacher les événements
    this.attachEventListeners();
    
    // Mettre à jour l'état de l'interface
    this.updateUI();
  }

  createUIElements() {
    // Bouton d'installation (toujours créé dynamiquement pour être sûr)
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
      installBtn.innerHTML = '<i class="fas fa-download"></i> Installer l\'app';
      document.body.appendChild(installBtn);
      console.log('🔧 Bouton d\'installation créé dynamiquement');
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
      networkStatus.className = 'alert network-status';
      networkStatus.style.cssText = `
        position: fixed;
        top: 20px;
        left: 20px;
        right: 20px;
        z-index: 1060;
        display: none;
        margin: 0;
      `;
      document.body.appendChild(networkStatus);
    }
  }

  attachEventListeners() {
    // Bouton installation
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      // Supprimer les anciens listeners pour éviter les doublons
      const newInstallBtn = installBtn.cloneNode(true);
      installBtn.parentNode.replaceChild(newInstallBtn, installBtn);
      newInstallBtn.addEventListener('click', () => this.installApp());
    }

    // Bouton mise à jour
    const updateBtn = document.getElementById('update-btn');
    if (updateBtn) {
      const newUpdateBtn = updateBtn.cloneNode(true);
      updateBtn.parentNode.replaceChild(newUpdateBtn, updateBtn);
      newUpdateBtn.addEventListener('click', () => window.location.reload());
    }
  }

  // Méthodes d'affichage UI
  showInstallButton() {
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.style.display = 'block';
      console.log('👁️ Bouton d\'installation affiché');
    } else {
      console.warn('⚠️ Bouton d\'installation introuvable');
    }
  }
  
  hideInstallButton() {
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.style.display = 'none';
      console.log('👁️ Bouton d\'installation masqué');
    }
  }

  showNotificationPrompt() {
    if (this.notificationPermission !== 'default') return;
    
    console.log('🔔 Affichage du prompt de notification...');
    // Pour simplifier, utiliser une simple alerte pour le moment
    if (confirm('Voulez-vous activer les notifications pour recevoir des rappels avant les sessions ?')) {
      this.requestNotificationPermission();
    }
  }

  hideNotificationPrompt() {
    // Implémentation simplifiée
    console.log('🔔 Prompt de notification masqué');
  }
  
  showNetworkStatus(message, type) {
    const statusEl = document.getElementById('network-status');
    if (statusEl) {
      statusEl.textContent = message;
      statusEl.className = `alert alert-${type} network-status`;
      statusEl.style.display = 'block';
      
      setTimeout(() => {
        statusEl.style.display = 'none';
      }, 3000);
    }
  }

  showNotificationStatus(message, type) {
    this.showNetworkStatus(message, type);
  }

  showUpdateAvailable() {
    const updateBtn = document.getElementById('update-btn');
    if (updateBtn) {
      updateBtn.style.display = 'block';
      console.log('🔄 Mise à jour disponible');
    }
  }

  updateUI() {
    // Forcer l'affichage du bouton si le prompt est disponible
    if (this.installPrompt) {
      this.showInstallButton();
    }
  }

  // Méthodes utilitaires
  handleServiceWorkerMessage(event) {
    const message = event.data;
    
    switch (message.type) {
      case 'notification-clicked':
        this.handleNotificationClick(message.data);
        break;
      case 'background-sync':
        this.handleBackgroundSync();
        break;
    }
  }

  handleNotificationClick(data) {
    if (data.url) {
      window.location.href = data.url;
    } else if (data.type === 'event_reminder') {
      window.location.href = '/conference/programme';
    }
  }

  handleBackgroundSync() {
    console.log('🔄 Synchronisation en arrière-plan déclenchée');
    this.syncProgramEvents();
  }

  urlB64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }
  
  async syncPendingData() {
    if (this.registration && this.registration.sync) {
      await this.registration.sync.register('background-sync');
    }
  }
  
  showNotification(message, options = {}) {
    if ('Notification' in window && Notification.permission === 'granted') {
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

// Fonctions de debug globales
window.debugPWA = {
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

// Exposer certaines méthodes globalement pour l'interface admin
window.ConferenceFlowNotifications = {
  requestPermission: () => window.conferenceFlowPWA?.requestNotificationPermission(),
  getStatus: () => window.conferenceFlowPWA?.getNotificationStatus(),
  updatePreferences: (prefs) => window.conferenceFlowPWA?.updateNotificationPreferences(prefs)
};
