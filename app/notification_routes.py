from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models_notifications import PushSubscription, NotificationEvent, AdminNotification, NotificationLog
from app.services.notification_service import notification_service
from datetime import datetime, timedelta
import json
import logging

# Créer le blueprint pour les notifications
notifications_api = Blueprint('notifications_api', __name__, url_prefix='/api')

@notifications_api.route('/vapid-public-key', methods=['GET'])
def get_vapid_public_key():
    """Retourne la clé publique VAPID pour les abonnements push."""
    try:
        public_key = current_app.config.get('VAPID_PUBLIC_KEY')
        
        if not public_key or public_key in ['VAPID_KEYS_NOT_GENERATED', 'NOTIFICATIONS_DISABLED']:
            return jsonify({
                'error': 'Notifications push non configurées',
                'publicKey': None
            }), 503
        
        return jsonify({
            'publicKey': public_key,
            'subject': current_app.config.get('VAPID_SUBJECT', 'mailto:admin@conference-flow.com')
        })
    
    except Exception as e:
        current_app.logger.error(f"Erreur récupération clé VAPID: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500

@notifications_api.route('/push-subscription', methods=['POST'])
@login_required
def save_push_subscription():
    """Sauvegarde ou met à jour l'abonnement aux notifications push d'un utilisateur."""
    try:
        data = request.get_json()
        
        if not data or 'subscription' not in data:
            return jsonify({'error': 'Données d\'abonnement manquantes'}), 400
        
        subscription_data = data['subscription']
        user_agent = data.get('userAgent', '')
        preferences = data.get('preferences', {})
        
        # Vérifier les données de l'abonnement
        required_fields = ['endpoint', 'keys']
        if not all(field in subscription_data for field in required_fields):
            return jsonify({'error': 'Format d\'abonnement invalide'}), 400
        
        keys = subscription_data['keys']
        if 'p256dh' not in keys or 'auth' not in keys:
            return jsonify({'error': 'Clés d\'abonnement manquantes'}), 400
        
        # Chercher un abonnement existant pour cet endpoint
        existing_subscription = PushSubscription.query.filter_by(
            endpoint=subscription_data['endpoint']
        ).first()
        
        if existing_subscription:
            # Mettre à jour l'abonnement existant
            existing_subscription.user_id = current_user.id
            existing_subscription.p256dh = keys['p256dh']
            existing_subscription.auth = keys['auth']
            existing_subscription.user_agent = user_agent
            existing_subscription.is_active = True
            
            current_app.logger.info(f"Abonnement push mis à jour pour utilisateur {current_user.id}")
        else:
            # Créer un nouvel abonnement
            new_subscription = PushSubscription(
                user_id=current_user.id,
                endpoint=subscription_data['endpoint'],
                p256dh=keys['p256dh'],
                auth=keys['auth'],
                user_agent=user_agent,
                is_active=True
            )
            db.session.add(new_subscription)
            
            current_app.logger.info(f"Nouvel abonnement push créé pour utilisateur {current_user.id}")
        
        # Mettre à jour les préférences de l'utilisateur
        if preferences:
            current_user.enable_event_reminders = preferences.get('eventReminders', True)
            current_user.enable_session_reminders = preferences.get('sessionReminders', True)
            current_user.enable_admin_broadcasts = preferences.get('adminBroadcasts', True)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Abonnement sauvegardé avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur sauvegarde abonnement push: {e}")
        return jsonify({'error': 'Erreur lors de la sauvegarde'}), 500

@notifications_api.route('/push-subscription', methods=['DELETE'])
@login_required
def delete_push_subscription():
    """Supprime l'abonnement aux notifications push d'un utilisateur."""
    try:
        data = request.get_json()
        endpoint = data.get('endpoint') if data else None
        
        if endpoint:
            # Supprimer un abonnement spécifique
            subscription = PushSubscription.query.filter_by(
                user_id=current_user.id,
                endpoint=endpoint
            ).first()
            
            if subscription:
                db.session.delete(subscription)
                message = "Abonnement spécifique supprimé"
            else:
                return jsonify({'error': 'Abonnement non trouvé'}), 404
        else:
            # Supprimer tous les abonnements de l'utilisateur
            PushSubscription.query.filter_by(user_id=current_user.id).delete()
            message = "Tous les abonnements supprimés"
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': message
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression abonnement push: {e}")
        return jsonify({'error': 'Erreur lors de la suppression'}), 500

@notifications_api.route('/program-events', methods=['GET'])
def get_program_events():
    """Retourne les événements du programme pour synchronisation PWA."""
    try:
        # Importer ici pour éviter les imports circulaires
        from app.conference_routes import load_programme_csv_common
        
        # Charger le programme depuis le CSV
        programme_data = load_programme_csv_common()
        
        if not programme_data:
            return jsonify([])
        
        events = []
        
        for day_key, day_info in programme_data.items():
            date_str = day_info.get('date', '')
            sessions = day_info.get('sessions', [])
            
            for session in sessions:
                # Convertir chaque session en événement
                event = {
                    'id': f"{day_key}_{len(events)}",  # ID unique
                    'title': session.get('title', ''),
                    'description': session.get('description', ''),
                    'location': session.get('location', ''),
                    'time': session.get('time', ''),
                    'date': date_str,
                    'type': session.get('type', 'session'),
                    'speaker': session.get('speaker', ''),
                    'sessions': session.get('sessions', []),  # Sessions parallèles
                    'ateliers': session.get('ateliers', [])  # Ateliers
                }
                
                # Calculer les timestamps pour les rappels
                try:
                    start_time = parse_session_datetime(date_str, session.get('time', ''))
                    if start_time:
                        event['start_timestamp'] = int(start_time.timestamp())
                        event['reminder_3min'] = int((start_time - timedelta(minutes=3)).timestamp())
                        event['reminder_15min'] = int((start_time - timedelta(minutes=15)).timestamp())
                except Exception as e:
                    current_app.logger.warning(f"Erreur parsing date/heure pour {session.get('title', '')}: {e}")
                
                events.append(event)
        
        return jsonify(events)
    
    except Exception as e:
        current_app.logger.error(f"Erreur récupération événements programme: {e}")
        return jsonify({'error': 'Erreur lors de la récupération des événements'}), 500

@notifications_api.route('/notification-preferences', methods=['GET'])
@login_required
def get_notification_preferences():
    """Retourne les préférences de notification de l'utilisateur."""
    try:
        preferences = {
            'eventReminders': current_user.enable_event_reminders,
            'sessionReminders': current_user.enable_session_reminders,
            'adminBroadcasts': current_user.enable_admin_broadcasts,
            'pushEnabled': current_user.enable_push_notifications,
            'hasActiveSubscription': current_user.has_active_push_subscription()
        }
        
        return jsonify(preferences)
    
    except Exception as e:
        current_app.logger.error(f"Erreur récupération préférences: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500

@notifications_api.route('/notification-preferences', methods=['POST'])
@login_required
def update_notification_preferences():
    """Met à jour les préférences de notification de l'utilisateur."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Données manquantes'}), 400
        
        # Mettre à jour les préférences
        if 'eventReminders' in data:
            current_user.enable_event_reminders = bool(data['eventReminders'])
        
        if 'sessionReminders' in data:
            current_user.enable_session_reminders = bool(data['sessionReminders'])
        
        if 'adminBroadcasts' in data:
            current_user.enable_admin_broadcasts = bool(data['adminBroadcasts'])
        
        if 'pushEnabled' in data:
            current_user.enable_push_notifications = bool(data['pushEnabled'])
            
            # Si désactivé, désactiver tous les abonnements
            if not current_user.enable_push_notifications:
                PushSubscription.query.filter_by(
                    user_id=current_user.id
                ).update({'is_active': False})
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Préférences mises à jour'
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur mise à jour préférences: {e}")
        return jsonify({'error': 'Erreur lors de la mise à jour'}), 500

@notifications_api.route('/test-notification', methods=['POST'])
@login_required
def send_test_notification():
    """Envoie une notification de test à l'utilisateur connecté."""
    try:
        if not current_user.has_active_push_subscription():
            return jsonify({
                'error': 'Aucun abonnement push actif trouvé'
            }), 400
        
        # Récupérer tous les abonnements actifs de l'utilisateur
        subscriptions = current_user.get_active_push_subscriptions()
        
        sent_count = 0
        failed_count = 0
        
        for subscription in subscriptions:
            try:
                success = notification_service.send_push_notification(
                    subscription=subscription,
                    title="🧪 Test Conference Flow",
                    message="Si vous voyez ceci, les notifications fonctionnent parfaitement !",
                    data={
                        'type': 'test',
                        'url': '/profile'
                    },
                    notification_type='test'
                )
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                current_app.logger.error(f"Erreur envoi test notification: {e}")
                failed_count += 1
        
        if sent_count > 0:
            return jsonify({
                'success': True,
                'message': f'Notification de test envoyée à {sent_count} abonnement(s)',
                'sent': sent_count,
                'failed': failed_count
            })
        else:
            return jsonify({
                'error': f'Échec envoi notification de test ({failed_count} échecs)',
                'sent': sent_count,
                'failed': failed_count
            }), 500
    
    except Exception as e:
        current_app.logger.error(f"Erreur test notification: {e}")
        return jsonify({'error': 'Erreur lors du test'}), 500

@notifications_api.route('/notification-stats', methods=['GET'])
@login_required
def get_notification_stats():
    """Retourne les statistiques de notifications pour l'utilisateur (admin uniquement)."""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Accès refusé'}), 403
        
        # Statistiques globales
        total_subscriptions = PushSubscription.query.filter_by(is_active=True).count()
        total_users_with_notifications = db.session.query(PushSubscription.user_id).filter_by(is_active=True).distinct().count()
        
        # Statistiques des logs (dernière semaine)
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        recent_logs = NotificationLog.query.filter(
            NotificationLog.sent_at >= one_week_ago
        ).all()
        
        successful_notifications = len([log for log in recent_logs if log.success])
        failed_notifications = len([log for log in recent_logs if not log.success])
        
        # Statistiques par type
        notification_types = {}
        for log in recent_logs:
            notification_type = log.notification_type or 'unknown'
            if notification_type not in notification_types:
                notification_types[notification_type] = {'sent': 0, 'failed': 0}
            
            if log.success:
                notification_types[notification_type]['sent'] += 1
            else:
                notification_types[notification_type]['failed'] += 1
        
        stats = {
            'totalActiveSubscriptions': total_subscriptions,
            'totalUsersWithNotifications': total_users_with_notifications,
            'lastWeekStats': {
                'successful': successful_notifications,
                'failed': failed_notifications,
                'total': len(recent_logs)
            },
            'notificationTypeStats': notification_types,
            'vapidConfigured': bool(current_app.config.get('VAPID_PRIVATE_KEY') and 
                                  current_app.config.get('VAPID_PRIVATE_KEY') not in ['VAPID_KEYS_NOT_GENERATED', 'NOTIFICATIONS_DISABLED'])
        }
        
        return jsonify(stats)
    
    except Exception as e:
        current_app.logger.error(f"Erreur statistiques notifications: {e}")
        return jsonify({'error': 'Erreur lors de la récupération des statistiques'}), 500

# Fonction utilitaire pour parser les dates/heures des sessions
def parse_session_datetime(date_str, time_str):
    """Parse une date et heure de session depuis le format du CSV."""
    if not date_str or not time_str:
        return None
    
    try:
        import re
        from datetime import datetime
        
        # Extraire l'heure de début (format: "13h00-14h00" ou "13h00")
        time_match = re.search(r'(\d{1,2})h(\d{2})', time_str)
        if not time_match:
            return None
            
        start_hour = int(time_match.group(1))
        start_min = int(time_match.group(2))
        
        # Parser la date au format "Mardi 1 juillet 2025"
        date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_str)
        if date_match:
            day = int(date_match.group(1))
            month_name = date_match.group(2).lower()
            year = int(date_match.group(3))
            
            # Conversion nom de mois français -> numéro
            mois_fr = {
                'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
                'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8,
                'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
            }
            
            month = mois_fr.get(month_name)
            if not month:
                return None
            
            # Créer l'objet datetime
            return datetime(year, month, day, start_hour, start_min)
        
        return None
        
    except Exception as e:
        current_app.logger.error(f"Erreur parsing date {date_str} {time_str}: {e}")
        return None
