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
    """Envoie un email de réinitialisation de mot de passe."""
    # Cette fonction utilise le système d'email existant de votre app
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    
    subject = "Réinitialisation de votre mot de passe - SFT 2026"
    
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Réinitialisation de mot de passe</h2>
        
        <p>Bonjour {user.full_name},</p>
        
        <p>Vous avez demandé la réinitialisation de votre mot de passe pour votre compte SFT 2026.</p>
        
        <p>Cliquez sur le lien ci-dessous pour créer un nouveau mot de passe :</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" 
               style="background-color: #007bff; color: white; padding: 15px 25px; 
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                Réinitialiser mon mot de passe
            </a>
        </div>
        
        <p><strong>Ce lien expire dans 1 heure.</strong></p>
        
        <p>Si vous n'avez pas demandé cette réinitialisation, vous pouvez ignorer cet email.</p>
        
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #eee;">
        <p style="font-size: 12px; color: #666;">
            SFT 2026 - Congrès Français de Thermique
        </p>
    </div>
    """
    
    # Utiliser la fonction send_email existante de votre application
    from flask import current_app
    current_app.send_email(
        subject=subject,
        recipients=[user.email],
        body="Version texte de l'email",
        html=html_body
    )

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("main.index"))

