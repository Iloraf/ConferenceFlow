from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, Affiliation

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

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("main.index"))
