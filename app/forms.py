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

from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, BooleanField, SelectMultipleField, widgets, SubmitField, StringField
from flask import current_app
from wtforms.validators import Optional
from .models import ThematiqueHelper, Affiliation
from wtforms.validators import DataRequired, Length, ValidationError

from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import TextAreaField


class ReviewForm(FlaskForm):
    comments_for_authors = TextAreaField("Commentaires pour les auteurs", validators=[DataRequired()])
    comments_for_committee = TextAreaField("Commentaires pour le comité scientifique")
    biot_fourier_award = BooleanField("Proposition pour le prix Biot-Fourier")
    grade = SelectField(
        "Note",
        choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("E", "E")],
        validators=[DataRequired()]
    )
    decision = SelectField(
        "Décision",
        choices=[("accept", "Accepter"), ("revise", "Réviser"), ("reject", "Rejeter")],
        validators=[DataRequired()]
    )
    submit = SubmitField("Soumettre la relecture")


class MultiCheckboxField(SelectMultipleField):
    """Champ personnalisé pour les cases à cocher multiples."""
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

class UserSpecialitesForm(FlaskForm):
    """Formulaire pour choisir les spécialités d'un utilisateur."""
    
    def __init__(self, *args, **kwargs):
        super(UserSpecialitesForm, self).__init__(*args, **kwargs)
        # Remplir dynamiquement les choix depuis DEFAULT_THEMATIQUES
        self.specialites.choices = [
            (them['code'], f"{them['nom']} ({them['code']})") 
            for them in ThematiqueHelper.get_all()
        ]
    
    specialites = MultiCheckboxField(
        'Spécialités',
        validators=[Optional()],
        coerce=str
    )
    
    submit = SubmitField('Enregistrer')


class CreateAffiliationForm(FlaskForm):
    """Formulaire pour créer une nouvelle affiliation."""
    sigle = StringField('Sigle', validators=[DataRequired(), Length(max=20)])
    nom_complet = StringField('Nom complet', validators=[DataRequired(), Length(max=200)])
    adresse = TextAreaField('Adresse', validators=[Optional()])
    submit = SubmitField('Créer l\'affiliation')
    
    def validate_sigle(self, sigle):
        """Vérifie que le sigle n'existe pas déjà."""
        existing = Affiliation.query.filter_by(sigle=sigle.data.upper()).first()
        if existing:
            raise ValidationError('Ce sigle existe déjà.')






class SubmitResumeForm(FlaskForm):
    """Formulaire pour soumettre un résumé."""
    title = StringField('Titre', validators=[DataRequired(), Length(max=200)])
    abstract = TextAreaField('Résumé', validators=[DataRequired()])
    keywords = StringField('Mots-clés', validators=[Optional(), Length(max=500)])
    
    def __init__(self, *args, **kwargs):
        super(SubmitResumeForm, self).__init__(*args, **kwargs)
        # Choix dynamiques pour les thématiques
        self.thematiques.choices = [
            (them['code'], f"{them['code']} - {them['nom']}") 
            for them in ThematiqueHelper.get_all()
        ]
    
    thematiques = MultiCheckboxField(
        'Thématiques',
        validators=[DataRequired(message="Sélectionnez au moins une thématique")],
        coerce=str
    )
    
    resume_file = FileField(
        'Fichier résumé (PDF)',
        validators=[
            FileRequired(),
            FileAllowed(['pdf'], 'Seuls les fichiers PDF sont autorisés')
        ]
    )
    
    submit = SubmitField('Soumettre le résumé')

class SubmitArticleForm(FlaskForm):
    """Formulaire pour soumettre un article."""
    article_file = FileField(
        'Fichier article (PDF)',
        validators=[
            FileRequired(),
            FileAllowed(['pdf'], 'Seuls les fichiers PDF sont autorisés')
        ]
    )
    
    submit = SubmitField('Soumettre l\'article')

class SubmitPosterForm(FlaskForm):
    """Formulaire pour soumettre un poster."""
    poster_file = FileField(
        'Fichier poster (PDF)',
        validators=[
            FileRequired(),
            FileAllowed(['pdf'], 'Seuls les fichiers PDF sont autorisés')
        ]
    )
    
    submit = SubmitField('Soumettre le poster')



