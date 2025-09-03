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

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import re
import uuid
from .forms import UserSpecialitesForm, CreateAffiliationForm
from .models import db, Communication, SubmissionFile, User, Affiliation, ThematiqueHelper, CommunicationStatus, ReviewAssignment, Review, ReviewRecommendation, Photo, PhotoCategory, Message, MessageCategory, MessageStatus, MessageReaction

main = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(file, file_type, communication_id):
    from flask import current_app
    static_folder = current_app.static_folder 
    if not file or not allowed_file(file.filename):
        raise ValueError("Type de fichier non autorisé")
    
    # Récupérer la communication pour connaître le type
    comm = Communication.query.get(communication_id)
    if not comm:
        raise ValueError("Communication non trouvée")
    
    original_filename = file.filename
    
    # Déterminer le dossier et le préfixe selon le type de communication et de fichier
    if comm.type == 'article':
        base_dir = os.path.join(static_folder, "uploads", "articles")
        if file_type == 'résumé':
            prefix = 'ab'  # abstract
        elif file_type == 'article':
            prefix = 'ar'  # article
        elif file_type == 'poster':
            prefix = 'po'  # poster
        else:
            raise ValueError(f"Type de fichier invalide pour article: {file_type}")
    elif comm.type == 'wip':
        base_dir = os.path.join(static_folder, "uploads", "wip")
        if file_type == 'wip':
            prefix = 'wip'  # work in progress
        elif file_type == 'poster':
            prefix = 'wippo'  # poster pour WIP
        else:
            raise ValueError(f"Type de fichier invalide pour WIP: {file_type}")
    else:
        raise ValueError(f"Type de communication invalide: {comm.type}")
    
    # Créer le dossier si nécessaire
    os.makedirs(base_dir, exist_ok=True)
    
    # Calculer la prochaine version
    last_version = SubmissionFile.query.filter_by(
        communication_id=communication_id, 
        file_type=file_type
    ).order_by(SubmissionFile.version.desc()).first()
    
    next_version = (last_version.version + 1) if last_version else 1
    
    # Générer le nom de fichier : prefix-comm_id-version.pdf
    file_extension = original_filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{prefix}-{communication_id}-{next_version}.{file_extension}"
    
    # Chemin complet
    file_path = os.path.join(base_dir, unique_filename)
    
    # Sauvegarder le fichier
    file.save(file_path)
    file_size = os.path.getsize(file_path)
    
    # Créer l'enregistrement en base
    submission_file = SubmissionFile(
        communication_id=communication_id,
        file_type=file_type,
        filename=unique_filename,
        original_filename=original_filename,
        file_path=file_path,
        version=next_version,
        file_size=file_size
    )
    
    db.session.add(submission_file)
    return submission_file


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        # Mise à jour du profil
        first_name = request.form.get("first_name", current_user.first_name)
        last_name = request.form.get("last_name", current_user.last_name)
        idhal = request.form.get('idhal', '').strip()
        orcid = request.form.get('orcid', '').strip()

        # Validation des champs obligatoires
        if not first_name or not last_name:
            flash('Le prénom et le nom sont obligatoires.', 'error')
            return redirect(url_for('main.profile'))
            
        # Validation ORCID si fourni
        if orcid:
            orcid_pattern = r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$'
            if not re.match(orcid_pattern, orcid):
                flash('Format ORCID invalide. Utilisez le format : 0000-0000-0000-0000', 'error')
                return redirect(url_for('main.profile'))
            
        # Validation IDHAL si fourni
        if idhal:
            idhal_pattern = r'^[a-zA-Z0-9\-]+$'
            if not re.match(idhal_pattern, idhal):
                flash('L\'IDHAL ne peut contenir que des lettres, chiffres et tirets.', 'error')
                return redirect(url_for('main.profile'))
            
        # Vérification de l'unicité ORCID si fourni
        if orcid:
            existing_user = User.query.filter(
                User.orcid == orcid, 
                User.id != current_user.id
            ).first()
            if existing_user:
                flash('Cet ORCID est déjà utilisé par un autre utilisateur.', 'error')
                return redirect(url_for('main.profile'))
            
        # Vérification de l'unicité IDHAL si fourni
        if idhal:
            existing_user = User.query.filter(
                User.idhal == idhal, 
                User.id != current_user.id
            ).first()
            if existing_user:
                flash('Cet IDHAL est déjà utilisé par un autre utilisateur.', 'error')
                return redirect(url_for('main.profile'))
            
        # Mise à jour des informations utilisateur
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.idhal = idhal if idhal else None
        current_user.orcid = orcid if orcid else None

        
        # Gestion des affiliations MULTIPLES
        affiliations_ids = request.form.getlist("affiliations")  # Récupère une liste
        current_user.affiliations.clear()  # Vide les affiliations actuelles
        
        for aff_id in affiliations_ids:
            if aff_id:  # Si l'ID n'est pas vide
                affiliation = Affiliation.query.get(aff_id)
                if affiliation:
                    current_user.affiliations.append(affiliation)
        
        # Changement de mot de passe (inchangé)
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        if current_password and new_password:
            if current_user.check_password(current_password):
                if new_password == confirm_password:
                    current_user.set_password(new_password)
                    flash("Mot de passe modifié avec succès.", "success")
                else:
                    flash("Les mots de passe ne correspondent pas.", "danger")
            else:
                flash("Mot de passe actuel incorrect.", "danger")
                
        db.session.commit()
        flash("Profil mis à jour.", "success")
        return redirect(url_for("main.profile"))
        
    # Récupérer les affiliations pour le formulaire
    #    affiliations = Affiliation.query.filter_by(is_active=True).all()
    affiliations = Affiliation.query.filter_by(is_active=True).order_by(Affiliation.sigle).all()
    return render_template("profile.html", affiliations=affiliations)

@main.route("/create-affiliation", methods=["GET", "POST"])
@login_required
def create_affiliation():
    """Permet de créer une nouvelle affiliation."""
    form = CreateAffiliationForm()
    
    if form.validate_on_submit():
        # Créer la nouvelle affiliation
        affiliation = Affiliation(
            sigle=form.sigle.data.upper(),
            nom_complet=form.nom_complet.data,
            adresse=form.adresse.data if form.adresse.data else None,
            is_active=True
        )
        
        db.session.add(affiliation)
        db.session.commit()
        
        flash(f'Affiliation "{affiliation.sigle}" créée avec succès !', 'success')
        return redirect(url_for('main.profile'))
    
    return render_template('create_affiliation.html', form=form)

