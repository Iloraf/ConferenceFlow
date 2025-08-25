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

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import re
import uuid
from .forms import UserSpecialitesForm, CreateAffiliationForm
from .models import db, Communication, SubmissionFile, User, Affiliation, ThematiqueHelper, CommunicationStatus, ReviewAssignment, Review, ReviewRecommendation

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

@main.route('/api/push-subscription', methods=['POST'])
@login_required
def save_push_subscription():
    """Sauvegarde l'abonnement aux notifications push."""
    try:
        subscription_data = request.get_json()
        
        # Sauvegarder en base (créer table si besoin)
        # PushSubscription.create(user_id=current_user.id, data=subscription_data)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
