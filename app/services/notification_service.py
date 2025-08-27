import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from flask import current_app, has_app_context
from app import db

# Import conditionnel de pywebpush
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    logging.warning("pywebpush n'est pas installé. Les notifications push ne fonctionneront pas.")

class NotificationService:
    """Service principal pour gérer les notifications push de Conference Flow."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Les configurations seront chargées à la demande
        self._vapid_private_key = None
        self._vapid_public_key = None
        self._vapid_claims = None
        self._initialized = False
        
        if not WEBPUSH_AVAILABLE:
            self.logger.warning("pywebpush non disponible - notifications push désactivées")
    
    def _ensure_initialized(self):
        """Initialise le service avec les configurations de l'app si pas déjà fait."""
        if self._initialized or not has_app_context():
            return
        
        try:
            # Charger la configuration depuis current_app
            self._vapid_private_key = current_app.config.get('VAPID_PRIVATE_KEY')
            self._vapid_public_key = current_app.config.get('VAPID_PUBLIC_KEY')
            self._vapid_claims = {
                "sub": current_app.config.get('VAPID_SUBJECT', "mailto:admin@conference-flow.com")
            }
            
            if not self._vapid_private_key or not self._vapid_public_key:
                self.logger.warning("Clés VAPID manquantes. Les notifications push ne fonctionneront pas.")
            elif self._vapid_private_key in ['VAPID_KEYS_NOT_GENERATED', 'NOTIFICATIONS_DISABLED']:
                self.logger.warning("Clés VAPID non configurées. Générez les clés avec configure.py.")
            else:
                self.logger.info("✅ Service de notifications initialisé avec les clés VAPID")
            
            self._initialized = True
            
        except Exception as e:
            self.logger.error(f"Erreur initialisation service notifications: {e}")
    
    @property
    def vapid_private_key(self):
        """Getter pour la clé privée VAPID (initialisation lazy)."""
        self._ensure_initialized()
        return self._vapid_private_key
    
    @property
    def vapid_public_key(self):
        """Getter pour la clé publique VAPID (initialisation lazy)."""
        self._ensure_initialized()
        return self._vapid_public_key
    
    @property
    def vapid_claims(self):
        """Getter pour les claims VAPID (initialisation lazy)."""
        self._ensure_initialized()
        return self._vapid_claims
    
    def is_available(self):
        """Vérifie si le service de notifications est disponible et configuré."""
        if not WEBPUSH_AVAILABLE:
            return False
        
        self._ensure_initialized()
        
        return (self.vapid_private_key and 
                self.vapid_public_key and 
                self.vapid_private_key not in ['VAPID_KEYS_NOT_GENERATED', 'NOTIFICATIONS_DISABLED'])
    
    def send_push_notification(self, subscription, title: str, 
                             message: str, data: Dict[Any, Any] = None,
                             notification_type: str = 'general') -> bool:
        """
        Envoie une notification push à un abonnement donné.
        
        Args:
            subscription: L'abonnement push de l'utilisateur (objet PushSubscription)
            title: Titre de la notification
            message: Contenu de la notification
            data: Données additionnelles (optionnel)
            notification_type: Type de notification pour les logs
            
        Returns:
            bool: True si envoyé avec succès, False sinon
        """
        if not self.is_available():
            self.logger.error("Service de notifications non disponible")
            return False
        
        try:
            # Préparer le payload de la notification
            payload = {
                "title": title,
                "body": message,
                "icon": "/static/icons/icon-192x192.png",
                "badge": "/static/icons/badge-72x72.png",
                "data": data or {},
                "timestamp": int(datetime.now().timestamp() * 1000),
                "requireInteraction": notification_type in ['event_reminder'],  # Notifications importantes
                "actions": [
                    {
                        "action": "view",
                        "title": "Voir",
                        "icon": "/static/icons/view.png"
                    },
                    {
                        "action": "dismiss",
                        "title": "Fermer",
                        "icon": "/static/icons/close.png"
                    }
                ]
            }
            
            # Envoyer la notification
            response = webpush(
                subscription_info=subscription.to_dict(),
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
                timeout=10
            )
            
            # Logger le succès
            self._log_notification(
                subscription.user_id,
                notification_type,
                title,
                message,
                subscription.endpoint,
                success=True,
                response_code=response.status_code
            )
            
            self.logger.info(f"✅ Notification envoyée à l'utilisateur {subscription.user_id}")
            return True
            
        except WebPushException as e:
            # Gérer les erreurs spécifiques à WebPush
            error_msg = str(e)
            response_code = getattr(e, 'response', {}).get('status_code', 0)
            
            # Si l'abonnement est expiré ou invalide, le désactiver
            if response_code in [400, 404, 410, 413]:
                self.logger.warning(f"Abonnement {subscription.id} invalide, désactivation")
                subscription.is_active = False
                db.session.commit()
            
            self._log_notification(
                subscription.user_id,
                notification_type,
                title,
                message,
                subscription.endpoint,
                success=False,
                error_message=error_msg,
                response_code=response_code
            )
            
            self.logger.error(f"❌ Erreur WebPush pour utilisateur {subscription.user_id}: {error_msg}")
            return False
            
        except Exception as e:
            # Autres erreurs
            self._log_notification(
                subscription.user_id,
                notification_type,
                title,
                message,
                subscription.endpoint,
                success=False,
                error_message=str(e)
            )
            
            self.logger.error(f"❌ Erreur envoi notification à {subscription.user_id}: {str(e)}")
            return False
    
    def send_event_reminder(self, event, minutes_before: int) -> Dict[str, int]:
        """
        Envoie un rappel d'événement à tous les utilisateurs éligibles.
        
        Args:
            event: L'événement du programme (objet NotificationEvent)
            minutes_before: Nombre de minutes avant l'événement
            
        Returns:
            Dict avec compteurs de succès/échecs
        """
        if not self.is_available():
            return {"sent": 0, "failed": 1, "skipped": 0}
        
        results = {"sent": 0, "failed": 0, "skipped": 0}
        
        try:
            # Import local pour éviter les imports circulaires
            from app.models_notifications import PushSubscription
            from app.models import User
            
            # Récupérer tous les abonnements actifs d'utilisateurs qui acceptent ce type de notification
            eligible_subscriptions = db.session.query(PushSubscription).join(User).filter(
                PushSubscription.is_active == True,
                User.enable_push_notifications == True,
                User.enable_event_reminders == True
            ).all()
            
            # Préparer le message
            if minutes_before > 0:
                title = f"📅 Dans {minutes_before} min : {event.title}"
            else:
                title = f"🔔 Début maintenant : {event.title}"
            
            message_parts = []
            if event.location:
                message_parts.append(f"📍 {event.location}")
            if event.description:
                message_parts.append(event.description[:100] + "..." if len(event.description) > 100 else event.description)
            
            message = " | ".join(message_parts) if message_parts else "Consultez le programme pour plus d'infos"
            
            # Données additionnelles
            data = {
                "type": "event_reminder",
                "event_id": event.event_id,
                "url": f"/conference/programme#{event.event_id}",
                "minutes_before": minutes_before
            }
            
            # Envoyer à tous les abonnements éligibles
            for subscription in eligible_subscriptions:
                try:
                    success = self.send_push_notification(
                        subscription=subscription,
                        title=title,
                        message=message,
                        data=data,
                        notification_type='event_reminder'
                    )
                    
                    if success:
                        results["sent"] += 1
                    else:
                        results["failed"] += 1
                        
                except Exception as e:
                    self.logger.error(f"Erreur envoi rappel événement à {subscription.user_id}: {e}")
                    results["failed"] += 1
            
            self.logger.info(f"📊 Rappel événement '{event.title}': {results['sent']} envoyés, {results['failed']} échecs")
            
        except Exception as e:
            self.logger.error(f"Erreur envoi rappel événement: {e}")
            results["failed"] += 1
        
        return results
    
    def send_admin_broadcast(self, notification) -> Dict[str, int]:
        """
        Envoie une notification manuelle de l'admin à tous les utilisateurs ciblés.
        
        Args:
            notification: La notification admin à envoyer (objet AdminNotification)
            
        Returns:
            Dict avec compteurs de succès/échecs
        """
        if not self.is_available():
            return {"sent": 0, "failed": 1, "skipped": 0}
        
        results = {"sent": 0, "failed": 0, "skipped": 0}
        
        try:
            # Import local pour éviter les imports circulaires
            from app.models_notifications import PushSubscription
            from app.models import User
            
            # Construire la requête selon les cibles
            query = db.session.query(PushSubscription).join(User).filter(
                PushSubscription.is_active == True,
                User.enable_push_notifications == True,
                User.enable_admin_broadcasts == True
            )
            
            if not notification.target_all_users:
                # Filtrage par rôle si pas tous les utilisateurs
                conditions = []
                if notification.target_reviewers:
                    conditions.append(User.is_reviewer == True)
                if notification.target_authors:
                    conditions.append(User.communications.any())  # A au moins une communication
                
                if conditions:
                    from sqlalchemy import or_
                    query = query.filter(or_(*conditions))
            
            eligible_subscriptions = query.all()
            
            # Préparer le message
            title = f"🔔 {notification.title}"
            message = notification.message
            
            data = {
                "type": "admin_broadcast",
                "notification_id": notification.id,
                "url": "/"
            }
            
            # Envoyer à tous les abonnements éligibles
            for subscription in eligible_subscriptions:
                try:
                    success = self.send_push_notification(
                        subscription=subscription,
                        title=title,
                        message=message,
                        data=data,
                        notification_type='admin_broadcast'
                    )
                    
                    if success:
                        results["sent"] += 1
                    else:
                        results["failed"] += 1
                        
                except Exception as e:
                    self.logger.error(f"Erreur envoi broadcast admin à {subscription.user_id}: {e}")
                    results["failed"] += 1
            
            # Mettre à jour les statistiques de la notification
            notification.sent_at = datetime.utcnow()
            notification.total_sent = results["sent"]
            notification.total_failed = results["failed"]
            db.session.commit()
            
            self.logger.info(f"📢 Broadcast admin '{notification.title}': {results['sent']} envoyés, {results['failed']} échecs")
            
        except Exception as e:
            self.logger.error(f"Erreur envoi broadcast admin: {e}")
            results["failed"] += 1
        
        return results
    
    def _log_notification(self, user_id: Optional[int], notification_type: str,
                         title: str, message: str, endpoint: str,
                         success: bool, error_message: str = None,
                         response_code: int = None):
        """Log une notification dans la base de données."""
        try:
            # Import local pour éviter les imports circulaires
            from app.models_notifications import NotificationLog
            
            log_entry = NotificationLog(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                endpoint=endpoint,
                success=success,
                error_message=error_message,
                response_code=response_code
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            # Ne pas faire planter le système si le logging échoue
            self.logger.error(f"Erreur logging notification: {e}")

# Instance globale du service (sans initialisation immédiate)
notification_service = NotificationService()

