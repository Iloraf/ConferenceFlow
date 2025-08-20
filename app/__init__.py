from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from markupsafe import Markup
import re
from datetime import datetime
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




def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    app.jinja_env.filters['nl2br'] = nl2br_filter
    app.jinja_env.filters['datetime'] = datetime_filter
    
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    
    login_manager.login_view = 'auth.login'

    with app.app_context():
        try:
            from .config_loader import ConfigLoader
            config_loader = ConfigLoader()
            
            # Charger les configurations
            app.conference_config = config_loader.load_conference_config()
            app.themes_config = config_loader.load_themes()
            app.email_config = config_loader.load_email_config()
            
            app.logger.info(f"Configuration chargée : {len(app.themes_config)} thématiques")
            
        except Exception as e:
            app.logger.error(f"Erreur chargement configuration : {e}")
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
    from .registration_routes import registration
    from .communication_public import public_comm
    from .conference_books import books
    from .hal_integration.hal_routes import hal_bp
    from .emails import (
        send_email,
        send_activation_email_to_user,
        send_coauthor_notification_email,
        send_existing_coauthor_notification_email,
        send_review_reminder_email,
        send_qr_code_reminder_email,
        send_decision_notification_email,
        send_biot_fourier_audition_notification
    )

    app.send_email = send_email
    app.send_activation_email_to_user = send_activation_email_to_user
    app.send_coauthor_notification_email = send_coauthor_notification_email
    app.send_existing_coauthor_notification_email = send_existing_coauthor_notification_email
    app.send_review_reminder_email = send_review_reminder_email
    app.send_qr_code_reminder_email = send_qr_code_reminder_email
    app.send_decision_notification_email = send_decision_notification_email 
    app.send_biot_fourier_audition_notification = send_biot_fourier_audition_notification

    
    app.register_blueprint(main)
    app.register_blueprint(conference)
    app.register_blueprint(auth, url_prefix="/auth")
    app.register_blueprint(admin, url_prefix="/admin")
    app.register_blueprint(registration, url_prefix="/registration")
    app.register_blueprint(books, url_prefix="/admin/books")
    app.register_blueprint(public_comm, url_prefix="/public")
    app.register_blueprint(hal_bp, url_prefix="/hal")
    return app
