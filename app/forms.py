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

# app/forms.py


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
