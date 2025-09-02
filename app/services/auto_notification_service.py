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
from app.models_notifications import NotificationEvent, PushSubscription, NotificationLog
from app.models import User
from app.services.notification_service import notification_service
import threading
import time
import schedule

class AutoNotificationService:
    """Service pour gérer les notifications automatiques d'événements."""
    
    def __init__(self):
        self.is_running = False
        self.notification_thread = None
    
    def start_notification_scheduler(self):
        """Démarre le planificateur de notifications."""
        if self.is_running:
            return
            
        self.is_running = True
        
        # Programmer les vérifications
        schedule.every().minute.do(self.check_and_send_notifications)
        schedule.every(10).minutes.do(self.sync_events_from_program)
        
        # Lancer dans un thread séparé
        self.notification_thread = threading.Thread(
            target=self._run_scheduler, 
            daemon=True
        )
        self.notification_thread.start()
        
        current_app.logger.info("🔔 Service de notifications automatiques démarré")
    
    def stop_notification_scheduler(self):
        """Arrête le planificateur."""
        self.is_running = False
        schedule.clear()
        current_app.logger.info("🔕 Service de notifications automatiques arrêté")
    
    def _run_scheduler(self):
        """Boucle principale du planificateur."""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(30)  # Vérifier toutes les 30 secondes
            except Exception as e:
                current_app.logger.error(f"Erreur dans le planificateur: {e}")
                time.sleep(60)  # Attendre plus longtemps en cas d'erreur
    
    def sync_events_from_program(self):
        """Synchronise les événements depuis le fichier programme CSV."""
        try:
            program_file = self._find_program_file()
            if not program_file:
                current_app.logger.warning("Fichier programme non trouvé pour synchronisation")
                return
            
            events = self._parse_program_csv(program_file)
            self._update_notification_events(events)
            
            current_app.logger.info(f"✅ Synchronisation: {len(events)} événements traités")
            
        except Exception as e:
            current_app.logger.error(f"Erreur synchronisation programme: {e}")
    
    def _find_program_file(self):
        """Trouve le fichier programme CSV."""
        possible_paths = [
            'app/static/content/programme.csv',
            'app/static/content/program.csv',
            'programme.csv',
            'program.csv'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    def _parse_program_csv(self, file_path):
        """Parse le fichier CSV du programme."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                
                for row in reader:
                    event = self._parse_csv_row(row)
                    if event:
                        events.append(event)
                        
        except Exception as e:
            current_app.logger.error(f"Erreur lecture CSV: {e}")
        
        return events
    
    def _parse_csv_row(self, row):
        """Parse une ligne du CSV en événement."""
        try:
            # Adapter selon votre format CSV
            title = row.get('titre') or row.get('title') or row.get('session')
            date_str = row.get('date') or row.get('jour')
            time_str = row.get('heure') or row.get('time') or row.get('horaire')
            location = row.get('lieu') or row.get('location') or row.get('salle')
            description = row.get('description') or row.get('resume')
            
            if not title or not date_str or not time_str:
                return None
            
            # Parser la date et l'heure
            start_time = self._parse_datetime(date_str, time_str)
            if not start_time:
                return None
            
            # Générer un ID unique
            event_id = self._generate_event_id(title, start_time)
            
            return {
                'event_id': event_id,
                'title': title,
                'description': description or '',
                'location': location or '',
                'start_time': start_time,
                'event_type': row.get('type') or 'session'
            }
            
        except Exception as e:
            current_app.logger.warning(f"Erreur parsing ligne CSV: {e}")
            return None
    
    def _parse_datetime(self, date_str, time_str):
        """Parse une date et heure depuis le CSV."""
        try:
            # Essayer différents formats
            date_formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']
            time_formats = ['%H:%M', '%H:%M:%S', '%H.%M']
            
            for date_fmt in date_formats:
                try:
                    date_obj = datetime.strptime(date_str.strip(), date_fmt).date()
                    break
                except ValueError:
                    continue
            else:
                return None
            
            for time_fmt in time_formats:
                try:
                    time_obj = datetime.strptime(time_str.strip(), time_fmt).time()
                    break
                except ValueError:
                    continue
            else:
                return None
            
            return datetime.combine(date_obj, time_obj)
            
        except Exception as e:
            current_app.logger.warning(f"Erreur parsing date/heure '{date_str}' '{time_str}': {e}")
            return None
    
    def _generate_event_id(self, title, start_time):
        """Génère un ID unique pour l'événement."""
        content = f"{title}_{start_time.isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _update_notification_events(self, events_data):
        """Met à jour les événements en base de données."""
        for event_data in events_data:
            existing_event = NotificationEvent.query.filter_by(
                event_id=event_data['event_id']
            ).first()
            
            if existing_event:
                # Mettre à jour si nécessaire
                existing_event.title = event_data['title']
                existing_event.description = event_data['description']
                existing_event.location = event_data['location']
                existing_event.start_time = event_data['start_time']
                existing_event.event_type = event_data['event_type']
                existing_event.updated_at = datetime.utcnow()
            else:
                # Créer nouvel événement
                new_event = NotificationEvent(
                    event_id=event_data['event_id'],
                    title=event_data['title'],
                    description=event_data['description'],
                    location=event_data['location'],
                    start_time=event_data['start_time'],
                    event_type=event_data['event_type']
                )
                db.session.add(new_event)
        
        db.session.commit()
    
    def check_and_send_notifications(self):
        """Vérifie et envoie les notifications pour les événements à venir."""
        now = datetime.utcnow()
        
        # Récupérer les événements nécessitant des notifications
        events_15min = NotificationEvent.query.filter(
            NotificationEvent.start_time <= now + timedelta(minutes=15),
            NotificationEvent.start_time > now + timedelta(minutes=14),
            NotificationEvent.notification_15min_sent == False
        ).all()
        
        events_3min = NotificationEvent.query.filter(
            NotificationEvent.start_time <= now + timedelta(minutes=3),
            NotificationEvent.start_time > now + timedelta(minutes=2),
            NotificationEvent.notification_3min_sent == False
        ).all()
        
        # Envoyer notifications 15 minutes
        for event in events_15min:
            self._send_event_notification(event, '15min')
        
        # Envoyer notifications 3 minutes
        for event in events_3min:
            self._send_event_notification(event, '3min')
    
    def _send_event_notification(self, event, reminder_type):
        """Envoie une notification pour un événement."""
        try:
            if reminder_type == '15min':
                title = f"Dans 15 min : {event.title}"
                priority = 'normal'
            else:  # 3min
                title = f"Dans 3 min : {event.title}"
                priority = 'high'
            
            body = f"📍 {event.location}" if event.location else "Session à venir"
            if event.description:
                body += f" - {event.description[:50]}..."
            
            # Récupérer les utilisateurs avec notifications activées
            target_users = User.query.filter(
                User.enable_event_reminders == True,
                User.is_active == True
            ).join(PushSubscription).filter(
                PushSubscription.is_active == True
            ).distinct().all()
            
            if not target_users:
                current_app.logger.info(f"Aucun utilisateur abonné pour {event.title}")
                return
            
            # Envoyer la notification
            success_count = 0
            for user in target_users:
                try:
                    if notification_service.send_notification_to_user(
                        user=user,
                        title=title,
                        body=body,
                        url='/conference/programme',
                        priority=priority
                    ):
                        success_count += 1
                except Exception as e:
                    current_app.logger.error(f"Erreur envoi à {user.email}: {e}")
            
            # Marquer comme envoyé
            if reminder_type == '15min':
                event.notification_15min_sent = True
            else:
                event.notification_3min_sent = True
            
            db.session.commit()
            
            current_app.logger.info(
                f"🔔 Notification {reminder_type} pour '{event.title}': "
                f"{success_count}/{len(target_users)} envoyées"
            )
            
        except Exception as e:
            current_app.logger.error(f"Erreur notification événement {event.event_id}: {e}")
    
    def create_manual_event(self, title, start_time, location=None, description=None):
        """Crée un événement manuellement (pour les admins)."""
        event_id = self._generate_event_id(title, start_time)
        
        event = NotificationEvent(
            event_id=event_id,
            title=title,
            description=description or '',
            location=location or '',
            start_time=start_time,
            event_type='manual'
        )
        
        db.session.add(event)
        db.session.commit()
        
        return event
    
    def get_upcoming_events(self, limit=10):
        """Récupère les prochains événements."""
        now = datetime.utcnow()
        
        return NotificationEvent.query.filter(
            NotificationEvent.start_time > now
        ).order_by(NotificationEvent.start_time).limit(limit).all()

# Instance globale du service
auto_notification_service = AutoNotificationService()
