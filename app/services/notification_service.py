import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from flask import current_app, has_app_context
from app import db
from ..models import db, PushSubscription, NotificationLog, User

# Import conditionnel de pywebpush
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    logging.warning("pywebpush n'est pas installé. Les notifications push ne fonctionneront pas.")

logger = logging.getLogger(__name__)

class NotificationService:
    """Service centralisé pour l'envoi de notifications push."""
    
    def __init__(self):
        self.vapid_private_key = os.getenv('VAPID_PRIVATE_KEY')
        self.vapid_public_key = os.getenv('VAPID_PUBLIC_KEY')
        self.vapid_email = os.getenv('VAPID_EMAIL', 'admin@conference-flow.local')
        
        # Import conditionnel de pywebpush
        try:
            from pywebpush import webpush, WebPushException
            self.webpush = webpush
            self.WebPushException = WebPushException
            self._available = True
        except ImportError:
            logger.warning("pywebpush non disponible - notifications désactivées")
            self.webpush = None
            self.WebPushException = None
            self._available = False
    
    def is_available(self):
        """Vérifie si le service de notification est disponible."""
        return (
            self._available and 
            self.vapid_private_key and 
            self.vapid_public_key and
            self.webpush is not None
        )
    
    def get_config_status(self):
        """Retourne le statut de la configuration."""
        return {
            'pywebpush_available': self._available,
            'vapid_keys_configured': bool(self.vapid_private_key and self.vapid_public_key),
            'service_ready': self.is_available()
        }
    
    def send_notification_to_subscription(self, subscription_data, notification_data):
        """Envoie une notification à un abonnement spécifique."""
        if not self.is_available():
            logger.error("Service de notification non disponible")
            return False
        
        try:
            # Préparer les données de la notification
            payload = json.dumps(notification_data)
            
            # Envoyer via pywebpush
            endpoint_url = subscription_data['endpoint']
            parsed = endpoint_url.split('/')
            base_url = f"{parsed[0]}//{parsed[2]}"
            
            self.webpush(
                subscription_info=subscription_data,
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims={
                    "sub": f"mailto:{self.vapid_email}",
                    "aud": base_url
                }
            )

            
            return True
            
        except self.WebPushException as e:
            logger.error(f"Erreur WebPush: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur envoi notification: {e}")
            return False
    
    def send_notification_to_user(self, user, title, body, url=None, priority='normal'):
        """Envoie une notification à un utilisateur spécifique."""
        if not user:
            return False
        
        # Récupérer les abonnements actifs de l'utilisateur
        subscriptions = PushSubscription.query.filter_by(
            user_id=user.id, 
            is_active=True
        ).all()
        
        if not subscriptions:
            logger.info(f"Aucun abonnement actif pour {user.email}")
            return False
        
        notification_data = {
            'title': title,
            'body': body,
            'icon': '/static/icons/icon-192x192.png',
            'badge': '/static/icons/badge-72x72.png',
            'url': url or '/',
            'priority': priority,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        success_count = 0
        
        for subscription in subscriptions:
            try:
                subscription_info = subscription.to_webpush_format()
                
                if self.send_notification_to_subscription(subscription_info, notification_data):
                    success_count += 1
                    
                    # Log de réussite
                    log_entry = NotificationLog(
                        user_id=user.id,
                        title=title,
                        body=body,
                        notification_type='manual',
                        priority=priority,
                        status='sent',
                        sent_at=datetime.utcnow()
                    )
                    db.session.add(log_entry)
                else:
                    # Log d'échec
                    log_entry = NotificationLog(
                        user_id=user.id,
                        title=title,
                        body=body,
                        notification_type='manual',
                        priority=priority,
                        status='failed',
                        error_message='Échec envoi WebPush'
                    )
                    db.session.add(log_entry)
                    
            except Exception as e:
                logger.error(f"Erreur notification pour {user.email}: {e}")
                
                # Log d'erreur
                log_entry = NotificationLog(
                    user_id=user.id,
                    title=title,
                    body=body,
                    notification_type='manual',
                    priority=priority,
                    status='failed',
                    error_message=str(e)
                )
                db.session.add(log_entry)
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erreur sauvegarde logs: {e}")
        
        return success_count > 0
    
    def send_broadcast_notification(self, title, body, data=None, target_users=None):
        """Envoie une notification à plusieurs utilisateurs."""
        if not target_users:
            return 0
        
        success_count = 0
        url = data.get('url') if data else None
        priority = data.get('priority', 'normal') if data else 'normal'
        
        for user in target_users:
            if self.send_notification_to_user(user, title, body, url, priority):
                success_count += 1
        
        logger.info(f"Broadcast envoyé: {success_count}/{len(target_users)} réussis")
        return success_count
    
    def send_test_notification(self, user, title="Test Conference Flow", body="Test de notification"):
        """Envoie une notification de test à un utilisateur."""
        return self.send_notification_to_user(
            user=user,
            title=title,
            body=body,
            url="/",
            priority="normal"
        )
    
    def send_event_reminder(self, event, reminder_type='15min'):
        """Envoie un rappel d'événement."""
        if reminder_type == '15min':
            title = f"Dans 15 minutes : {event.title}"
        elif reminder_type == '3min':
            title = f"Dans 3 minutes : {event.title}"
        else:
            title = f"Rappel : {event.title}"
        
        body = f"Session en {event.location}" if event.location else "Session à venir"
        
        # Envoyer à tous les utilisateurs abonnés aux rappels d'événements
        target_users = User.query.join(PushSubscription).filter(
            PushSubscription.enable_event_reminders == True,
            PushSubscription.is_active == True
        ).distinct().all()
        
        success_count = self.send_broadcast_notification(
            title=title,
            body=body,
            data={
                'url': '/conference/programme',
                'priority': 'high' if reminder_type == '3min' else 'normal',
                'event_id': event.id
            },
            target_users=target_users
        )
        
        # Marquer le rappel comme envoyé
        if reminder_type == '15min':
            event.reminder_15min_sent = True
        elif reminder_type == '3min':
            event.reminder_3min_sent = True
        
        db.session.commit()
        return success_count

# Instance globale du service
notification_service = NotificationService()