@main.route("/mes-communications")
@login_required
def mes_communications():
    comms = Communication.query.join(Communication.authors).filter(
        User.id == current_user.id
    ).order_by(Communication.created_at.desc()).all()
    
    result = []
    for comm in comms:
        latest_files = {}
        for file_type in ['article', 'wip', 'poster']:
            latest_file = comm.get_latest_file(file_type)
            if latest_file:
                latest_files[file_type] = latest_file
        result.append((comm, latest_files))
    
    return render_template("mes_communications.html", communications=result)

@main.route("/soumettre", methods=["GET", "POST"])
@login_required
def choose_type():
    if request.method == "POST":
        type_choice = request.form.get("type")
        if type_choice not in ['article', 'wip']:
            flash("Type invalide.", "danger")
            return redirect(url_for("main.choose_type"))
        return redirect(url_for("main.start_submission", type=type_choice))
    
    return render_template("choose_type.html")


@main.route("/soumettre/<type>", methods=["GET", "POST"])
@login_required
def start_submission(type):
    if type not in ['article', 'wip']:
        flash("Type invalide.", "danger")
        return redirect(url_for("main.choose_type"))
        
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        thematiques = request.form.getlist("thematique")
        coauthors = request.form.getlist("coauthors")
        file = request.files.get("file")
        hal_authorization = bool(request.form.get("hal_authorization"))

        # Validations
        if not title:
            flash("Titre obligatoire.", "danger")
            return redirect(url_for("main.start_submission", type=type))
        
        if not thematiques:
            flash("Sélectionnez une thématique.", "danger")
            return redirect(url_for("main.start_submission", type=type))
        
        # Vérification du fichier obligatoire
        if not file or not file.filename:
            file_type_name = 'résumé' if type == 'article' else 'work in progress'
            flash(f"Le fichier {file_type_name} est obligatoire.", "danger")
            return redirect(url_for("main.start_submission", type=type))
        
        try:
            # Déterminer le statut initial selon le type
            initial_status = CommunicationStatus.RESUME_SOUMIS if type == 'article' else CommunicationStatus.WIP_SOUMIS
            
            comm = Communication(
                title=title,
                #abstract=None,
                type=type,
                status=initial_status,
                hal_authorization=hal_authorization,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
            # Assigner les thématiques
            comm.set_thematiques(thematiques)
            
            db.session.add(comm)
            db.session.flush()
            # Ajouter l'auteur principal
            comm.authors.append(current_user)
            
            # Traiter les co-auteurs
            for coauthor_value in coauthors:
                if coauthor_value.startswith('new:'):
                    # Nouvel auteur ajouté via le modal
                    _, email, first_name, last_name = coauthor_value.split(':')
                    
                    # Vérifier si l'utilisateur existe déjà
                    existing_user = User.query.filter_by(email=email).first()
                    if existing_user:
                        # L'utilisateur existe déjà
                        comm.authors.append(existing_user)
                        user_to_notify = existing_user
                        is_new_user = False
                    else:
                        # Vraiment nouveau utilisateur
                        new_user = User(
                            email=email,
                            first_name=first_name if first_name else None,
                            last_name=last_name if last_name else None,
                            is_active=True,
                            is_activated=False,
                            created_at=datetime.utcnow()
                        )
                        new_user.password_hash = 'PENDING_ACTIVATION'
                        token = new_user.generate_activation_token()
                        
                        db.session.add(new_user)
                        db.session.flush()
                        comm.authors.append(new_user)
                        user_to_notify = new_user
                        is_new_user = True
                else:
                    # Auteur existant sélectionné dans la liste
                    existing_user = User.query.get(int(coauthor_value))
                    if existing_user:
                        comm.authors.append(existing_user)
                        user_to_notify = existing_user
                        is_new_user = False
                    else:
                        continue  # Skip si utilisateur non trouvé
    
                # Envoyer l'email approprié
                try:
                    if is_new_user:
                        current_app.send_coauthor_notification_email(user_to_notify, comm, token)
                        print(f"✅ Email activation envoyé à {user_to_notify.email}")
                    else:
                        current_app.send_existing_coauthor_notification_email(user_to_notify, comm)
                        print(f"✅ Email notification envoyé à {user_to_notify.email}")
                except Exception as e:
                    print(f"❌ Erreur envoi email à {user_to_notify.email}: {e}")
            # Traiter le fichier (maintenant obligatoire)
            file_type = 'résumé' if type == 'article' else 'wip'
            submission_file = save_file(file, file_type, comm.id)
            db.session.commit()
            
            try:
                current_app.send_submission_confirmation_email(comm, file_type, submission_file)
                flash(f"Communication créée avec fichier {file_type}. Email de confirmation envoyé.", "success")
            except Exception as e:
                # Ne pas faire échouer la soumission si l'email échoue
                current_app.logger.error(f"Erreur envoi email confirmation: {e}")
                flash(f"Communication créée avec fichier {file_type}. Erreur envoi email.", "warning")
            
            return redirect(url_for("main.update_submission", comm_id=comm.id))


            
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
    
    # GET : Récupérer tous les utilisateurs pour la sélection
    users = User.query.filter(User.id != current_user.id).order_by(User.last_name, User.first_name).all()
    
    return render_template("submit_abstract.html", 
                         type=type, 
                         all_thematiques=ThematiqueHelper.get_all(),
                         users=users)

@main.route("/soumission/<int:comm_id>", methods=["GET", "POST"])
@login_required
def update_submission(comm_id):
    comm = Communication.query.get_or_404(comm_id)
    
    if current_user not in comm.authors:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.mes_communications"))
    
    if request.method == "POST":
        file_type = request.form.get("file_type")
        file = request.files.get("file")
        
        # Déterminer les types de fichiers autorisés selon le type de communication
        if comm.type == 'article':
            allowed_types = ['résumé', 'article', 'poster']
        elif comm.type == 'wip':
            allowed_types = ['wip', 'poster']
        else:
            allowed_types = []
        
        if not file_type or file_type not in allowed_types:
            flash(f"Type de fichier invalide. Types autorisés: {', '.join(allowed_types)}", "danger")
            return redirect(url_for("main.update_submission", comm_id=comm.id))
        
        # Vérifier si on peut uploader ce type de fichier
        if not comm.can_upload_file_type(file_type):
            flash(f"Vous ne pouvez pas uploader un fichier {file_type} dans l'état actuel.", "warning")
            return redirect(url_for("main.update_submission", comm_id=comm.id))
        
        if not file or not file.filename:
            flash("Sélectionnez un fichier.", "danger")
            return redirect(url_for("main.update_submission", comm_id=comm.id))
        
        try:
            submission_file = save_file(file, file_type, comm.id)
            
 # Faire avancer le statut selon le nouveau système
            new_status = comm.get_next_status_after_upload(file_type)
            status_changed = new_status != comm.status
            
            if status_changed:
                comm.status = new_status
                
                # Mettre à jour les dates selon le type
                if file_type == 'résumé':
                    comm.resume_submitted_at = datetime.utcnow()
                elif file_type == 'article':
                    comm.article_submitted_at = datetime.utcnow()
                elif file_type == 'poster':
                    comm.poster_submitted_at = datetime.utcnow()
            
            comm.updated_at = datetime.utcnow()
            db.session.commit()
            
            notification_type = file_type if status_changed else 'revision'
            
            try:
                if status_changed:
                    # Premier dépôt de ce type
                    current_app.send_submission_confirmation_email(comm, file_type, submission_file)
                    flash(f"Fichier {file_type} ajouté (v{submission_file.version}). Email de confirmation envoyé.", "success")
                else:
                    # Révision/mise à jour
                    current_app.send_submission_confirmation_email(comm, 'revision', submission_file)
                    flash(f"Fichier {file_type} révisé (v{submission_file.version}). Email de confirmation envoyé.", "success")
            except Exception as e:
                # Ne pas faire échouer la soumission si l'email échoue
                current_app.logger.error(f"Erreur envoi email confirmation: {e}")
                flash(f"Fichier {file_type} ajouté (v{submission_file.version}). Erreur envoi email.", "warning")
           
        except ValueError as e:
            flash(str(e), "danger")
        
        return redirect(url_for("main.update_submission", comm_id=comm.id))
    
    # Déterminer les types de fichiers selon le type de communication
    if comm.type == 'article':
        file_types = ['résumé', 'article', 'poster']
    elif comm.type == 'wip':
        file_types = ['wip', 'poster']
    else:
        file_types = []
    
    files_by_type = {}
    for file_type in file_types:
        files_by_type[file_type] = SubmissionFile.query.filter_by(
            communication_id=comm.id, 
            file_type=file_type
        ).order_by(SubmissionFile.version.desc()).all()
    
    return render_template("update_submission.html", 
                         comm=comm, 
                         files_by_type=files_by_type,
                         allowed_uploads={ft: comm.can_upload_file_type(ft) for ft in file_types})

@main.route("/download-file/<int:file_id>")
def download_file(file_id):
    file = SubmissionFile.query.get_or_404(file_id)
    
    if not os.path.exists(file.file_path):
        flash("Fichier non trouvé.", "danger")
        return redirect(url_for("main.index"))
    
    return send_file(file.file_path, 
                    as_attachment=True, 
                    download_name=file.filename)

@main.route("/delete-communication/<int:comm_id>", methods=["POST"])
@login_required
def delete_communication(comm_id):
    comm = Communication.query.get_or_404(comm_id)
    
    if current_user not in comm.authors:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.mes_communications"))

    for file in comm.submission_files:
        if os.path.exists(file.file_path):
            os.remove(file.file_path)
    
    if comm.qr_code_path and os.path.exists(comm.qr_code_path):
        os.remove(comm.qr_code_path)
    
    db.session.delete(comm)
    db.session.commit()
    flash("Communication supprimée.", "success")
    return redirect(url_for("main.mes_communications"))



@main.route('/profile/specialites', methods=['GET', 'POST'])
@login_required
def edit_specialites():
    """Permet à un utilisateur de modifier ses spécialités."""
    form = UserSpecialitesForm()
    
    if form.validate_on_submit():
        # Récupérer les codes sélectionnés
        selected_codes = form.specialites.data
        
        # Valider les codes (sécurité)
        valid_codes = [code for code in selected_codes if ThematiqueHelper.is_valid_code(code)]
        
        # Assigner au user
        current_user.set_specialites(valid_codes)
        db.session.commit()
        
        flash(f'{len(valid_codes)} spécialités enregistrées', 'success')
        return redirect(url_for('main.profile'))
    
    # Pré-remplir le formulaire avec les spécialités actuelles
    if request.method == 'GET':
        current_codes = current_user.specialites_codes.split(',') if current_user.specialites_codes else []
        form.specialites.data = current_codes
    
    return render_template('edit_specialites.html', form=form)

@main.route('/activate/<token>', methods=['GET', 'POST'])
def activate_account(token):
    """Page d'activation du compte reviewer."""
    # Trouver l'utilisateur avec ce token
    user = User.query.filter_by(activation_token=token).first()
    
    if not user or not user.is_activation_token_valid(token):
        flash('Lien d\'activation invalide ou expiré.', 'danger')
        return redirect(url_for('main.index'))
    
    if user.is_activated:
        flash('Ce compte est déjà activé.', 'info')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or len(password) < 8:
            flash('Le mot de passe doit contenir au moins 8 caractères.', 'danger')
        elif password != confirm_password:
            flash('Les mots de passe ne correspondent pas.', 'danger')
        else:
            # Activer le compte
            user.set_password(password)
            user.is_activated = True
            user.activation_token = None  # Supprimer le token
            db.session.commit()
            
            flash('Compte activé avec succès ! Vous pouvez maintenant vous connecter.', 'success')
            return redirect(url_for('auth.login'))
    
    return render_template('activate_account.html', user=user)

@main.context_processor
def inject_thematique_helpers():
    """Injecte les helpers dans tous les templates."""
    def get_thematique_by_code(code):
        return ThematiqueHelper.get_by_code(code)
    
    return dict(get_thematique_by_code=get_thematique_by_code)


@main.route('/reviewer/dashboard')
@login_required
def reviewer_dashboard():
    """Tableau de bord pour les reviewers."""
    if not current_user.is_reviewer:
        flash('Accès réservé aux reviewers.', 'danger')
        return redirect(url_for('main.index'))
    
    # Récupérer les assignations du reviewer
    assignments = ReviewAssignment.query.filter_by(
        reviewer_id=current_user.id
    ).order_by(ReviewAssignment.assigned_at.desc()).all()
    
    pending_reviews = []
    completed_reviews = []
    declined_reviews = []

    for assignment in assignments:
        # Récupérer l'objet Review associé
        review = Review.query.filter_by(
            communication_id=assignment.communication_id,
            reviewer_id=current_user.id
        ).first()
    
        assignment_data = {
            'assignment': assignment,
            'review': review,
            'communication': assignment.communication
        }
    
        # Vérifier si la review a été refusée
        if hasattr(assignment, 'declined') and assignment.declined:
            declined_reviews.append(assignment_data)
        elif review and review.completed:
            completed_reviews.append(assignment_data)
        else:
            pending_reviews.append(assignment_data)

    return render_template('reviewer_dashboard.html',
                           pending_reviews=pending_reviews,
                           completed_reviews=completed_reviews,
                           declined_reviews=declined_reviews)


@main.route('/reviewer/review/<int:comm_id>', methods=['GET', 'POST'])
@login_required
def submit_review(comm_id):
    """Page pour soumettre/modifier une review."""
    if not current_user.is_reviewer:
        flash('Accès réservé aux reviewers.', 'danger')
        return redirect(url_for('main.index'))
    
    # Vérifier que le reviewer est assigné à cette communication
    assignment = ReviewAssignment.query.filter_by(
        communication_id=comm_id,
        reviewer_id=current_user.id
    ).first()
    
    if not assignment:
        flash('Vous n\'êtes pas assigné à cette communication.', 'danger')
        return redirect(url_for('main.reviewer_dashboard'))
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Récupérer ou créer l'objet Review
    review = Review.query.filter_by(
        communication_id=comm_id,
        reviewer_id=current_user.id
    ).first()
    
    if not review:
        review = Review(
            communication_id=comm_id,
            reviewer_id=current_user.id
        )
        db.session.add(review)
        db.session.flush()
    
    if request.method == 'POST':
        # Récupérer les données du formulaire
        score = request.form.get('score')
        recommendation = request.form.get('recommendation')
        comments_for_authors = request.form.get('comments_for_authors', '').strip()
        comments_for_committee = request.form.get('comments_for_committee', '').strip()
        recommend_for_biot_fourier = 'recommend_for_biot_fourier' in request.form
        
        # Validation
        if not score or not recommendation:
            flash('Score et recommandation sont obligatoires.', 'danger')
            return redirect(url_for('main.submit_review', comm_id=comm_id))
        
        try:
            score = int(score)
            if score < 0 or score > 10:
                raise ValueError("Score invalide")
        except ValueError:
            flash('Score doit être un nombre entre 0 et 10.', 'danger')
            return redirect(url_for('main.submit_review', comm_id=comm_id))
        
        # Gérer le fichier de review
        review_file = request.files.get('review_file')
        if review_file and review_file.filename:
            try:
                # Sauvegarder le fichier de review
                review_file_path = save_review_file(review_file, comm_id, current_user.id)
                review.review_file_path = review_file_path
            except ValueError as e:
                flash(str(e), 'danger')
                return redirect(url_for('main.submit_review', comm_id=comm_id))
        
        # Mettre à jour la review
        review.score = score
        review.recommendation = ReviewRecommendation(recommendation)
        review.comments_for_authors = comments_for_authors or None
        review.comments_for_committee = comments_for_committee or None
        review.recommend_for_biot_fourier = recommend_for_biot_fourier
        review.submitted_at = datetime.utcnow()
        review.completed = True
        
        # Mettre à jour l'assignation
        assignment.status = 'completed'
        assignment.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Review soumise avec succès !', 'success')
        return redirect(url_for('main.reviewer_dashboard'))
    
    return render_template('submit_review.html',
                         communication=communication,
                         assignment=assignment,
                         review=review)

def save_review_file(file, communication_id, reviewer_id):
    """Sauvegarde un fichier de review."""
    if not allowed_file(file.filename):
        raise ValueError("Type de fichier non autorisé")
    
    from flask import current_app
    static_folder = current_app.static_folder
    
    # Dossier pour les fichiers de review
    base_dir = os.path.join(static_folder, "uploads", "reviews")
    os.makedirs(base_dir, exist_ok=True)
    
    # Nom du fichier : review-comm_id-reviewer_id.extension
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    filename = f"review-{communication_id}-{reviewer_id}.{file_extension}"
    
    file_path = os.path.join(base_dir, filename)
    file.save(file_path)
    
    return file_path

@main.route('/reviewer/assignment/<int:assignment_id>/decline', methods=['GET', 'POST'])
@login_required
def decline_review_assignment(assignment_id):
    """Permet au reviewer de refuser une assignation de review."""
    if not current_user.is_reviewer:
        flash('Accès réservé aux reviewers.', 'danger')
        return redirect(url_for('main.index'))
    
    assignment = ReviewAssignment.query.get_or_404(assignment_id)
    
    # Vérifier que c'est bien son assignation
    if assignment.reviewer_id != current_user.id:
        flash('Vous ne pouvez pas refuser cette review.', 'danger')
        return redirect(url_for('main.reviewer_dashboard'))
    
    # Vérifier qu'elle n'est pas déjà refusée ou terminée
    if assignment.declined:
        flash('Cette review a déjà été refusée.', 'info')
        return redirect(url_for('main.reviewer_dashboard'))
    
    if assignment.status == 'completed':
        flash('Cette review est déjà terminée.', 'warning')
        return redirect(url_for('main.reviewer_dashboard'))
    
    if request.method == 'POST':
        reason = request.form.get('reason')
        other_reason = request.form.get('other_reason', '').strip()
        
        # Validation
        valid_reasons = ['conflict', 'workload', 'expertise', 'unavailable', 'other']
        if reason not in valid_reasons:
            flash('Raison de refus invalide.', 'danger')
            return redirect(url_for('main.decline_review_assignment', assignment_id=assignment_id))
        
        if reason == 'other' and not other_reason:
            flash('Veuillez préciser la raison du refus.', 'danger')
            return redirect(url_for('main.decline_review_assignment', assignment_id=assignment_id))
        
        try:
            # Refuser la review
            assignment.decline_review(reason, other_reason)
            db.session.commit()
            
            # Notifier l'admin (optionnel)
            try:
                print(f"🔍 DEBUG: Tentative d'envoi d'email pour assignment {assignment.id}")
                from .emails import send_review_decline_notification
                send_review_decline_notification(assignment, reason, other_reason)
                print(f"✅ DEBUG: Email envoyé avec succès")
            except Exception as e:
                print(f"❌ DEBUG: Erreur notification refus: {e}")
                current_app.logger.error(f"Erreur notification refus: {e}")
            
            flash('Review refusée. L\'équipe organisatrice a été notifiée.', 'success')
            return redirect(url_for('main.reviewer_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur refus review: {e}")
            flash('Erreur lors du refus de la review.', 'danger')
    
    # GET : Afficher le formulaire de refus
    return render_template('reviewer/decline_review.html', 
                         assignment=assignment,
                         communication=assignment.communication)

@main.route('/api/push-subscription_legacy', methods=['POST'])
@login_required
def save_push_subscription():
    """Sauvegarde l'abonnement aux notifications push."""
    try:
        data = request.get_json()
        current_app.logger.info(f"Données reçues pour abonnement: {data}") 

        
        if not data or 'subscription' not in data:
            return jsonify({'error': 'Données d\'abonnement manquantes'}), 400
        
        from .models import PushSubscription
        
        # Vérifier si un abonnement existe déjà pour cet utilisateur
        existing = PushSubscription.query.filter_by(user_id=current_user.id).first()
        
        if existing:
            # Mettre à jour l'abonnement existant
            subscription_info = data['subscription']
            existing.endpoint = subscription_info['endpoint']
            existing.p256dh_key = subscription_info['keys']['p256dh']
            existing.auth_key = subscription_info['keys']['auth']
            existing.last_seen = datetime.utcnow()
            existing.is_active = True
            existing.user_agent = data.get('userAgent', '')
        else:
            # Créer un nouvel abonnement
            subscription_info = data['subscription']
            new_subscription = PushSubscription(
                user_id=current_user.id,
                endpoint=subscription_info['endpoint'],
                p256dh_key=subscription_info['keys']['p256dh'],
                auth_key=subscription_info['keys']['auth'],
                user_agent=data.get('userAgent', '')
            )
            db.session.add(new_subscription)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur sauvegarde abonnement: {e}")
        return jsonify({'error': str(e)}), 500
    
@main.route('/manifest.json')
def manifest():
    """Génère dynamiquement le manifest.json PWA à partir de conference.yml"""
    
    try:
        # Récupérer les infos depuis conference.yml
        config = current_app.conference_config
        conference_info = config.get('conference', {})
        
        # Nom de l'app à partir de conference.yml
        app_name = conference_info.get('short_name', 'Conference Flow')
        name = conference_info.get('name', 'Conference Flow')
        theme_color = conference_info.get('theme_color', '#007bff')
        
        # Construire le manifest dynamiquement
        manifest_data = {
            "name": name,
            "short_name": app_name,
            "description": f"Application mobile pour {name}",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": theme_color,
            "orientation": "portrait-primary",
            "scope": "/",
            "lang": "fr",
            "categories": ["education", "productivity"],
            "icons": [
                {
                    "src": "/static/icons/icon-192x192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icons/icon-512x512.png", 
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any"
                },
                {
                    "src": "/static/icons/badge-72x72.png",
                    "sizes": "72x72", 
                    "type": "image/png",
                    "purpose": "monochrome"
                }
            ],
            "shortcuts": [
                {
                    "name": "Programme",
                    "short_name": "Programme",
                    "description": "Voir le programme de la conférence",
                    "url": "/conference/programme",
                    "icons": [{"src": "/static/icons/icon-192x192.png", "sizes": "192x192"}]
                },
                {
                    "name": "Mes communications", 
                    "short_name": "Communications",
                    "description": "Gérer mes communications",
                    "url": "/mes-communications",
                    "icons": [{"src": "/static/icons/icon-192x192.png", "sizes": "192x192"}]
                }
            ],
            # Configuration des notifications push
            "gcm_sender_id": "103953800507",  # ID générique pour les notifications
            "permissions": [
                "notifications"
            ],
            # Métadonnées additionnelles
            "prefer_related_applications": False,
            "edge_side_panel": {
                "preferred_width": 400
            }
        }
        
        response = jsonify(manifest_data)
        response.headers['Content-Type'] = 'application/manifest+json'
        response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache 24h
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération manifest.json: {e}")
        
        # Manifest de fallback
        fallback_manifest = {
            "name": "Conference Flow",
            "short_name": "ConferenceFlow",
            "description": "Application de gestion de conférence",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#007bff",
            "icons": [
                {
                    "src": "/static/icons/icon-192x192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                }
            ]
        }
        
        response = jsonify(fallback_manifest)
        response.headers['Content-Type'] = 'application/manifest+json'
        return response

@main.route('/sw.js')
def service_worker():
    return current_app.send_static_file('sw.js')



# ==================== ROUTES GALERIE PHOTOS ====================

@main.route("/galerie")
def galerie():
    """Affiche la galerie photos publique."""
    from .models import Photo, PhotoCategory
    
    # Récupérer les photos par catégorie
    photos_by_category = {}
    for category in PhotoCategory:
        photos = Photo.get_by_category(category)
        if photos:
            photos_by_category[category] = photos
    
    # Photos récentes pour la section "À la une"
    recent_photos = Photo.get_recent(limit=8)
    
    return render_template("galerie/index.html", 
                         photos_by_category=photos_by_category,
                         recent_photos=recent_photos,
                         categories=PhotoCategory)

@main.route("/galerie/ajouter", methods=["GET", "POST"])
@login_required
def ajouter_photo():
    """Permet aux participants d'ajouter des photos."""
    from .forms import PhotoUploadForm
    from .models import Photo, PhotoCategory
    
    form = PhotoUploadForm()
    
    if form.validate_on_submit():
        try:
            photo_file = form.photo_file.data
            
            # Validation de la taille du fichier (10 MB max)
            if photo_file.content_length and photo_file.content_length > 10 * 1024 * 1024:
                flash("La photo est trop voluminuse (maximum 10 MB).", "danger")
                return render_template("galerie/ajouter.html", form=form)
            
            # Sauvegarder le fichier
            photo = save_photo_file(
                file=photo_file,
                user_id=current_user.id,
                description=form.description.data,
                category=form.category.data
            )
            
            flash("Photo ajoutée avec succès à la galerie !", "success")
            return redirect(url_for("main.galerie"))
            
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Erreur upload photo: {e}")
            flash("Erreur lors de l'upload de la photo.", "danger")
    
    return render_template("galerie/ajouter.html", form=form)

@main.route("/galerie/mes-photos")
@login_required
def mes_photos():
    """Affiche les photos de l'utilisateur connecté."""
    from .models import Photo
    
    photos = Photo.query.filter_by(user_id=current_user.id)\
                       .order_by(Photo.created_at.desc()).all()
    
    return render_template("galerie/mes_photos.html", photos=photos)

@main.route("/galerie/photo/<int:photo_id>")
def voir_photo(photo_id):
    """Affiche une photo en détail."""
    from .models import Photo
    
    photo = Photo.query.get_or_404(photo_id)
    
    # Vérifier si la photo est visible
    if not photo.is_public or not photo.is_approved:
        if not current_user.is_authenticated or (
            current_user.id != photo.user_id and not current_user.is_admin
        ):
            flash("Cette photo n'est pas accessible.", "danger")
            return redirect(url_for("main.galerie"))
    
    return render_template("galerie/detail.html", photo=photo)

@main.route("/galerie/modifier/<int:photo_id>", methods=["GET", "POST"])
@login_required
def modifier_photo(photo_id):
    """Permet à l'utilisateur de modifier sa photo."""
    from .forms import PhotoEditForm
    from .models import Photo
    
    photo = Photo.query.get_or_404(photo_id)
    
    # Vérifier les permissions
    if not photo.can_be_edited_by(current_user):
        flash("Vous ne pouvez pas modifier cette photo.", "danger")
        return redirect(url_for("main.mes_photos"))
    
    form = PhotoEditForm(obj=photo)
    
    if form.validate_on_submit():
        photo.description = form.description.data
        photo.category = form.category.data
        photo.is_public = form.is_public.data
        photo.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash("Photo mise à jour avec succès !", "success")
        return redirect(url_for("main.mes_photos"))
    
    return render_template("galerie/modifier.html", form=form, photo=photo)

@main.route("/galerie/supprimer/<int:photo_id>", methods=["POST"])
@login_required
def supprimer_photo(photo_id):
    """Permet à l'utilisateur de supprimer sa photo."""
    from .models import Photo
    
    photo = Photo.query.get_or_404(photo_id)
    
    # Vérifier les permissions
    if not photo.can_be_edited_by(current_user):
        flash("Vous ne pouvez pas supprimer cette photo.", "danger")
        return redirect(url_for("main.mes_photos"))
    
    try:
        # Supprimer le fichier physique
        if os.path.exists(photo.file_path):
            os.remove(photo.file_path)
        
        # Supprimer la miniature si elle existe
        thumbnail_path = photo.file_path.replace('/photos/', '/photos/thumbnails/')
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        
        # Supprimer de la base de données
        db.session.delete(photo)
        db.session.commit()
        
        flash("Photo supprimée avec succès.", "success")
    except Exception as e:
        current_app.logger.error(f"Erreur suppression photo {photo_id}: {e}")
        flash("Erreur lors de la suppression de la photo.", "danger")
    
    return redirect(url_for("main.mes_photos"))

@main.route("/galerie/categorie/<category_name>")
def galerie_categorie(category_name):
    """Affiche les photos d'une catégorie spécifique."""
    from .models import Photo, PhotoCategory
    
    # Vérifier que la catégorie existe
    try:
        category = PhotoCategory(category_name)
    except ValueError:
        flash("Catégorie introuvable.", "danger")
        return redirect(url_for("main.galerie"))
    
    photos = Photo.get_by_category(category)
    category_display = category_name.replace('_', ' ').title()
    
    return render_template("galerie/categorie.html", 
                         photos=photos,
                         category=category,
                         category_display=category_display)


# ==================== FONCTIONS UTILITAIRES PHOTOS ====================

# Dans app/routes.py, remplacez complètement la fonction save_photo_file par celle-ci :

def save_photo_file(file, user_id, description=None, category='generale'):
    """Sauvegarde une photo uploadée avec traitement et validation."""
    from .models import Photo, PhotoCategory
    from PIL import Image
    import secrets
    
    if not file or not file.filename:
        raise ValueError("Aucun fichier sélectionné")
    
    # Validation du type de fichier
    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise ValueError(f"Format non autorisé. Utilisez: {', '.join(allowed_extensions)}")
    
    # Générer un nom de fichier unique
    random_hex = secrets.token_hex(8)
    filename = f"photo_{user_id}_{random_hex}.{file_extension}"
    
    # Chemin de sauvegarde - CORRIGÉ
    photos_dir = os.path.join('app', 'static', 'uploads', 'photos')
    os.makedirs(photos_dir, exist_ok=True)
    file_path = os.path.join(photos_dir, filename)
    
    print(f"DEBUG: Sauvegarde dans {file_path}")  # Pour debug
    
    try:
        # Sauvegarder temporairement pour traitement
        file.save(file_path)
        print(f"DEBUG: Fichier sauvé, taille: {os.path.getsize(file_path)} bytes")
        
        # Traitement de l'image avec Pillow
        with Image.open(file_path) as img:
            # Obtenir les dimensions originales
            original_width, original_height = img.size
            print(f"DEBUG: Dimensions originales: {original_width}x{original_height}")
            
            # Redimensionner si trop grande (max 1920x1920)
            max_size = 1920
            if original_width > max_size or original_height > max_size:
                img.thumbnail((max_size, max_size), Image.LANCZOS)
                img.save(file_path, optimize=True, quality=90)
                print(f"DEBUG: Image redimensionnée")
            
            # Créer une miniature
            thumbnail_dir = os.path.join(photos_dir, 'thumbnails')
            os.makedirs(thumbnail_dir, exist_ok=True)
            thumbnail_path = os.path.join(thumbnail_dir, filename)
            
            thumbnail = img.copy()
            thumbnail.thumbnail((300, 300), Image.LANCZOS)
            thumbnail.save(thumbnail_path, optimize=True, quality=85)
            print(f"DEBUG: Miniature créée: {thumbnail_path}")
            
            # Obtenir les nouvelles dimensions
            final_width, final_height = img.size
        
        # Obtenir la taille du fichier final
        file_size = os.path.getsize(file_path)
        print(f"DEBUG: Taille finale: {file_size} bytes")
        
        # Créer l'enregistrement en base
        photo = Photo(
            filename=filename,
            original_name=file.filename,
            description=description,
            category=PhotoCategory(category),
            file_size=file_size,
            mime_type=f"image/{file_extension}",
            width=final_width,
            height=final_height,
            user_id=user_id,
            is_approved=True,  # Approuvé par défaut
            is_public=True
        )
        
        db.session.add(photo)
        db.session.commit()
        
        print(f"DEBUG: Photo enregistrée en base avec ID: {photo.id}")
        return photo
        
    except Exception as e:
        print(f"DEBUG: Erreur - {str(e)}")
        # Nettoyer en cas d'erreur
        if os.path.exists(file_path):
            os.remove(file_path)
        raise ValueError(f"Erreur traitement image: {str(e)}")


# ==================== ROUTES ZONE D'ÉCHANGES/MESSAGES ====================

@main.route("/echanges")
def echanges():
    """Page principale de la zone d'échanges."""
    from .models import Message, MessageCategory, MessageReaction
    from .forms import MessageSearchForm
    
    # Récupérer les messages par catégorie
    messages_by_category = {}
    total_messages = 0
    
    for category in MessageCategory:
        messages = Message.get_by_category(category, limit=5)
        if messages:
            messages_by_category[category] = messages
            total_messages += len(messages)
    
    # Messages récents pour la section "À la une"
    recent_messages = Message.get_recent(limit=6)
    
    # Messages populaires
    popular_messages = Message.get_popular(limit=4, days=7)
    
    # Statistiques
    stats = {
        'total_messages': Message.query.filter_by(status='active').count(),
        'total_categories': len([cat for cat, msgs in messages_by_category.items() if msgs]),
        'total_replies': Message.query.filter(Message.parent_id.isnot(None), 
                                            Message.status == 'active').count(),
        'active_users': db.session.query(Message.user_id).filter_by(status='active').distinct().count()
    }
    
    # Formulaire de recherche
    search_form = MessageSearchForm()
    
    return render_template("echanges/index.html",
                         messages_by_category=messages_by_category,
                         recent_messages=recent_messages,
                         popular_messages=popular_messages,
                         stats=stats,
                         search_form=search_form,
                         categories=MessageCategory)

@main.route("/echanges/nouveau", methods=["GET", "POST"])
@login_required
def nouveau_message():
    """Créer un nouveau message."""
    from .forms import MessageForm
    from .models import Message, MessageCategory, MessageStatus
    
    form = MessageForm()
    
    if form.validate_on_submit():
        try:
            message = Message(
                title=form.title.data,
                content=form.content.data,
                category=MessageCategory(form.category.data),
                topic=form.topic.data if form.topic.data else None,
                user_id=current_user.id,
                status=MessageStatus.ACTIVE,
                is_public=True
            )
            
            db.session.add(message)
            db.session.commit()
            
            flash("Votre message a été publié avec succès !", "success")
            return redirect(url_for("main.voir_message", message_id=message.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur création message: {e}")
            flash("Erreur lors de la publication du message.", "danger")
    
    return render_template("echanges/nouveau.html", form=form)

@main.route("/echanges/message/<int:message_id>")
def voir_message(message_id):
    """Voir un message et ses réponses."""
    from .models import Message, MessageReaction, MessageStatus
    from .forms import MessageReplyForm
    
    message = Message.query.get_or_404(message_id)
    
    # DEBUG: Afficher les infos du message
    #####################################################
    # print(f"🔍 DEBUG - Message {message_id}:")        #
    # print(f"   Titre: {message.title}")               #
    # print(f"   Statut: {message.status}")             #
    # print(f"   Statut value: {message.status.value}") #
    # print(f"   Public: {message.is_public}")          #
    #####################################################
    
    # Vérifier si le message est visible
    if not message.is_public or message.status.value != 'active':
        if not current_user.is_authenticated or (
            current_user.id != message.user_id and not current_user.is_admin
        ):
            flash("Ce message n'est pas accessible.", "danger")
            return redirect(url_for("main.echanges"))
    
    # Incrémenter le compteur de vues
    try:
        message.view_count += 1
        db.session.commit()
    except:
        db.session.rollback()
    
    # CORRIGÉ: Récupérer les réponses avec syntaxe correcte
    print(f"🔍 DEBUG - Recherche réponses pour message {message_id}:")
    
    # Toutes les réponses (pour debug)
    all_replies = Message.query.filter_by(parent_id=message.id).all()
    print(f"   Toutes les réponses: {len(all_replies)}")
    
    # Filtrer manuellement pour éviter les erreurs SQLAlchemy
    replies = []
    for reply in all_replies:
        print(f"      → Reply {reply.id}: statut={reply.status.value}, public={reply.is_public}")
        if reply.status.value == 'active' and reply.is_public:
            replies.append(reply)
    
    print(f"   Réponses actives et publiques: {len(replies)}")
    
    # Trier par date de création
    replies.sort(key=lambda x: x.created_at)
    
    # Formulaire de réponse
    reply_form = MessageReplyForm()
    
    # Réactions du message
    reactions_summary = {}
    if message.reactions:
        from collections import Counter
        reaction_counts = Counter([r.reaction_type for r in message.reactions])
        reactions_summary = dict(reaction_counts)
    
    # Vérifier si l'utilisateur a déjà réagi
    user_reactions = []
    if current_user.is_authenticated:
        user_reactions = [r.reaction_type for r in message.reactions if r.user_id == current_user.id]
    
    print(f"🔍 DEBUG - Envoi au template: {len(replies)} réponses")
    
    return render_template("echanges/detail.html",
                         message=message,
                         replies=replies,
                         reply_form=reply_form,
                         reactions_summary=reactions_summary,
                         user_reactions=user_reactions)

@main.route("/echanges/message/<int:message_id>/repondre", methods=["POST"])
@login_required
def repondre_message(message_id):
    """Répondre à un message."""
    from .forms import MessageReplyForm
    from .models import Message, MessageStatus
    
    parent_message = Message.query.get_or_404(message_id)
    form = MessageReplyForm()
    
    if form.validate_on_submit():
        try:
            reply = Message(
                title=f"Re: {parent_message.title}",
                content=form.content.data,
                category=parent_message.category,
                topic=parent_message.topic,
                user_id=current_user.id,
                parent_id=parent_message.id,
                status=MessageStatus.ACTIVE,
                is_public=True
            )
            
            db.session.add(reply)
            db.session.commit()
            
            flash("Votre réponse a été ajoutée !", "success")
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur ajout réponse: {e}")
            flash("Erreur lors de l'ajout de la réponse.", "danger")
    
    return redirect(url_for("main.voir_message", message_id=message_id))

@main.route("/echanges/mes-messages")
@login_required
def mes_messages():
    """Messages de l'utilisateur connecté."""
    from .models import Message
    
    # Messages créés par l'utilisateur
    messages = Message.query.filter_by(user_id=current_user.id)\
                          .order_by(Message.created_at.desc()).all()
    
    # Séparer messages principaux et réponses
    main_messages = [m for m in messages if not m.is_reply]
    replies = [m for m in messages if m.is_reply]
    
    return render_template("echanges/mes_messages.html", 
                         main_messages=main_messages,
                         replies=replies)

@main.route("/echanges/message/<int:message_id>/modifier", methods=["GET", "POST"])
@login_required
def modifier_message(message_id):
    """Modifier un message."""
    from .forms import MessageEditForm
    from .models import Message
    
    message = Message.query.get_or_404(message_id)
    
    # Vérifier les permissions
    if not message.can_be_edited_by(current_user):
        flash("Vous ne pouvez pas modifier ce message.", "danger")
        return redirect(url_for("main.mes_messages"))
    
    form = MessageEditForm(obj=message)
    
    if form.validate_on_submit():
        try:
            message.title = form.title.data
            message.content = form.content.data
            message.category = form.category.data
            message.topic = form.topic.data if form.topic.data else None
            message.is_public = form.is_public.data
            message.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash("Message mis à jour avec succès !", "success")
            return redirect(url_for("main.voir_message", message_id=message.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur modification message: {e}")
            flash("Erreur lors de la modification.", "danger")
    
    return render_template("echanges/modifier.html", form=form, message=message)

@main.route("/echanges/message/<int:message_id>/supprimer", methods=["POST"])
@login_required
def supprimer_message(message_id):
    """Supprimer un message."""
    from .models import Message
    
    message = Message.query.get_or_404(message_id)
    
    # Vérifier les permissions
    if not message.can_be_deleted_by(current_user):
        flash("Vous ne pouvez pas supprimer ce message.", "danger")
        return redirect(url_for("main.mes_messages"))
    
    try:
        # Si c'est un message principal avec des réponses, on l'archive plutôt que de le supprimer
        if message.replies_count > 0 and not message.is_reply:
            from .models import MessageStatus
            message.status = MessageStatus.ARCHIVED
            message.title = "[Message supprimé]"
            message.content = "Ce message a été supprimé par son auteur."
            db.session.commit()
            flash("Message archivé (conservé car il a des réponses).", "info")
        else:
            # Supprimer complètement si pas de réponses
            db.session.delete(message)
            db.session.commit()
            flash("Message supprimé avec succès.", "success")
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression message {message_id}: {e}")
        flash("Erreur lors de la suppression.", "danger")
    
    return redirect(url_for("main.mes_messages"))

@main.route("/echanges/categorie/<category_name>")
def echanges_categorie(category_name):
    """Messages d'une catégorie spécifique."""
    from .models import Message, MessageCategory
    
    # Vérifier que la catégorie existe
    try:
        category = MessageCategory(category_name)
    except ValueError:
        flash("Catégorie introuvable.", "danger")
        return redirect(url_for("main.echanges"))
    
    # Récupérer les messages de la catégorie
    messages = Message.get_by_category(category)
    
    # Labels français
    category_labels = {
        'general': 'Général',
        'technique': 'Technique', 
        'logistique': 'Logistique',
        'networking': 'Networking',
        'questions': 'Questions/Aide',
        'annonces': 'Annonces'
    }
    category_display = category_labels.get(category_name, category_name.title())
    
    return render_template("echanges/categorie.html",
                         messages=messages,
                         category=category,
                         category_display=category_display)

@main.route("/echanges/rechercher", methods=["GET", "POST"])
def rechercher_messages():
    """Recherche dans les messages."""
    from .forms import MessageSearchForm
    from .models import Message, MessageCategory
    
    form = MessageSearchForm()
    results = []
    
    if form.validate_on_submit():
        query_text = form.query.data
        category = form.category.data if form.category.data else None
        
        try:
            if category:
                category = MessageCategory(category)
            results = Message.search(query_text, category)
        except Exception as e:
            current_app.logger.error(f"Erreur recherche messages: {e}")
            flash("Erreur lors de la recherche.", "danger")
    
    return render_template("echanges/recherche.html", 
                         form=form, 
                         results=results)

@main.route("/echanges/message/<int:message_id>/reaction", methods=["POST"])
@login_required
def toggle_reaction(message_id):
    """Ajouter/retirer une réaction à un message."""
    from .models import Message, MessageReaction
    
    message = Message.query.get_or_404(message_id)
    reaction_type = request.form.get('reaction_type', 'like')
    
    # Vérifier si l'utilisateur a déjà cette réaction
    existing_reaction = MessageReaction.query.filter_by(
        message_id=message_id,
        user_id=current_user.id,
        reaction_type=reaction_type
    ).first()
    
    try:
        if existing_reaction:
            # Retirer la réaction
            db.session.delete(existing_reaction)
            action = 'removed'
        else:
            # Ajouter la réaction
            reaction = MessageReaction(
                message_id=message_id,
                user_id=current_user.id,
                reaction_type=reaction_type
            )
            db.session.add(reaction)
            action = 'added'
        
        db.session.commit()
        
        # Retourner JSON pour AJAX
        if request.is_json:
            # Compter les réactions actuelles
            reaction_counts = {}
            for r in message.reactions:
                reaction_counts[r.reaction_type] = reaction_counts.get(r.reaction_type, 0) + 1
                
            return jsonify({
                'success': True,
                'action': action,
                'reaction_type': reaction_type,
                'counts': reaction_counts
            })
        else:
            flash(f"Réaction {'ajoutée' if action == 'added' else 'supprimée'} !", "success")
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur réaction: {e}")
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        else:
            flash("Erreur lors de l'ajout de la réaction.", "danger")
    
    return redirect(url_for("main.voir_message", message_id=message_id))
