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
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from markupsafe import Markup
import re
from datetime import datetime, timedelta
from .conference_routes import conference
from .models import db

migrate = Migrate()
login_manager = LoginManager()
mail = Mail()


def nl2br_filter(text):
    """
    Convertit les sauts de ligne en balises HTML <br>.
    
    Args:
        text (str): Le texte à convertir
        
    Returns:
        Markup: Le texte HTML avec les <br>
    """
    if not text:
        return ""
    
    # Échapper le HTML pour éviter les injections XSS
    from markupsafe import escape
    text = escape(text)
    
    # Remplacer les sauts de ligne par des <br>
    text = re.sub(r'\r\n|\r|\n', '<br>', str(text))
    
    # Retourner comme Markup pour éviter l'échappement automatique
    return Markup(text)

def datetime_filter(timestamp, format='%d/%m/%Y %H:%M'):
    """Convertit un timestamp en date formatée."""
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp).strftime(format)
    return str(timestamp)

def convert_theme_codes_filter(codes_string):
    """Filtre Jinja pour convertir les codes de thématiques en noms complets."""
    if not codes_string:
        return 'Non spécifiées'
    
    try:
        from app.emails import _convert_codes_to_names
        return _convert_codes_to_names(codes_string)
    except Exception as e:
        # Utiliser print ou logging standard au lieu de app.logger
        import logging
        logging.warning(f"Erreur conversion thématiques dans template: {e}")
        return codes_string or 'Non spécifiées'



