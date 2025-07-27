# app/models.py - Modèles de données pour SFT 2026

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from enum import Enum

db = SQLAlchemy()




# ==================== TABLES D'ASSOCIATION ====================


# Table d'association pour les auteurs des communications
communication_authors = db.Table('communication_authors',
    db.Column('communication_id', db.Integer, db.ForeignKey('communication.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)
# Table d'association pour les affiliations des users
user_affiliations = db.Table('user_affiliations',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('affiliation_id', db.Integer, db.ForeignKey('affiliation.id'), primary_key=True)
)


# ==================== MODÈLES PRINCIPAUX ====================

class User(UserMixin, db.Model):
    """Modèle utilisateur avec support des rôles et spécialités."""
    
    # Clé primaire OBLIGATOIRE
    id = db.Column(db.Integer, primary_key=True)
    
    # Informations de base
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)

    # Identifiants chercheur - NOUVEAUX CHAMPS
    idhal = db.Column(db.String(50), nullable=True)
    orcid = db.Column(db.String(19), nullable=True)  # Format: 0000-0000-0000-0000
    
    # Rôles
    is_admin = db.Column(db.Boolean, default=False)
    is_reviewer = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Métadonnées
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relations
    affiliations = db.relationship('Affiliation', secondary=user_affiliations, 
                               back_populates='members')

    
    # Relations many-to-many
    specialites_codes = db.Column(db.String(500), nullable=True)

    
    authored_communications = db.relationship('Communication', secondary=communication_authors,
                                            back_populates='authors')

    activation_token = db.Column(db.String(100), nullable=True, unique=True)
    is_activated = db.Column(db.Boolean, default=False)
    activation_sent_at = db.Column(db.DateTime, nullable=True)
    
    def generate_activation_token(self):
        """Génère un token d'activation unique."""
        import secrets
        self.activation_token = secrets.token_urlsafe(32)
        self.activation_sent_at = datetime.utcnow()
        return self.activation_token
    
    def is_activation_token_valid(self, token):
        """Vérifie si le token d'activation est valide."""
        if not self.activation_token or self.activation_token != token:
            return False
        
        # Token valide 7 jours
        from datetime import timedelta
        if self.activation_sent_at:
            expiry = self.activation_sent_at + timedelta(days=7)
            return datetime.utcnow() <= expiry
        
        return True


    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def set_password(self, password):
        """Hash et stocke le mot de passe."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Vérifie le mot de passe."""
        return check_password_hash(self.password_hash, password)

    @property
    def specialites(self):
        """Retourne les objets thématiques des spécialités."""
        if not self.specialites_codes:
            return []
        codes = [code.strip() for code in self.specialites_codes.split(',') if code.strip()]
        return [ThematiqueHelper.get_by_code(code) for code in codes 
                if ThematiqueHelper.is_valid_code(code)]
    
    # AJOUTEZ CETTE MÉTHODE
    def set_specialites(self, codes_list):
        """Définit les spécialités à partir d'une liste de codes."""
        if not codes_list:
            self.specialites_codes = None
            return
        
        valid_codes = [code.upper() for code in codes_list if ThematiqueHelper.is_valid_code(code)]
        self.specialites_codes = ','.join(valid_codes) if valid_codes else None
    
    @property
    def nb_reviews_assigned(self):
        """Nombre de reviews assignées (en cours)."""
        return ReviewAssignment.query.filter_by(
            reviewer_id=self.id,
            status='assigned'
        ).count()
    
    @property
    def nb_reviews_completed(self):
        """Nombre de reviews terminées."""
        return ReviewAssignment.query.filter_by(
            reviewer_id=self.id,
            status='completed'
        ).count()
    
    def has_conflict_with_communication(self, communication):
        """Vérifie s'il y a un conflit d'intérêt avec une communication."""
        if not communication.authors:
            return False
            
        # Récupérer les affiliations des auteurs
        author_affiliations = set()
        for author in communication.authors:
            if author.affiliation:
                author_affiliations.add(author.affiliation.id)
        
        # Vérifier si le reviewer a la même affiliation
        if self.affiliation:
            return self.affiliation.id in author_affiliations
            
        return False

    @property
    def full_name(self):
        """Nom complet de l'utilisateur."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.email


    
class Affiliation(db.Model):
    """Modèle pour les affiliations (laboratoires, universités, etc.)."""
    
    id = db.Column(db.Integer, primary_key=True)
    sigle = db.Column(db.String(20), unique=True, nullable=False)
    nom_complet = db.Column(db.String(200), nullable=False)
    adresse = db.Column(db.Text, nullable=True)
    citation = db.Column(db.String(500), nullable=True)
    identifiant_hal = db.Column(db.String(50), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    members = db.relationship('User', secondary=user_affiliations, 
                              back_populates='affiliations')
    
    def __repr__(self):
        return f'<Affiliation {self.sigle}: {self.nom_complet}>'
    
    @classmethod
    def find_by_sigle(cls, sigle):
        """Trouve une affiliation par son sigle."""
        return cls.query.filter_by(sigle=sigle.upper()).first()
    
    @classmethod
    def find_by_hal_id(cls, hal_id):
        """Trouve une affiliation par son identifiant HAL."""
        return cls.query.filter_by(identifiant_hal=hal_id).first()

#  THEMATIQUES ######
class ThematiqueHelper:
    """Classe utilitaire pour gérer les thématiques fixes."""
    
    @classmethod
    def get_all(cls):
        """Retourne toutes les thématiques."""
        return DEFAULT_THEMATIQUES
    
    @classmethod
    def get_by_code(cls, code):
        """Récupère une thématique par son code."""
        code = code.upper()
        return next((t for t in DEFAULT_THEMATIQUES if t['code'] == code), None)
    
    @classmethod
    def get_codes(cls):
        """Retourne la liste des codes valides."""
        return [t['code'] for t in DEFAULT_THEMATIQUES]
    
    @classmethod
    def is_valid_code(cls, code):
        """Vérifie si un code de thématique est valide."""
        return code.upper() in cls.get_codes()


class CommunicationStatus(Enum):
    # Workflow Article
    RESUME_SOUMIS = 'résumé_soumis'
    ARTICLE_SOUMIS = 'article_soumis' 
    EN_REVIEW = 'en_review'
    REVISION_DEMANDEE = 'révision_demandée'  
    ACCEPTE = 'accepté'
    REJETE = 'rejeté'
    
    # Workflow WIP
    WIP_SOUMIS = 'wip_soumis'
    
    # Commun aux deux
    POSTER_SOUMIS = 'poster_soumis'




class Communication(db.Model):
    """Modèle pour les communications soumises."""
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    #abstract = db.Column(db.Text, nullable=True)
    keywords = db.Column(db.String(500), nullable=True)
    
    # Statut du workflow
    status = db.Column(db.Enum(CommunicationStatus), nullable=False)   
    type = db.Column(db.String(50), nullable=False)

    # Thématiques
    thematiques_codes = db.Column(db.String(500), nullable=True)
    
    # Dates importantes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resume_submitted_at = db.Column(db.DateTime, nullable=True)
    article_submitted_at = db.Column(db.DateTime, nullable=True)
    poster_submitted_at = db.Column(db.DateTime, nullable=True)
    
    # Relations
    authors = db.relationship('User', secondary=communication_authors,
                            back_populates='authored_communications')

    final_decision = db.Column(db.String(20), nullable=True)  # 'accepter', 'rejeter', 'reviser'
    decision_date = db.Column(db.DateTime, nullable=True)
    decision_by_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_communication_decision_by'), nullable=True)
    decision_comments = db.Column(db.Text, nullable=True)
    decision_notification_sent = db.Column(db.Boolean, default=False, nullable=True)
    decision_notification_sent_at = db.Column(db.DateTime, nullable=True)
    decision_notification_error = db.Column(db.Text, nullable=True)
    decision_by = db.relationship('User', foreign_keys=[decision_by_id])
    
    hal_authorization = db.Column(db.Boolean, default=True, nullable=False)
    hal_deposited_at = db.Column(db.DateTime, nullable=True)
    hal_url = db.Column(db.String(255), nullable=True)
    
    
    def __repr__(self):
        return f'<Communication {self.id}: {self.title}>'

    def get_file(self, file_type):
        """Récupère le fichier actuel d'un type donné."""
        return SubmissionFile.query.filter_by(
            communication_id=self.id,
            file_type=file_type
        ).first()

    def has_file(self, file_type):
        """Vérifie si un fichier d'un type donné existe."""
        return self.get_file(file_type) is not None

    def can_submit_article(self):
        """Vérifie si on peut soumettre l'article."""
        return (self.status == CommunicationStatus.RESUME_SOUMIS and 
                self.has_file('résumé'))

    def can_submit_poster(self):
        """Vérifie si on peut soumettre le poster."""
        return self.status == CommunicationStatus.ACCEPTE

    def get_latest_file(self, file_type):
        """Récupère la dernière version d'un fichier."""
        return SubmissionFile.query.filter_by(
            communication_id=self.id,
            file_type=file_type
        ).order_by(SubmissionFile.version.desc()).first()

    
    def advance_to_next_status(self):
        """Fait avancer la communication vers le statut suivant."""
        if self.status == CommunicationStatus.RESUME_SOUMIS and self.has_file('article'):
            self.status = CommunicationStatus.ARTICLE_SOUMIS
            self.article_submitted_at = datetime.utcnow()
        elif self.status == CommunicationStatus.ACCEPTE and self.has_file('poster'):
            self.status = CommunicationStatus.POSTER_SOUMIS
            self.poster_submitted_at = datetime.utcnow()

    def get_next_status_after_upload(self, file_type):
        """Détermine le prochain statut après upload d'un fichier."""
        if self.type == 'article':
            if file_type == 'résumé':
                return CommunicationStatus.RESUME_SOUMIS
            elif file_type == 'article':
                return CommunicationStatus.ARTICLE_SOUMIS
            elif file_type == 'poster':
                return CommunicationStatus.POSTER_SOUMIS
        elif self.type == 'wip':
            if file_type == 'wip':
                return CommunicationStatus.WIP_SOUMIS
            elif file_type == 'poster':
                return CommunicationStatus.POSTER_SOUMIS
        
        return self.status  # Pas de changement

    def can_upload_file_type(self, file_type):
        """Vérifie si on peut uploader un type de fichier selon l'état actuel."""
        if self.type == 'article':
            if file_type == 'résumé':
                return True  # Toujours possible de remplacer le résumé
            elif file_type == 'article':
                return self.status in [CommunicationStatus.RESUME_SOUMIS, CommunicationStatus.ARTICLE_SOUMIS]
            elif file_type == 'poster':
                return self.status == CommunicationStatus.ACCEPTE
        elif self.type == 'wip':
            if file_type == 'wip':
                return True  # Toujours possible de remplacer le WIP
            elif file_type == 'poster':
                return self.status == CommunicationStatus.WIP_SOUMIS
        
        return False
    
    
    @property
    def thematiques(self):
        """Retourne les objets thématiques de la communication."""
        if not self.thematiques_codes:
            return []
        codes = [code.strip() for code in self.thematiques_codes.split(',') if code.strip()]
        return [ThematiqueHelper.get_by_code(code) for code in codes 
                if ThematiqueHelper.is_valid_code(code)]
    
    def set_thematiques(self, codes_list):
        """Définit les thématiques à partir d'une liste de codes."""
        if not codes_list:
            self.thematiques_codes = None
            return
        
        valid_codes = [code.upper() for code in codes_list if ThematiqueHelper.is_valid_code(code)]
        self.thematiques_codes = ','.join(valid_codes) if valid_codes else None
    
    def has_thematique(self, code):
        """Vérifie si la communication a une thématique donnée."""
        if not self.thematiques_codes:
            return False
        return code.upper() in self.thematiques_codes.split(',')

    # Dans la classe Communication, ajoutez ces nouvelles méthodes :

    def get_potential_reviewers_advanced(self):
        """Trouve les reviewers potentiels avec détection de conflits avancée."""
        if not self.thematiques_codes:
            return []
    
        # Codes de thématiques de cette communication
        comm_codes = [code.strip() for code in self.thematiques_codes.split(',') if code.strip()]
    
        # Récupérer tous les reviewers actifs
        all_reviewers = User.query.filter_by(
            is_reviewer=True, 
            is_active=True,
            is_activated=True
        ).all()
    
        potential_reviewers = []
    
        for reviewer in all_reviewers:
            # Vérifier qu'il a des spécialités communes
            if not reviewer.specialites_codes:
                continue
        
            reviewer_codes = reviewer.specialites_codes.split(',')
            common_themes = set(comm_codes) & set(reviewer_codes)
        
            if not common_themes:
                continue  # Pas de thématiques en commun
        
            # Détecter les conflits d'intérêts
            conflict_detected = False
            conflict_reason = None
        
            # 1. Conflit d'affiliation
            if self.has_affiliation_conflict_with_reviewer(reviewer):
                conflict_detected = True
                conflict_reason = "Même affiliation qu'un auteur"
        
            # 2. Le reviewer est déjà auteur
            if reviewer in self.authors:
                conflict_detected = True
                conflict_reason = "Le reviewer est auteur de la communication"
        
            # 3. Déjà assigné à cette communication
            already_assigned = ReviewAssignment.query.filter_by(
                communication_id=self.id,
                reviewer_id=reviewer.id
            ).first()
        
            if already_assigned:
                continue  # Skip, déjà assigné
        
            # Calculer un score de pertinence
            score = self.calculate_reviewer_relevance_score(reviewer, common_themes)
        
            potential_reviewers.append({
                'reviewer': reviewer,
                'common_themes': list(common_themes),
                'conflict_detected': conflict_detected,
                'conflict_reason': conflict_reason,
                'relevance_score': score,
                'current_workload': reviewer.nb_reviews_assigned
            })
    
        # Trier par score de pertinence (desc) puis par charge de travail (asc)
        potential_reviewers.sort(
            key=lambda x: (-x['relevance_score'], x['current_workload'], x['conflict_detected'])
        )
    
        return potential_reviewers

    def has_affiliation_conflict_with_reviewer(self, reviewer):
        """Vérifie s'il y a conflit d'affiliation entre le reviewer et les auteurs."""
        if not reviewer.affiliations:
            return False
    
        reviewer_affiliation_ids = {aff.id for aff in reviewer.affiliations}
        
        for author in self.authors:
            if author.affiliations:
                author_affiliation_ids = {aff.id for aff in author.affiliations}
                if reviewer_affiliation_ids & author_affiliation_ids:  # Intersection non-vide
                    return True
            
        return False

    def calculate_reviewer_relevance_score(self, reviewer, common_themes):
        """Calcule un score de pertinence pour un reviewer."""
        score = 0
    
        # Points pour chaque thématique en commun (AUGMENTÉ)
        score += len(common_themes) * 25  # Era 10, maintenant 25
    
        # Bonus si le reviewer a beaucoup d'expertise
        if reviewer.specialites_codes:
            total_specialities = len(reviewer.specialites_codes.split(','))
            score += min(total_specialities * 3, 15)  # Était 2, maintenant 3
    
        # Malus pour la charge de travail actuelle (RÉDUIT)
        current_load = reviewer.nb_reviews_assigned
        score -= current_load * 3  # Était -5, maintenant -3
    
        # Bonus pour l'expérience
        completed_reviews = reviewer.nb_reviews_completed
        score += min(completed_reviews * 2, 10)  # Était 3/15, maintenant 2/10
    
        return max(score, 0)

    def suggest_reviewers(self, nb_reviewers=2):
        """Suggère automatiquement des reviewers pour cette communication."""
        potential_reviewers = self.get_potential_reviewers_advanced()

        if len(potential_reviewers) == 0:
            return {
                'success': False,
                'message': 'Aucun reviewer disponible trouvé',
                'suggestions': []
            }

        # Séparer les reviewers avec et sans conflit
        no_conflict = [r for r in potential_reviewers if not r['conflict_detected']]
        with_conflict = [r for r in potential_reviewers if r['conflict_detected']]

        suggestions = []

        # Prioriser les reviewers sans conflit
        for reviewer_data in no_conflict[:nb_reviewers]:
            suggestions.append(reviewer_data)
    
        # Si pas assez sans conflit, ajouter ceux avec conflit
        if len(suggestions) < nb_reviewers:
            remaining_needed = nb_reviewers - len(suggestions)
            for reviewer_data in with_conflict[:remaining_needed]:
                suggestions.append(reviewer_data)
    
        # Déterminer le succès et le message
        if len(potential_reviewers) < nb_reviewers:
            success = True  # Afficher quand même
            message = f'Reviewers disponibles ({len(potential_reviewers)} trouvés, {nb_reviewers} recommandés)'
        else:
            success = True
            message = f'{len(suggestions)} reviewer(s) suggéré(s)'
        
        return {
            'success': success,
            'suggestions': suggestions,
            'total_available': len(potential_reviewers),
            'message': message
        }


    def make_final_decision(self, decision, admin_user, comments=None):
        """
        Prend une décision finale sur la communication.
        
        Args:
        decision (str): 'accepter', 'rejeter', ou 'reviser'
        admin_user (User): L'administrateur qui prend la décision
        comments (str, optional): Commentaires sur la décision
        """
        if decision not in ['accepter', 'rejeter', 'reviser']:
            raise ValueError("Décision invalide. Doit être 'accepter', 'rejeter', ou 'reviser'")
    
        # Enregistrer la décision
        self.final_decision = decision
        self.decision_date = datetime.utcnow()
        self.decision_by_id = admin_user.id
        self.decision_comments = comments
        
        # Réinitialiser les champs de notification
        self.decision_notification_sent = False
        self.decision_notification_sent_at = None
        self.decision_notification_error = None
        
        # Mettre à jour le statut selon la décision
        if decision == 'accepter':
            self.status = CommunicationStatus.ACCEPTE
        elif decision == 'rejeter':
            self.status = CommunicationStatus.REJETE
        elif decision == 'reviser':
            self.status = CommunicationStatus.REVISION_DEMANDEE

        biot_fourier_audition_selected = db.Column(db.Boolean, default=False, nullable=True)
        biot_fourier_audition_selected_at = db.Column(db.DateTime, nullable=True)
        biot_fourier_audition_selected_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
        biot_fourier_audition_notification_sent = db.Column(db.Boolean, default=False, nullable=True)
        biot_fourier_audition_notification_sent_at = db.Column(db.DateTime, nullable=True)

        biot_fourier_selected_by = db.relationship('User', foreign_keys=[biot_fourier_audition_selected_by_id])

            
        return True
    
    @property
    def decision_made(self):
        """Vérifie si une décision finale a été prise."""
        return self.final_decision is not None
    
    def get_decision_status_display(self):
        """Retourne un affichage formaté du statut de décision."""
        if not self.decision_made:
            return {
                'status': 'pending',
                'text': 'En attente de décision',
                'class': 'warning'
            }
        
        decision_map = {
            'accepter': {'status': 'accepted', 'text': 'Acceptée', 'class': 'success'},
            'rejeter': {'status': 'rejected', 'text': 'Rejetée', 'class': 'danger'},
            'reviser': {'status': 'revision', 'text': 'Révision demandée', 'class': 'warning'}
        }
        
        return decision_map.get(self.final_decision, {
            'status': 'unknown', 'text': 'Statut inconnu', 'class': 'secondary'
        })
    
    def can_make_decision(self):
        """Vérifie si on peut prendre une décision sur cette communication."""
        # On peut prendre une décision si :
        # - C'est un article en review
        # - Ou c'est un WIP soumis
        # - Et qu'aucune décision n'a encore été prise
        if self.decision_made:
            return False
            
        return self.status in [
            CommunicationStatus.EN_REVIEW,
            CommunicationStatus.WIP_SOUMIS
        ]
    
    def reset_decision(self, admin_user):
        """
        Annule une décision prise (pour correction).
        Remet la communication en état "en review" ou "wip_soumis".
        """
        if not self.decision_made:
            return False
        
        # Remettre le statut précédent
        if self.type == 'article':
            self.status = CommunicationStatus.EN_REVIEW
        elif self.type == 'wip':
            self.status = CommunicationStatus.WIP_SOUMIS
        
        # Effacer la décision
        self.final_decision = None
        self.decision_date = None
        self.decision_by_id = None
        self.decision_comments = None
        
        return True
    

###################  Review  ####################


class ReviewRecommendation(Enum):
    ACCEPT = 'accepter'
    REVISE = 'réviser' 
    REJECT = 'rejeter'

class Review(db.Model):
    """Modèle pour le contenu des reviews avec tous les champs requis."""
    id = db.Column(db.Integer, primary_key=True)
    communication_id = db.Column(db.Integer, db.ForeignKey('communication.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Contenu de la review
    score = db.Column(db.Integer, nullable=True)  # Note sur 10
    recommendation = db.Column(db.Enum(ReviewRecommendation), nullable=True)
    comments_for_authors = db.Column(db.Text, nullable=True)  # Commentaires pour les auteurs
    comments_for_committee = db.Column(db.Text, nullable=True)  # Commentaires privés pour le conseil
    review_file_path = db.Column(db.String(255), nullable=True)  # Fichier de review optionnel
    
    # Prix Biot-Fourier
    recommend_for_biot_fourier = db.Column(db.Boolean, default=False)
    
    # Métadonnées
    submitted_at = db.Column(db.DateTime, nullable=True)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    communication = db.relationship('Communication', backref='reviews')
    reviewer = db.relationship('User', backref='submitted_reviews')
    
    def __repr__(self):
        return f'<Review {self.id}: {self.recommendation}>'

class ReviewAssignment(db.Model):
    """Modèle pour les affectations de review avec métadonnées complètes."""
    
    id = db.Column(db.Integer, primary_key=True)
    communication_id = db.Column(db.Integer, db.ForeignKey('communication.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Métadonnées d'assignation
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Admin qui a assigné
    notification_sent_at = db.Column(db.DateTime, nullable=True)
    
    # Statut et échéances
    status = db.Column(db.String(20), default='assigned')  # assigned, in_progress, completed, declined
    due_date = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Détection automatique
    auto_suggested = db.Column(db.Boolean, default=False)  # Suggéré automatiquement
    conflict_detected = db.Column(db.Boolean, default=False)  # Conflit détecté
    conflict_reason = db.Column(db.String(200), nullable=True)  # Raison du conflit

    declined = db.Column(db.Boolean, default=False, nullable=True)
    declined_at = db.Column(db.DateTime, nullable=True)
    decline_reason = db.Column(db.String(100), nullable=True)  # raison prédéfinie
    decline_reason_other = db.Column(db.Text, nullable=True)
    
    # Relations
    communication = db.relationship('Communication', backref='review_assignments')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref='review_assignments')
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id])
    
    def __repr__(self):
        return f'<ReviewAssignment {self.communication_id} -> {self.reviewer.email if self.reviewer else self.reviewer_id}>'
    
    @property
    def is_overdue(self):
        """Vérifie si la review est en retard."""
        if not self.due_date or self.status == 'completed':
            return False
        return datetime.utcnow() > self.due_date
    
    def get_or_create_review(self):
        """Récupère ou crée l'objet Review associé."""
        review = Review.query.filter_by(
            communication_id=self.communication_id,
            reviewer_id=self.reviewer_id
        ).first()
        
        if not review:
            review = Review(
                communication_id=self.communication_id,
                reviewer_id=self.reviewer_id
            )
            db.session.add(review)
            db.session.flush()
        
        return review

    def decline_review(self, reason, other_reason=None):
        """Permet au reviewer de refuser la review."""
        self.declined = True
        self.declined_at = datetime.utcnow()
        self.decline_reason = reason
        self.decline_reason_other = other_reason if reason == 'other' else None
        self.status = 'declined'
        
        return True
    
    @property
    def decline_reason_display(self):
        """Affichage formaté de la raison du refus."""
        if not self.declined:
            return None
            
        reasons = {
            'conflict': 'Conflit d\'intérêt',
            'workload': 'Surcharge de travail',
            'expertise': 'Domaine hors expertise',
            'unavailable': 'Indisponibilité',
            'other': 'Autre raison'
        }
        
        base_reason = reasons.get(self.decline_reason, self.decline_reason)
        
        if self.decline_reason == 'other' and self.decline_reason_other:
            return f"{base_reason}: {self.decline_reason_other}"
        
        return base_reason


class FileType(Enum):
    RESUME = 'résumé'
    ARTICLE = 'article'  
    POSTER = 'poster'





    
class SubmissionFile(db.Model):
    """Modèle pour les fichiers de soumission."""
    id = db.Column(db.Integer, primary_key=True)
    communication_id = db.Column(db.Integer, db.ForeignKey('communication.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(255), nullable=False)
    version = db.Column(db.Integer, default=1)
    communication = db.relationship('Communication', backref='submission_files')  # Changé de 'files' à 'submission_files'

class Registration(db.Model):
    """Modèle pour les inscriptions à la conférence."""
    id = db.Column(db.Integer, primary_key=True)
    
    # Informations personnelles
    title = db.Column(db.String(20))
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    
    # Affiliation
    institution = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(200))
    position = db.Column(db.String(100))
    
    # Dates et statut
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_status = db.Column(db.String(20), default='pending')
    total_amount = db.Column(db.Float, default=0.0)
    
    # Relation avec l'utilisateur
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='registration')






    
# ==================== DONNÉES PAR DÉFAUT ====================

DEFAULT_THEMATIQUES = [
    {
        'code': 'COND', 
        'nom': 'Conduction, convection, rayonnement',
        'description': 'Transferts de chaleur par conduction, convection et rayonnement',
        'couleur': '#dc3545'
    },
    {
        'code': 'MULTI', 
        'nom': 'Changement de phase et transferts multiphasiques',
        'description': 'Phénomènes de changement de phase et écoulements multiphasiques',
        'couleur': '#20c997'
    },
    {
        'code': 'POREUX', 
        'nom': 'Transferts en milieux poreux',
        'description': 'Transferts de masse et de chaleur en milieux poreux',
        'couleur': '#0dcaf0'
    },
    {
        'code': 'MICRO', 
        'nom': 'Micro et nanothermique',
        'description': 'Transferts thermiques à l\'échelle micro et nanométrique',
        'couleur': '#198754'
    },
    {
        'code': 'BIO', 
        'nom': 'Thermique du vivant',
        'description': 'Applications thermiques dans le domaine du vivant',
        'couleur': '#fd7e14'
    },
    {
        'code': 'SYST', 
        'nom': 'Énergétique des systèmes',
        'description': 'Énergétique et optimisation des systèmes',
        'couleur': '#d63384'
    },
    {
        'code': 'COMBUST', 
        'nom': 'Combustion et flammes',
        'description': 'Phénomènes de combustion et étude des flammes',
        'couleur': '#ff6b35'
    },
    {
        'code': 'MACHINE', 
        'nom': 'Machines thermiques et frigorifiques',
        'description': 'Machines thermiques, pompes à chaleur, systèmes frigorifiques',
        'couleur': '#007bff'
    },
    {
        'code': 'ECHANG', 
        'nom': 'Échangeurs de chaleur',
        'description': 'Conception et optimisation des échangeurs de chaleur',
        'couleur': '#6f42c1'
    },
    {
        'code': 'STOCK', 
        'nom': 'Stockage thermique',
        'description': 'Technologies de stockage de l\'énergie thermique',
        'couleur': '#6610f2'
    },
    {
        'code': 'RENOUV', 
        'nom': 'Énergies renouvelables',
        'description': 'Applications thermiques des énergies renouvelables',
        'couleur': '#28a745'
    },
    {
        'code': 'BATIM', 
        'nom': 'Thermique du bâtiment',
        'description': 'Efficacité énergétique et confort thermique des bâtiments',
        'couleur': '#ffc107'
    },
    {
        'code': 'INDUS', 
        'nom': 'Thermique industrielle',
        'description': 'Applications thermiques dans l\'industrie',
        'couleur': '#17a2b8'
    },
    {
        'code': 'METRO', 
        'nom': 'Métrologie et techniques inverses',
        'description': 'Mesures thermiques et méthodes inverses',
        'couleur': '#6c757d'
    },
    {
        'code': 'SIMUL', 
        'nom': 'Modélisation et simulation numérique',
        'description': 'Méthodes numériques et modélisation en thermique',
        'couleur': '#343a40'
    }
]

def init_thematiques():
    """Initialise les thématiques par défaut."""
    created_count = 0
    
    for them_data in DEFAULT_THEMATIQUES:
        existing = Thematique.query.filter_by(code=them_data['code']).first()
        if not existing:
            thematique = Thematique(**them_data)
            db.session.add(thematique)
            created_count += 1
    
    try:
        db.session.commit()
        print(f"✅ {created_count} thématiques initialisées")
        return created_count
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur lors de l'initialisation des thématiques: {e}")
        raise e




# class Review(db.Model):
#     """Modèle pour le contenu des reviews."""
#     id = db.Column(db.Integer, primary_key=True)
#     communication_id = db.Column(db.Integer, db.ForeignKey('communication.id'), nullable=False)
#     reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
#     # Contenu de la review
#     comments = db.Column(db.Text)
#     decision = db.Column(db.String(20))  # accept, revise, reject
#     submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
#     completed = db.Column(db.Boolean, default=False)
    
#     # Relations
#     communication = db.relationship('Communication', backref='reviews')
#     reviewer = db.relationship('User', backref='submitted_reviews')
    
#     def __repr__(self):
#         return f'<Review {self.id}: {self.decision}>'


def import_affiliations_from_csv(csv_path='static/uploads/data/labos.csv'):
    """Importe les affiliations depuis le fichier CSV."""
    import csv
    import os
    from flask import current_app
    
    if not os.path.exists(csv_path):
        print(f"❌ Fichier {csv_path} non trouvé")
        return 0
    
    created_count = 0
    updated_count = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file, delimiter=';')
            
            for line_num, row in enumerate(csv_reader, 2):  # Ligne 2 car en-tête = ligne 1
                sigle = row.get('sigle', '').strip().upper()
                nom_complet = row.get('nom_complet', '').strip()
                adresse = row.get('adresse', '').strip()
                citation = row.get('citation', '').strip()
                identifiant_hal = row.get('identifiant_hal', '').strip()
                
                if not sigle or not nom_complet:
                    print(f"⚠️  Ligne {line_num}: Sigle ou nom manquant - ignorée")
                    continue
                
                # Vérifier si l'affiliation existe déjà
                existing = Affiliation.query.filter_by(sigle=sigle).first()
                
                if existing:
                    # Mettre à jour si nécessaire
                    updated = False
                    if existing.nom_complet != nom_complet:
                        existing.nom_complet = nom_complet
                        updated = True
                    if existing.adresse != (adresse or None):
                        existing.adresse = adresse or None
                        updated = True
                    if existing.citation != (citation or None):
                        existing.citation = citation or None
                        updated = True
                    if existing.identifiant_hal != (identifiant_hal or None):
                        existing.identifiant_hal = identifiant_hal or None
                        updated = True
                    
                    if updated:
                        existing.updated_at = datetime.utcnow()
                        updated_count += 1
                        print(f"📝 Affiliation mise à jour: {sigle}")
                else:
                    # Créer nouvelle affiliation
                    affiliation = Affiliation(
                        sigle=sigle,
                        nom_complet=nom_complet,
                        adresse=adresse or None,
                        citation=citation or None,
                        identifiant_hal=identifiant_hal or None,
                        is_active=True
                    )
                    db.session.add(affiliation)
                    created_count += 1
                    print(f"✅ Affiliation créée: {sigle}")
        
        db.session.commit()
        print(f"🎉 Import terminé: {created_count} créées, {updated_count} mises à jour")
        return created_count + updated_count
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur lors de l'import des affiliations: {e}")
        return 0