class PhotoUploadForm(FlaskForm):
    """Formulaire pour uploader des photos dans la galerie."""
    
    # Import nécessaire pour PhotoCategory
    def __init__(self, *args, **kwargs):
        super(PhotoUploadForm, self).__init__(*args, **kwargs)
        from .models import PhotoCategory
        # Choix dynamiques pour les catégories
        self.category.choices = [
            (cat.value, cat.value.replace('_', ' ').title()) 
            for cat in PhotoCategory
        ]
    
    photo_file = FileField(
        'Photo',
        validators=[
            FileRequired('Veuillez sélectionner une photo'),
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Formats autorisés : JPG, JPEG, PNG, GIF')
        ],
        description='Formats acceptés : JPG, JPEG, PNG, GIF (max 10 MB)'
    )
    
    description = TextAreaField(
        'Description',
        validators=[Optional(), Length(max=500)],
        description='Description optionnelle de la photo (max 500 caractères)'
    )
    
    category = SelectField(
        'Catégorie',
        validators=[DataRequired('Veuillez choisir une catégorie')],
        choices=[],  # Sera rempli dynamiquement
        description='Catégorie pour organiser la galerie'
    )
    
    submit = SubmitField('Ajouter la photo')


class PhotoEditForm(FlaskForm):
    """Formulaire pour modifier une photo existante."""
    
    def __init__(self, *args, **kwargs):
        super(PhotoEditForm, self).__init__(*args, **kwargs)
        from .models import PhotoCategory
        # Choix dynamiques pour les catégories
        self.category.choices = [
            (cat.value, cat.value.replace('_', ' ').title()) 
            for cat in PhotoCategory
        ]
    
    description = TextAreaField(
        'Description',
        validators=[Optional(), Length(max=500)],
        description='Description de la photo (max 500 caractères)'
    )
    
    category = SelectField(
        'Catégorie',
        validators=[DataRequired('Veuillez choisir une catégorie')],
        choices=[],  # Sera rempli dynamiquement
    )
    
    is_public = BooleanField(
        'Photo publique',
        description='Décochez pour masquer la photo aux autres participants'
    )
    
    submit = SubmitField('Mettre à jour')


class PhotoModerationForm(FlaskForm):
    """Formulaire de modération pour les admins."""
    
    is_approved = BooleanField('Photo approuvée')
    is_public = BooleanField('Photo publique')
    
    moderation_notes = TextAreaField(
        'Notes de modération',
        validators=[Optional(), Length(max=1000)],
        description='Notes internes (non visibles par l\'utilisateur)'
    )
    
    submit = SubmitField('Appliquer la modération')

# ==================== FORMULAIRES ZONE D'ÉCHANGES ====================

class MessageForm(FlaskForm):
    """Formulaire pour créer/modifier un message."""
    
    def __init__(self, *args, **kwargs):
        super(MessageForm, self).__init__(*args, **kwargs)
        from .models import MessageCategory
        # Choix dynamiques pour les catégories
        self.category.choices = [
            (cat.value, self._get_category_label(cat.value)) 
            for cat in MessageCategory
        ]
    
    def _get_category_label(self, category_value):
        """Retourne le label français pour une catégorie."""
        labels = {
            'general': 'Général',
            'technique': 'Technique',
            'logistique': 'Logistique',
            'networking': 'Networking',
            'questions': 'Questions/Aide',
            'annonces': 'Annonces'
        }
        return labels.get(category_value, category_value.title())
    
    title = StringField(
        'Titre',
        validators=[
            DataRequired('Le titre est obligatoire'),
            Length(min=5, max=200, message='Le titre doit faire entre 5 et 200 caractères')
        ],
        description='Titre descriptif pour votre message'
    )
    
    content = TextAreaField(
        'Message',
        validators=[
            DataRequired('Le contenu est obligatoire'),
            Length(min=10, max=5000, message='Le message doit faire entre 10 et 5000 caractères')
        ],
        description='Détaillez votre message (max 5000 caractères)'
    )
    
    category = SelectField(
        'Catégorie',
        validators=[DataRequired('Veuillez choisir une catégorie')],
        choices=[],  # Sera rempli dynamiquement
        description='Choisissez la catégorie la plus appropriée'
    )
    
    topic = StringField(
        'Sujet/Thème (optionnel)',
        validators=[Optional(), Length(max=100)],
        description='Précisez un thème ou sous-sujet (optionnel)'
    )
    
    submit = SubmitField('Publier le message')