def create_app():
    app = Flask(__name__)
    
    # Configuration directe depuis les variables d'environnement (remplace config.py)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join("static", "uploads")
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 52428800))
    
    # Configuration email
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 465))
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False') == 'True'
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
    
    # Configuration application
    app.config['BASE_URL'] = os.getenv('BASE_URL', 'http://localhost:5000')
    app.config['ENV'] = os.getenv('FLASK_ENV', 'development')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Configuration emails par défaut
    app.config['REGISTRATION_EMAIL_RECIPIENTS'] = ["organizers@conferenceflow.fr", "admin@conferenceflow.fr"]
    app.config['REGISTRATION_EMAIL_SENDER'] = os.getenv('MAIL_USERNAME', 'inscription@conferenceflow.fr')
    
    # Validation des variables requises
    required_vars = ['SECRET_KEY', 'DATABASE_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Variables d'environnement manquantes : {', '.join(missing_vars)}")

    # Configuration HAL (NOUVEAU)
    app.config['HAL_API_URL'] = os.getenv('HAL_API_URL', 'https://api.archives-ouvertes.fr')
    app.config['HAL_TEST_MODE'] = os.getenv('HAL_TEST_MODE', 'true').lower() == 'true'
    app.config['HAL_USERNAME'] = os.getenv('HAL_USERNAME')
    app.config['HAL_PASSWORD'] = os.getenv('HAL_PASSWORD')
    
    # Configuration notifications push (NOUVEAU)
    app.config['VAPID_PRIVATE_KEY'] = os.getenv('VAPID_PRIVATE_KEY')
    app.config['VAPID_PUBLIC_KEY'] = os.getenv('VAPID_PUBLIC_KEY') 
    app.config['VAPID_SUBJECT'] = os.getenv('VAPID_SUBJECT', 'mailto:admin@conference-flow.com')
    app.config['NOTIFICATION_SEND_REMINDERS'] = os.getenv('NOTIFICATION_SEND_REMINDERS', 'true').lower() == 'true'

    if app.config['ENV'] == 'production':
        app.config['SESSION_COOKIE_SECURE'] = True 
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=120)
    
    # Parser les temps de rappel (ex: "15,3" -> [15, 3])
    reminder_times_str = os.getenv('NOTIFICATION_REMINDER_TIMES', '15,3')
    try:
        app.config['NOTIFICATION_REMINDER_TIMES'] = [int(x.strip()) for x in reminder_times_str.split(',')]
    except (ValueError, AttributeError):
        app.config['NOTIFICATION_REMINDER_TIMES'] = [15, 3]  # valeur par défaut
    
    app.config['NOTIFICATION_MAX_RETRIES'] = int(os.getenv('NOTIFICATION_MAX_RETRIES', 3))

    
    app.jinja_env.filters['nl2br'] = nl2br_filter
    app.jinja_env.filters['datetime'] = datetime_filter
    app.jinja_env.filters['convert_theme_codes'] = convert_theme_codes_filter
    
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    
    login_manager.login_view = 'auth.login'

    try:
        from app.notification_routes import notifications_api
        app.register_blueprint(notifications_api)
        app.logger.info("✅ Routes API notifications enregistrées")
    except ImportError as e:
        app.logger.warning(f"⚠️ Impossible de charger les routes notifications: {e}")
    except Exception as e:
        app.logger.error(f"❌ Erreur enregistrement routes notifications: {e}")
    
    with app.app_context():

        try:
            # 1. Import des modèles existants
            from app import models  # vos modèles existants si vous en avez
            
            # 2. Import des modèles de notifications
            #from app.models_notifications import PushSubscription, NotificationEvent, AdminNotification, NotificationLog
            from app.models import PushSubscription, NotificationEvent, AdminNotification, NotificationLog
            app.logger.info("✅ Modèles de notifications importés")
            
            # 3. Créer TOUTES les tables (existantes + notifications)
            db.create_all()
            app.logger.info("✅ Toutes les tables créées/vérifiées")
            
            # 4. Test du service de notification
            from app.services.notification_service import notification_service
            if notification_service.is_available():
                app.logger.info("✅ Service de notifications disponible et configuré")
            else:
                app.logger.warning("⚠️ Service de notifications non configuré (clés VAPID manquantes)")
                
        except ImportError as e:
            app.logger.warning(f"⚠️ Certains composants de notifications non disponibles: {e}")
        except Exception as e:
            app.logger.error(f"❌ Erreur initialisation base de données ou notifications: {e}")


        try:
            from .config_loader import ConfigLoader
            config_loader = ConfigLoader()
            
            # Charger les configurations
            app.conference_config = config_loader.load_conference_config()
            app.themes_config = config_loader.load_themes()
            app.email_config = config_loader.load_email_config()

            app.config_loader = config_loader
            app.logger.info(f"✅ Configuration chargée : {len(app.themes_config)} thématiques")
            
        except Exception as e:
            app.logger.error(f"❌ Erreur chargement configuration : {e}")
            # Configuration par défaut en cas d'erreur
            app.conference_config = {}
            app.themes_config = []
            app.email_config = {}

        @app.context_processor
        def inject_conference_config():
            """Injecte la configuration dans tous les templates."""
            conference_info = app.conference_config.get('conference', {})
            dates_info = app.conference_config.get('dates', {})
            location_info = app.conference_config.get('location', {})
            contacts_info = app.conference_config.get('contacts', {})
            fees_info = app.conference_config.get('fees', {})
            transport_info = app.conference_config.get('transport', {})
            accommodation_info = app.conference_config.get('accommodation', {})
            legal_info = app.conference_config.get('legal', {})
            
            return {
                'conference': conference_info,  # ← CHANGEMENT : on passe directement conference_info au lieu d'une structure modifiée
                'conference_dates': dates_info,
                'conference_location': location_info,
                'conference_contacts': contacts_info,
                'conference_fees': fees_info,
                'conference_transport': transport_info,
                'conference_accommodation': accommodation_info,
                'legal': legal_info,
                'themes_available': len(app.themes_config)
            }


        
    
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))


    
    from .routes import main
    from .auth import auth
    from .admin import admin
    #from .registration_routes import registration
    from .communication_public import public_comm
    from .conference_books import books
    from .export_integration.export_routes import export_bp
    from .emails import (
        send_email,
        send_submission_confirmation_email,
        send_activation_email_to_user,
        send_coauthor_notification_email,
        send_existing_coauthor_notification_email,
        send_review_reminder_email,
        send_qr_code_reminder_email,
        send_decision_email,
        send_biot_fourier_audition_notification,
        send_reviewer_assignment_email,
        send_hal_collection_request
    )
    try:
        from app.models import PushSubscription, NotificationEvent, AdminNotification, NotificationLog
        app.logger.info("✅ Modèles de notifications importés")
    except ImportError as e:
        app.logger.warning(f"⚠️ Modèles de notifications non disponibles: {e}")

    app.send_email = send_email
    app.send_submission_confirmation_email = send_submission_confirmation_email
    app.send_activation_email_to_user = send_activation_email_to_user
    app.send_coauthor_notification_email = send_coauthor_notification_email
    app.send_existing_coauthor_notification_email = send_existing_coauthor_notification_email
    app.send_review_reminder_email = send_review_reminder_email
    app.send_qr_code_reminder_email = send_qr_code_reminder_email
    app.send_decision_email = send_decision_email 
    app.send_biot_fourier_audition_notification = send_biot_fourier_audition_notification
    app.send_reviewer_assignment_email = send_reviewer_assignment_email
    app.send_hal_collection_request = send_hal_collection_request
    
    app.register_blueprint(main)
    app.register_blueprint(conference)
    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(admin, url_prefix="/admin")
    #app.register_blueprint(registration, url_prefix="/registration")
    app.register_blueprint(books, url_prefix="/admin/books")
    app.register_blueprint(public_comm, url_prefix="/public")
    app.register_blueprint(export_bp)


    # ==================== NOTIFICATIONS AUTOMATIQUES ====================
    ########################################################################################
    # if not app.config.get('TESTING', False):                                             #
    #     try:                                                                             #
    #         from app.services.auto_notification_service import auto_notification_service #
    #                                                                                      #
    #         # Démarrer le service dans le contexte de l'app                              #
    #         with app.app_context():                                                      #
    #             auto_notification_service.start_notification_scheduler()                 #
    #             app.logger.info("🔔 Service de notifications automatiques démarré")      #
    #                                                                                      #
    #         # Ajouter le service à l'app                                                 #
    #         app.auto_notification_service = auto_notification_service                    #
    #                                                                                      #
    #     except ImportError as e:                                                         #
    #         app.logger.warning(f"⚠️ Service notifications non disponible: {e}")           #
    #     except Exception as e:                                                           #
    #         app.logger.error(f"❌ Erreur service notifications: {e}")                    #
    #                                                                                      #
    #                                                                                      #
    # return app                                                                           #
    ########################################################################################


    # ==================== NOTIFICATIONS AUTOMATIQUES ====================
    if not app.config.get('TESTING', False):  # Ne pas démarrer en mode test
        try:
            from app.services.auto_notification_service import AutoNotificationService
            
            class LazyNotificationService:
                def __init__(self, app):
                    self.app = app
                    self._service = None
                    self._initialized = False
                    self.logger = app.logger
                
                def _ensure_initialized(self):
                    """S'assure que le service est initialisé."""
                    if not self._initialized:
                        try:
                            with self.app.app_context():
                                self._service = AutoNotificationService()
                                self._service.sync_events_from_program()
                                self._service.start_notification_scheduler()
                                self.logger.info("🔔 Service de notifications automatiques initialisé (lazy)")
                                self._initialized = True
                        except Exception as e:
                            self.logger.error(f"Erreur initialisation lazy notifications: {e}")
                
                def sync_events_from_program(self):
                    self._ensure_initialized()
                    if self._service:
                        with self.app.app_context():
                            return self._service.sync_events_from_program()
                
                def start(self):
                    self._ensure_initialized()
                    if self._service:
                        return self._service.start()
                
                def stop(self):
                    if self._service:
                        return self._service.stop()
                
                @property
                def is_running(self):
                    if not self._service:
                        return False
                    return self._service.is_running
            
            # ⚠️ AJOUT : Créer le service lazy
            app.auto_notification_service = LazyNotificationService(app)
            
            # ⚠️ AJOUT : Hook pour initialiser au premier accès aux routes admin
            @app.before_request
            def init_notifications_on_first_admin_access():
                from flask import request
                if (request.endpoint and 
                    request.endpoint.startswith('admin.') and 
                    'notification' in request.endpoint and
                    not app.auto_notification_service._initialized):
                    
                    app.auto_notification_service._ensure_initialized()
            
        except ImportError as e:
            app.logger.error(f"Service de notifications automatiques non disponible: {e}")
        except Exception as e:
            app.logger.error(f"Erreur setup notifications auto: {e}")
    
    # ⚠️ AJOUT : Arrêt propre du service
    import atexit
    
    def shutdown_notification_service():
        if hasattr(app, 'auto_notification_service'):
            try:
                app.auto_notification_service.stop()
                app.logger.info("🛑 Service de notifications arrêté")
            except Exception as e:
                app.logger.error(f"Erreur arrêt service notifications: {e}")
    
    atexit.register(shutdown_notification_service)

    return app
