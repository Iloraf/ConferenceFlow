
class ConferenceFlowPWA {
  constructor() {
    this.isOnline = navigator.onLine;
    this.installPrompt = null;
    this.registration = null;
    
    this.init();
  }
  
  async init() {
    console.log('📱 Initialisation Conference Flow PWA');
    
    // Enregistrer le Service Worker
    if ('serviceWorker' in navigator) {
      try {
        this.registration = await navigator.serviceWorker.register('/static/sw.js');
        console.log('✅ Service Worker enregistré');
        
        // Écouter les mises à jour
        this.registration.addEventListener('updatefound', () => {
          this.showUpdateAvailable();
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
    this.setupNotifications();
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
  
  showInstallButton() {
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.style.display = 'block';
      installBtn.addEventListener('click', () => this.installApp());
    }
  }
  
  hideInstallButton() {
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
      installBtn.style.display = 'none';
    }
  }
  
  setupNetworkStatus() {
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.showNetworkStatus('En ligne', 'success');
      this.syncPendingData();
    });
    
    window.addEventListener('offline', () => {
      this.isOnline = false;
      this.showNetworkStatus('Hors ligne', 'warning');
    });
  }
  
  showNetworkStatus(message, type) {
    const statusEl = document.getElementById('network-status');
    if (statusEl) {
      statusEl.textContent = message;
      statusEl.className = `alert alert-${type}`;
      statusEl.style.display = 'block';
      
      setTimeout(() => {
        statusEl.style.display = 'none';
      }, 3000);
    }
  }
  
  async setupNotifications() {
    if ('Notification' in window) {
      const permission = await Notification.requestPermission();
      
      if (permission === 'granted') {
        console.log('✅ Notifications autorisées');
        
        // S'abonner aux notifications push
        if (this.registration && 'pushManager' in this.registration) {
          await this.subscribeToPush();
        }
      }
    }
  }
  
  async subscribeToPush() {
    try {
      const subscription = await this.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: this.urlB64ToUint8Array('YOUR_VAPID_PUBLIC_KEY')
      });
      
      // Envoyer la subscription au serveur
      await fetch('/api/push-subscription', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(subscription)
      });
      
      console.log('✅ Abonnement push configuré');
    } catch (error) {
      console.error('❌ Erreur push subscription:', error);
    }
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
  
  showNotification(message) {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('Conference Flow', {
        body: message,
        icon: '/static/icons/icon-192x192.png'
      });
    }
  }
  
  showUpdateAvailable() {
    const updateBtn = document.getElementById('update-btn');
    if (updateBtn) {
      updateBtn.style.display = 'block';
      updateBtn.addEventListener('click', () => {
        window.location.reload();
      });
    }
  }
}

// Initialiser la PWA au chargement
document.addEventListener('DOMContentLoaded', () => {
  window.conferenceFlowPWA = new ConferenceFlowPWA();
});