class MessageReplyForm(FlaskForm):
    """Formulaire pour répondre à un message."""
    
    content = TextAreaField(
        'Votre réponse',
        validators=[
            DataRequired('La réponse ne peut pas être vide'),
            Length(min=5, max=2000, message='La réponse doit faire entre 5 et 2000 caractères')
        ],
        description='Rédigez votre réponse (max 2000 caractères)'
    )
    
    submit = SubmitField('Répondre')


class MessageEditForm(FlaskForm):
    """Formulaire pour modifier un message existant."""
    
    def __init__(self, *args, **kwargs):
        super(MessageEditForm, self).__init__(*args, **kwargs)
        from .models import MessageCategory
        # Choix dynamiques pour les catégories
        self.category.choices = [
            (cat.value, self._get_category_label(cat.value)) 
            for cat in MessageCategory
        ]
    
    def _get_category_label(self, category_value):
        """Retourne le label français pour une catégorie."""
        labels = {
            'general': 'Général',
            'technique': 'Technique',
            'logistique': 'Logistique',
            'networking': 'Networking',
            'questions': 'Questions/Aide',
            'annonces': 'Annonces'
        }
        return labels.get(category_value, category_value.title())
    
    title = StringField(
        'Titre',
        validators=[
            DataRequired('Le titre est obligatoire'),
            Length(min=5, max=200, message='Le titre doit faire entre 5 et 200 caractères')
        ]
    )
    
    content = TextAreaField(
        'Message',
        validators=[
            DataRequired('Le contenu est obligatoire'),
            Length(min=10, max=5000, message='Le message doit faire entre 10 et 5000 caractères')
        ]
    )
    
    category = SelectField(
        'Catégorie',
        validators=[DataRequired('Veuillez choisir une catégorie')],
        choices=[]  # Sera rempli dynamiquement
    )
    
    topic = StringField(
        'Sujet/Thème (optionnel)',
        validators=[Optional(), Length(max=100)]
    )
    
    is_public = BooleanField(
        'Message public',
        description='Décochez pour rendre le message privé'
    )
    
    submit = SubmitField('Mettre à jour')


class MessageSearchForm(FlaskForm):
    """Formulaire de recherche dans les messages."""
    
    def __init__(self, *args, **kwargs):
        super(MessageSearchForm, self).__init__(*args, **kwargs)
        from .models import MessageCategory
        # Choix dynamiques pour les catégories avec option "Toutes"
        self.category.choices = [('', 'Toutes les catégories')] + [
            (cat.value, self._get_category_label(cat.value)) 
            for cat in MessageCategory
        ]
    
    def _get_category_label(self, category_value):
        """Retourne le label français pour une catégorie."""
        labels = {
            'general': 'Général',
            'technique': 'Technique',
            'logistique': 'Logistique',
            'networking': 'Networking',
            'questions': 'Questions/Aide',
            'annonces': 'Annonces'
        }
        return labels.get(category_value, category_value.title())
    
    query = StringField(
        'Rechercher',
        validators=[
            Optional(),
            Length(min=3, max=100, message='La recherche doit faire au moins 3 caractères')
        ],
        description='Mots-clés à rechercher dans les messages'
    )
    
    category = SelectField(
        'Catégorie',
        validators=[Optional()],
        choices=[]  # Sera rempli dynamiquement
    )
    
    submit = SubmitField('Rechercher')


class MessageModerationForm(FlaskForm):
    """Formulaire de modération pour les admins."""
    
    def __init__(self, *args, **kwargs):
        super(MessageModerationForm, self).__init__(*args, **kwargs)
        from .models import MessageStatus
        # Choix pour les statuts
        self.status.choices = [
            (status.value, self._get_status_label(status.value)) 
            for status in MessageStatus
        ]
    
    def _get_status_label(self, status_value):
        """Retourne le label français pour un statut."""
        labels = {
            'active': 'Actif',
            'archived': 'Archivé',
            'moderated': 'Modéré (masqué)'
        }
        return labels.get(status_value, status_value.title())
    
    status = SelectField(
        'Statut',
        validators=[DataRequired()],
        choices=[]  # Sera rempli dynamiquement
    )
    
    is_pinned = BooleanField('Message épinglé')
    is_public = BooleanField('Message public')
    
    moderation_notes = TextAreaField(
        'Notes de modération',
        validators=[Optional(), Length(max=1000)],
        description='Notes internes (non visibles par l\'utilisateur)'
    )
    
    submit = SubmitField('Appliquer la modération')
