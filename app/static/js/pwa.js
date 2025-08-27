class ConferenceFlowPWA {
  constructor() {
    this.isOnline = navigator.onLine;
    this.installPrompt = null;
    this.registration = null;
    this.vapidPublicKey = null;
    this.notificationPermission = Notification.permission;
    this.userPreferences = this.loadUserPreferences();
    
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
        this.vapidPublicKey = data.publicKey;
        console.log('✅ Clé VAPID publique chargée');
      } else {
        console.warn('⚠️ Impossible de charger la clé VAPID publique');
      }
    } catch (error) {
      console.error('❌ Erreur chargement clé VAPID:', error);
    }
  }
  
  setupInstallPrompt() {
    window.addEventListener('beforeinstallprompt', (event) => {
      event.preventDefault();
      this.installPrompt = event;
      this.showInstallButton();
    });
    
    window.addEventListener('appinstalled', () => {
      console.log('✅ App installée');
      this.hideInstallButton();
      this.showNotification('Conference Flow installé avec succès!');
      
      // Demander les notifications après installation
      setTimeout(() => {
        this.requestNotificationPermission();
      }, 2000);
    });
  }
  
  async installApp() {
    if (!this.installPrompt) {
      return;
    }
    
    const result = await this.installPrompt.prompt();
    console.log('📱 Résultat installation:', result.outcome);
    
    this.installPrompt = null;
    this.hideInstallButton();
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
      return false;
    }

    try {
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
      return;
    }

    try {
      // Vérifier s'il existe déjà un abonnement
      let subscription = await this.registration.pushManager.getSubscription();
      
      if (!subscription) {
        // Créer un nouvel abonnement
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
      const response = await fetch('/api/push-subscription', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
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
        throw new Error(`Erreur serveur: ${response.status}`);
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
        this.storeEventsLocally(events);
        console.log(`✅ ${events.length} événements du programme synchronisés`);
      }
    } catch (error) {
      console.error('❌ Erreur synchronisation événements:', error);
    }
  }

  storeEventsLocally(events) {
    try {
      localStorage.setItem('conferenceflow_events', JSON.stringify(events));
      localStorage.setItem('conferenceflow_events_sync', Date.now().toString());
    } catch (error) {
      console.error('❌ Erreur stockage événements:', error);
    }
  }

  getStoredEvents() {
    try {
      const eventsData = localStorage.getItem('conferenceflow_events');
      return eventsData ? JSON.parse(eventsData) : [];
    } catch (error) {
      console.error('❌ Erreur lecture événements stockés:', error);
      return [];
    }
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
    // Bouton d'installation (si pas déjà présent)
    if (!document.getElementById('install-btn')) {
      const installBtn = document.createElement('button');
      installBtn.id = 'install-btn';
      installBtn.className = 'btn btn-primary pwa-install-btn';
      installBtn.style.display = 'none';
      installBtn.innerHTML = '<i class="fas fa-download"></i> Installer l\'app';
      document.body.appendChild(installBtn);
    }

    // Bouton de mise à jour
    if (!document.getElementById('update-btn')) {
      const updateBtn = document.createElement('button');
      updateBtn.id = 'update-btn';
      updateBtn.className = 'btn btn-warning pwa-update-btn';
      updateBtn.style.display = 'none';
      updateBtn.innerHTML = '<i class="fas fa-sync"></i> Mettre à jour';
      document.body.appendChild(updateBtn);
    }

    // Status réseau
    if (!document.getElementById('network-status')) {
      const networkStatus = document.createElement('div');
      networkStatus.id = 'network-status';
      networkStatus.className = 'network-status';
      networkStatus.style.display = 'none';
      document.body.appendChild(networkStatus);
    }

    // Prompt pour les notifications
    if (!document.getElementById('notification-prompt')) {
      const notificationPrompt = document.createElement('div');
      notificationPrompt.id = 'notification-prompt';
      notificationPrompt.className = 'notification-prompt';
      notificationPrompt.style.display = 'none';
      notificationPrompt.innerHTML = `
        <div class="card">
          <div class="card-body">
            <h6><i class="fas fa-bell"></i> Activer les notifications</h6>
            <p class="small">Recevez des rappels avant les sessions qui vous intéressent.</p>
            <div class="d-flex gap-2">
              <button id="enable-notifications" class="btn btn-primary btn-sm">Activer</button>
              <button id="dismiss-notifications" class="btn btn-outline-secondary btn-sm">Plus tard</button>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(notificationPrompt);
    }
  }

  attachEventListeners() {
    // Bouton installation
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.addEventListener('click', () => this.installApp());
    }

    // Bouton mise à jour
    const updateBtn = document.getElementById('update-btn');
    if (updateBtn) {
      updateBtn.addEventListener('click', () => window.location.reload());
    }

    // Boutons notifications
    const enableBtn = document.getElementById('enable-notifications');
    const dismissBtn = document.getElementById('dismiss-notifications');
    
    if (enableBtn) {
      enableBtn.addEventListener('click', () => this.requestNotificationPermission());
    }
    
    if (dismissBtn) {
      dismissBtn.addEventListener('click', () => this.hideNotificationPrompt());
    }
  }

  // Méthodes d'affichage UI
  showInstallButton() {
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.style.display = 'block';
    }
  }
  
  hideInstallButton() {
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.style.display = 'none';
    }
  }

  showNotificationPrompt() {
    if (this.notificationPermission !== 'default') return;
    
    const prompt = document.getElementById('notification-prompt');
    if (prompt) {
      prompt.style.display = 'block';
      setTimeout(() => prompt.classList.add('show'), 100);
    }
  }

  hideNotificationPrompt() {
    const prompt = document.getElementById('notification-prompt');
    if (prompt) {
      prompt.classList.remove('show');
      setTimeout(() => prompt.style.display = 'none', 300);
    }
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
    // Réutilise le système de statut réseau pour les notifications
    this.showNetworkStatus(message, type);
  }

  showUpdateAvailable() {
    const updateBtn = document.getElementById('update-btn');
    if (updateBtn) {
      updateBtn.style.display = 'block';
    }
  }

  updateUI() {
    // Mettre à jour l'état des boutons selon les permissions
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.style.display = this.installPrompt ? 'block' : 'none';
    }
  }

  // Méthodes utilitaires
  handleServiceWorkerMessage(event) {
    const message = event.data;
    
    switch (message.type) {
      case 'notification-clicked':
        // Gérer les clics sur notifications
        this.handleNotificationClick(message.data);
        break;
      case 'background-sync':
        // Gérer la synchronisation en arrière-plan
        this.handleBackgroundSync();
        break;
    }
  }

  handleNotificationClick(data) {
    // Naviguer vers la page appropriée selon le type de notification
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

  loadUserPreferences() {
    try {
      const prefs = localStorage.getItem('conferenceflow_notification_prefs');
      return prefs ? JSON.parse(prefs) : {
        eventReminders: true,
        sessionReminders: true,
        adminBroadcasts: true
      };
    } catch (error) {
      return {
        eventReminders: true,
        sessionReminders: true,
        adminBroadcasts: true
      };
    }
  }

  saveUserPreferences(preferences) {
    try {
      this.userPreferences = { ...this.userPreferences, ...preferences };
      localStorage.setItem('conferenceflow_notification_prefs', JSON.stringify(this.userPreferences));
    } catch (error) {
      console.error('❌ Erreur sauvegarde préférences:', error);
    }
  }

  getCSRFToken() {
    // Récupérer le token CSRF depuis les métadonnées ou cookies
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    return metaTag ? metaTag.getAttribute('content') : '';
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
    this.saveUserPreferences(preferences);
    
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
  window.conferenceFlowPWA = new ConferenceFlowPWA();
});

// Exposer certaines méthodes globalement pour l'interface admin
window.ConferenceFlowNotifications = {
  requestPermission: () => window.conferenceFlowPWA?.requestNotificationPermission(),
  getStatus: () => window.conferenceFlowPWA?.getNotificationStatus(),
  updatePreferences: (prefs) => window.conferenceFlowPWA?.updateNotificationPreferences(prefs)
};

