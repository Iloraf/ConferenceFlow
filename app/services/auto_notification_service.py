"""
Conference Flow - Système de gestion de conférence scientifique
Copyright (C) 2025 Olivier Farges olivier@olivier-farges.xyz

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import csv
import hashlib
from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models import PushSubscription, NotificationEvent, NotificationLog
import threading
import time
import schedule
import logging
import re

class AutoNotificationService:
    """Service pour gérer les notifications automatiques d'événements."""
    
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.logger = logging.getLogger(__name__)
        self.app = current_app
        
    def start_notification_scheduler(self):
        """Démarre le service de notifications automatiques."""
        if self.is_running:
            self.logger.info("⚠️ Service auto-notifications déjà en cours")
            return
        
        self.is_running = True
        
        # Programmer les tâches
        schedule.every(10).minutes.do(self.sync_events_from_program)
        schedule.every(1).minutes.do(self.check_and_send_reminders)
        
        # Synchronisation initiale
        self.sync_events_from_program()
        
        # Démarrer le thread de surveillance
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        
        self.logger.info("✅ Service auto-notifications démarré")
    
    def stop_notification_scheduler(self):
        """Arrête le service de notifications automatiques."""
        self.is_running = False
        schedule.clear()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        self.logger.info("🛑 Service auto-notifications arrêté")
    
    def _run_scheduler(self):
        """Boucle principale du planificateur."""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(30)  # Vérifier toutes les 30 secondes
            except Exception as e:
                self.logger.error(f"Erreur dans le planificateur: {e}")
                time.sleep(60)  # Attendre plus longtemps en cas d'erreur
    
    def sync_events_from_program(self):
        """Synchronise les événements depuis le fichier programme CSV."""
        try:
            program_file = self._find_program_file()
            if not program_file:
                self.logger.warning("Fichier programme non trouvé pour synchronisation")
                return
            
            self.logger.info(f"🔍 Lecture du fichier: {program_file}")
            events = self._parse_program_csv(program_file)
            self.logger.info(f"📝 {len(events)} événements parsés depuis le CSV")
            
            self._update_notification_events(events)
            
            self.logger.info(f"✅ Synchronisation terminée: {len(events)} événements traités")
            
        except Exception as e:
            self.logger.error(f"Erreur synchronisation programme: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _find_program_file(self):
        """Trouve le fichier programme CSV de Conference Flow."""
        # Utiliser le même chemin que dans conference_routes.py
        csv_path = os.path.join(current_app.root_path, 'static', 'content', 'programme.csv')
        
        if os.path.exists(csv_path):
            return csv_path
        else:
            self.logger.warning(f"Fichier programme.csv non trouvé à: {csv_path}")
            return None

    
    def _parse_program_csv(self, file_path):
        """Parse le fichier CSV du programme de Conference Flow."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                # Utiliser le même délimiteur que dans votre projet (';')
                reader = csv.DictReader(csvfile, delimiter=';')
                
                row_count = 0
                for row in reader:
                    row_count += 1
                    
                    # Nettoyer les données comme dans conference_routes.py
                    cleaned_row = {}
                    for k, v in row.items():
                        clean_k = k.strip() if k else ''
                        clean_v = v.strip() if v else ''
                        cleaned_row[clean_k] = clean_v
                    
                    
                    event = self._parse_csv_row(cleaned_row)
                    if event:
                        events.append(event)
                    else:
                        if row_count <= 3:
                            self.logger.info(f"❌ Ligne ignorée (données manquantes ou erreur)")
                
                self.logger.info(f"📊 Total lignes lues: {row_count}, événements créés: {len(events)}")
                        
        except Exception as e:
            self.logger.error(f"Erreur lecture programme.csv: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        return events
    
    def _parse_csv_row(self, row):
        """Parse une ligne du CSV en événement selon le format Conference Flow."""
        try:
            # Récupérer les colonnes nécessaires avec gestion flexible
            title = self._get_csv_value(row, ['session', 'titre', 'title', 'nom'])
            description = self._get_csv_value(row, ['titre', 'description', 'desc', 'resume'])
            location = self._get_csv_value(row, ['lieu', 'location', 'salle', 'place'])
            date_str = self._get_csv_value(row, ['date', 'jour', 'day'])
            time_str = self._get_csv_value(row, ['horaire', 'heure', 'time'])
            event_type = self._get_csv_value(row, ['type', 'category'], default='session')
            intervenant = self._get_csv_value(row, ['intervenant', 'speaker', 'conferencier'])
            
            
            # Vérification des champs obligatoires
            if not all([title, date_str, time_str]):
                self.logger.debug(f"❌ Ligne ignorée: titre='{title}', date='{date_str}', heure='{time_str}'")
                return None
            
            # Parser la date/heure
            start_datetime = self._parse_datetime(date_str, time_str)
            if not start_datetime:
                self.logger.warning(f"❌ Impossible de parser la date/heure: '{date_str}' '{time_str}'")
                return None
            
            # Générer un ID unique
            event_id = self._generate_event_id(date_str, time_str, title)
            
            # Enrichir le titre avec l'intervenant
            full_title = title
            if intervenant:
                full_title += f" - {intervenant}"
            
            # Enrichir la description avec les sessions parallèles
            full_description = description
            sessions = [self._get_csv_value(row, [f'session{i}']) for i in range(1, 5)]
            sessions = [s for s in sessions if s]
            if sessions:
                if full_description:
                    full_description += "\n\n"
                full_description += f"Sessions parallèles: {', '.join(sessions)}"
            
            return {
                'event_id': event_id,
                'title': full_title,
                'description': full_description,
                'location': location,
                'start_time': start_datetime,
                'event_type': event_type
                # Retirer source_checksum car le modèle ne l'a pas
            }
            
        except Exception as e:
            self.logger.error(f"Erreur parsing ligne CSV: {e}, row: {row}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _get_csv_value(self, row, possible_keys, default=''):
        """Récupère une valeur du CSV en testant plusieurs clés possibles."""
        for key in possible_keys:
            value = row.get(key, '').strip()
            if value:
                return value
        return default
    
    def _parse_datetime(self, date_str, horaire):
        """Parse la date et l'heure du programme."""
        try:
            # Extraire l'heure de début (format "9h00-10h30" ou "9h00")
            time_match = re.match(r'(\d{1,2})h(\d{2})', horaire.split('-')[0])
            if not time_match:
                return None
            
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            
            # Extraire la date (format "Mardi 2 juin 2026")
            date_parts = date_str.split()
            if len(date_parts) < 4:
                return None
            
            day = int(date_parts[1])
            month_name = date_parts[2].lower()
            year = int(date_parts[3])
            
            # Mapping des mois français
            months = {
                'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
                'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
            }
            
            month = months.get(month_name, 6)  # Default to juin
            
            return datetime(year, month, day, hour, minute)
            
        except Exception as e:
            self.logger.error(f"Erreur parsing datetime '{date_str} {horaire}': {e}")
            return None
    
    def _generate_event_id(self, date_str, time_str, title):
        """Génère un ID unique pour l'événement."""
        combined = f"{date_str}_{time_str}_{title}".encode('utf-8')
        return hashlib.md5(combined).hexdigest()[:16]
    
    def _calculate_row_checksum(self, row):
        """Calcule un checksum pour détecter les modifications - désactivé car pas de colonne en base."""
        # Cette méthode reste pour compatibilité mais ne sert plus 
        # car le modèle n'a pas de colonne source_checksum
        return None
    
    def _update_notification_events(self, parsed_events):
        """Met à jour les événements de notification en base."""
        try:
            for event_data in parsed_events:
                existing = NotificationEvent.query.filter_by(
                    event_id=event_data['event_id']
                ).first()
                
                if existing:
                    # Mettre à jour l'événement existant
                    existing.title = event_data['title']
                    existing.description = event_data['description']
                    existing.location = event_data['location']
                    existing.start_time = event_data['start_time']
                    existing.event_type = event_data['event_type']
                    existing.updated_at = datetime.utcnow()
                    
                else:
                    # Créer un nouvel événement - adapter aux colonnes réelles du modèle
                    new_event = NotificationEvent(
                        event_id=event_data['event_id'],
                        title=event_data['title'],
                        description=event_data['description'],
                        location=event_data['location'],
                        start_time=event_data['start_time'],
                        event_type=event_data['event_type']
                        # Retirer source_checksum car il n'existe pas dans le modèle
                    )
                    db.session.add(new_event)
                    
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erreur mise à jour événements: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    def check_and_send_reminders(self):
        """Vérifie et envoie les rappels de notifications."""
        try:
            now = datetime.utcnow()
            
            # Récupérer les événements nécessitant des notifications
            events_needing_15min = NotificationEvent.query.filter(
                NotificationEvent.notification_15min_sent == False,
                NotificationEvent.start_time > now,
                NotificationEvent.start_time <= now + timedelta(minutes=15)
            ).all()
            
            events_needing_3min = NotificationEvent.query.filter(
                NotificationEvent.notification_3min_sent == False,
                NotificationEvent.start_time > now,
                NotificationEvent.start_time <= now + timedelta(minutes=3)
            ).all()
            
            # Envoyer les notifications 15 minutes
            for event in events_needing_15min:
                self._send_event_reminder(event, 15)
                event.notification_15min_sent = True
            
            # Envoyer les notifications 3 minutes
            for event in events_needing_3min:
                self._send_event_reminder(event, 3)
                event.notification_3min_sent = True
            
            if events_needing_15min or events_needing_3min:
                db.session.commit()
                total_sent = len(events_needing_15min) + len(events_needing_3min)
                self.logger.info(f"📱 {total_sent} notification(s) de rappel envoyée(s)")
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erreur envoi rappels: {e}")
    
    def _send_event_reminder(self, event, minutes_before):
        """Envoie un rappel pour un événement."""
        try:
            # Importer le service de notifications
            from app.services.notification_service import notification_service
            
            if not notification_service or not hasattr(notification_service, 'is_available') or not notification_service.is_available():
                self.logger.warning("Service de notifications non disponible")
                return
            
            # Construire le message
            if minutes_before >= 15:
                title = f"📅 Dans {minutes_before} minutes"
                icon = "⏰"
            else:
                title = f"🚨 Dans {minutes_before} minutes"
                icon = "🔔"
            
            message = f"{event.title}"
            if event.location:
                message += f"\n📍 {event.location}"
            
            # Récupérer tous les utilisateurs avec notifications activées
            active_subscriptions = PushSubscription.query.join(
                PushSubscription.user
            ).filter(
                PushSubscription.is_active == True,
                # Vérifier que l'utilisateur a activé les notifications d'événements
                # (cette vérification peut être adaptée selon votre modèle User)
            ).all()
            
            sent_count = 0
            failed_count = 0
            
            for subscription in active_subscriptions:
                try:
                    # Vérifier les préférences de l'utilisateur
                    user = subscription.user
                    if not getattr(user, 'enable_event_reminders', True):
                        continue
                    
                    success = notification_service.send_notification_to_user(
                        subscription=subscription,
                        title=title,
                        message=message,
                        data={
                            'type': 'event_reminder',
                            'event_id': event.event_id,
                            'minutes_before': minutes_before,
                            'url': '/programme'
                        },
                        notification_type='event_reminder'
                    )
                    
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Erreur envoi notification à {subscription.id}: {e}")
                    failed_count += 1
            
            self.logger.info(f"📱 Rappel {minutes_before}min pour '{event.title}': {sent_count} envoyés, {failed_count} échecs")
            
        except Exception as e:
            self.logger.error(f"Erreur rappel événement: {e}")
    
    def get_upcoming_events(self, limit=20):
        """Récupère les prochains événements."""
        try:
            now = datetime.utcnow()
            events = NotificationEvent.query.filter(
                NotificationEvent.start_time > now
            ).order_by(NotificationEvent.start_time).limit(limit).all()
            
            return events
            
        except Exception as e:
            self.logger.error(f"Erreur récupération événements à venir: {e}")
            return []
    
    def get_past_events(self, limit=10):
        """Récupère les événements passés."""
        try:
            now = datetime.utcnow()
            events = NotificationEvent.query.filter(
                NotificationEvent.start_time <= now
            ).order_by(NotificationEvent.start_time.desc()).limit(limit).all()
            
            return events
            
        except Exception as e:
            self.logger.error(f"Erreur récupération événements passés: {e}")
            return []
    
    def get_stats(self):
        """Retourne les statistiques du service."""
        try:
            now = datetime.utcnow()
            
            total_events = NotificationEvent.query.count()
            future_events = NotificationEvent.query.filter(
                NotificationEvent.start_time > now
            ).count()
            past_events = total_events - future_events
            
            notifications_15min = NotificationEvent.query.filter(
                NotificationEvent.notification_15min_sent == True
            ).count()
            notifications_3min = NotificationEvent.query.filter(
                NotificationEvent.notification_3min_sent == True
            ).count()
            
            next_event = NotificationEvent.query.filter(
                NotificationEvent.start_time > now
            ).order_by(NotificationEvent.start_time).first()
            
            return {
                'service_running': self.is_running,
                'total_events': total_events,
                'future_events': future_events,
                'past_events': past_events,
                'notifications_sent': {
                    '15min': notifications_15min,
                    '3min': notifications_3min
                },
                'next_event': next_event
            }
            
        except Exception as e:
            self.logger.error(f"Erreur récupération stats: {e}")
            return {
                'service_running': self.is_running,
                'total_events': 0,
                'future_events': 0,
                'past_events': 0,
                'notifications_sent': {'15min': 0, '3min': 0},
                'next_event': None
            }
    
    def create_test_event(self, title, minutes_from_now=16):
        """Crée un événement de test pour vérifier les notifications."""
        try:
            start_time = datetime.utcnow() + timedelta(minutes=minutes_from_now)
            
            test_event = NotificationEvent(
                event_id=f"test_{int(time.time())}",
                title=title,
                description="Événement de test pour vérifier les notifications automatiques",
                location="Salle de test",
                start_time=start_time,
                event_type="test"
                # Retirer source_checksum
            )
            
            db.session.add(test_event)
            db.session.commit()
            
            self.logger.info(f"✅ Événement de test créé: {title} à {start_time}")
            return test_event
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erreur création événement test: {e}")
    
    def create_manual_event(self, title, start_time, location='', description=''):
        """Crée un événement manuel."""
        try:
            event_id = self._generate_event_id(
                start_time.strftime('%Y-%m-%d'), 
                start_time.strftime('%H:%M'), 
                title
            )
            
            manual_event = NotificationEvent(
                event_id=event_id,
                title=title,
                description=description,
                location=location,
                start_time=start_time,
                event_type="manual",
                source_checksum="manual_event"
            )
            
            db.session.add(manual_event)
            db.session.commit()
            
            self.logger.info(f"✅ Événement manuel créé: {title}")
            return manual_event
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erreur création événement manuel: {e}")
            return None


# Instance globale du service
auto_notification_service = AutoNotificationService()


