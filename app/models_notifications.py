from app import db
from datetime import datetime

class PushSubscription(db.Model):
    """Modèle pour stocker les abonnements aux notifications push des utilisateurs."""
    __tablename__ = 'push_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relation avec User
    user = db.relationship('User', backref='push_subscriptions')
    
    def to_dict(self):
        """Convertit l'abonnement en format attendu par pywebpush."""
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh,
                "auth": self.auth
            }
        }
    
    def __repr__(self):
        return f'<PushSubscription {self.id} - User {self.user_id}>'


class NotificationEvent(db.Model):
    """Modèle pour les événements de notification (sessions du programme)."""
    __tablename__ = 'notification_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(100), unique=True, nullable=False)  # identifiant unique de l'événement
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(100))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    event_type = db.Column(db.String(50))  # plenary, parallel, break, etc.
    
    # Notifications envoyées
    notification_3min_sent = db.Column(db.Boolean, default=False)
    notification_15min_sent = db.Column(db.Boolean, default=False)
    notification_start_sent = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<NotificationEvent {self.event_id}: {self.title}>'


class AdminNotification(db.Model):
    """Modèle pour les notifications manuelles envoyées par l'admin."""
    __tablename__ = 'admin_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Options d'envoi
    target_all_users = db.Column(db.Boolean, default=True)
    target_reviewers = db.Column(db.Boolean, default=False)
    target_authors = db.Column(db.Boolean, default=False)
    
    # Suivi d'envoi
    sent_at = db.Column(db.DateTime)
    total_sent = db.Column(db.Integer, default=0)
    total_failed = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    sender = db.relationship('User', backref='sent_notifications')
    
    def __repr__(self):
        return f'<AdminNotification {self.id}: {self.title}>'


class NotificationLog(db.Model):
    """Log des notifications envoyées."""
    __tablename__ = 'notification_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    notification_type = db.Column(db.String(50))  # 'event_reminder', 'admin_broadcast', etc.
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    
    # Détails techniques
    endpoint = db.Column(db.Text)
    success = db.Column(db.Boolean)
    error_message = db.Column(db.Text)
    response_code = db.Column(db.Integer)
    
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    user = db.relationship('User', backref='notification_logs')
    
    def __repr__(self):
        return f'<NotificationLog {self.id}: {self.notification_type}>'
