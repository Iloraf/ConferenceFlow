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

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, Affiliation
import secrets
from datetime import datetime, timedelta

auth = Blueprint("auth", __name__)

@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        if not email or not password:
            flash("Veuillez remplir tous les champs.", "danger")
            return render_template("auth/login.html")
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            flash(f"Bienvenue {user.full_name} !", "success")
            return redirect(url_for('main.index'))
        else:
            flash("Email ou mot de passe incorrect.", "danger")
    
    return render_template("auth/login.html")

@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        # Validation
        if not all([first_name, last_name, email, password]):
            flash("Tous les champs sont obligatoires.", "danger")
            return render_template("auth/register.html")
        
        if User.query.filter_by(email=email).first():
            flash("Cette adresse email est déjà utilisée.", "danger")
            return render_template("auth/register.html")
        
        try:
            user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            flash("Inscription réussie ! Vous pouvez vous connecter.", "success")
            return redirect(url_for("auth.login"))
            
        except Exception as e:
            db.session.rollback()
            flash("Erreur lors de l'inscription.", "danger")
    
    return render_template("auth/register.html")

# NOUVELLES ROUTES POUR LE MOT DE PASSE OUBLIÉ
@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Page pour demander la réinitialisation du mot de passe."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        
        if not email:
            flash("Veuillez saisir votre adresse email.", "danger")
            return render_template("auth/forgot_password.html")
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Générer un token de réinitialisation
            token = secrets.token_urlsafe(32)
            user.reset_password_token = token
            user.reset_password_expires = datetime.utcnow() + timedelta(hours=1)  # Expire dans 1 heure
            db.session.commit()
            
            try:
                # Envoyer l'email (fonction à implémenter)
                send_password_reset_email(user, token)
                flash("Un email de réinitialisation a été envoyé à votre adresse.", "success")
                return redirect(url_for("auth.login"))
            except Exception as e:
                current_app.logger.error(f"Erreur envoi email: {e}")
                flash("Erreur lors de l'envoi de l'email. Veuillez réessayer.", "danger")
        else:
            # Par sécurité, on affiche le même message même si l'email n'existe pas
            flash("Un email de réinitialisation a été envoyé à votre adresse.", "success")
            return redirect(url_for("auth.login"))
    
    return render_template("auth/forgot_password.html")

@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Page pour réinitialiser le mot de passe avec le token."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    
    # Vérifier le token
    user = User.query.filter_by(reset_password_token=token).first()
    
    if not user or not user.reset_password_expires or user.reset_password_expires < datetime.utcnow():
        flash("Lien de réinitialisation invalide ou expiré.", "danger")
        return redirect(url_for("auth.forgot_password"))
    
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        if not password or len(password) < 8:
            flash("Le mot de passe doit contenir au moins 8 caractères.", "danger")
        elif password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "danger")
        else:
            # Mettre à jour le mot de passe
            user.set_password(password)
            user.reset_password_token = None
            user.reset_password_expires = None
            db.session.commit()
            
            flash("Mot de passe réinitialisé avec succès ! Vous pouvez vous connecter.", "success")
            return redirect(url_for("auth.login"))
    
    return render_template("auth/reset_password.html", token=token)

def send_password_reset_email(user, token):
    """Envoie un email de réinitialisation de mot de passe via le système centralisé."""
    try:
        from app.emails import send_any_email_with_themes
        from flask import current_app
        
        # URL de réinitialisation
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        
        # Contexte pour l'email
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'call_to_action_url': reset_url,
            'TOKEN_EXPIRES_HOURS': 1  # Le token expire dans 1 heure
        }
        
        # Envoyer via le système centralisé - utilise automatiquement emails.yml et conference.yml
        send_any_email_with_themes(
            template_name='password_reset',  # Correspondra à password_reset dans emails.yml
            recipient_email=user.email,
            base_context=base_context,
            user=user,
            color_scheme='orange'  # Orange pour les alertes/réinitialisations
        )
        
        current_app.logger.info(f"Email de réinitialisation envoyé à {user.email}")
        
    except Exception as e:
        current_app.logger.error(f"Erreur envoi email de réinitialisation à {user.email}: {str(e)}")
        raise

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("main.index"))

