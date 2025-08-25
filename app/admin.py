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

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from .models import db, Affiliation, Communication, User, ThematiqueHelper, ReviewAssignment, CommunicationStatus, SubmissionFile, Review, HALDeposit
from io import StringIO
import csv
import os
from datetime import datetime, timedelta
import yaml
from pathlib import Path
import shutil



admin = Blueprint("admin", __name__)

@admin.route("/dashboard")
@login_required
def admin_dashboard():
    """Dashboard principal d'administration."""
    if not current_user.is_admin:
        flash("Accès réservé aux administrateurs.", "danger")
        return redirect(url_for("main.index"))
    
    users = User.query.all()
    affiliations_count = Affiliation.query.count()
    pending_reviews = Communication.query.filter_by(status=CommunicationStatus.ARTICLE_SOUMIS).count()
    
    # Compter les fichiers CSV dans le dossier content
    csv_files_count = 0
    try:
        content_dir = Path(current_app.root_path) / "static" / "content"
        if content_dir.exists():
            csv_files_count = len(list(content_dir.glob("*.csv")))
    except Exception as e:
        current_app.logger.error(f"Erreur comptage fichiers CSV: {e}")
    
    # AJOUTER : Statistiques pour les livres
    stats = {
        'articles_count': Communication.query.filter(
            Communication.type == 'article',
            Communication.status == CommunicationStatus.ACCEPTE
        ).count(),
        'resumes_count': Communication.query.filter(
            Communication.type == 'article',
            Communication.status.in_([
                CommunicationStatus.RESUME_SOUMIS,
                CommunicationStatus.ARTICLE_SOUMIS,
                CommunicationStatus.EN_REVIEW,
                CommunicationStatus.ACCEPTE
            ])
        ).count(),
        'wips_count': Communication.query.filter(
            Communication.type == 'wip',
            Communication.status == CommunicationStatus.WIP_SOUMIS
        ).count()
    }

    try:
        
        # Communications éligibles pour HAL
        eligible_communications = Communication.query.filter(
            Communication.status.in_([
                CommunicationStatus.ACCEPTE,
                CommunicationStatus.WIP_SOUMIS,
                CommunicationStatus.POSTER_SOUMIS
            ]),
            Communication.hal_authorization == True
        ).count()
        
        # Statistiques des dépôts
        hal_deposits = HALDeposit.query.all()
        
        hal_stats = {
            'total_communications': eligible_communications,
            'successful_deposits': len([d for d in hal_deposits if d.status == 'success']),
            'failed_deposits': len([d for d in hal_deposits if d.status == 'error']),
            'pending_deposits': len([d for d in hal_deposits if d.status == 'pending'])
        }
    except Exception as e:
        # En cas d'erreur (tables pas encore créées, etc.)
        hal_stats = {
            'total_communications': 0,
            'successful_deposits': 0,
            'failed_deposits': 0,
            'pending_deposits': 0
        }
    

    
    return render_template("admin.html", 
                         users=users,
                         affiliations_count=affiliations_count,
                         pending_reviews=pending_reviews,
                         csv_files_count=csv_files_count,
                         stats=stats, hal_stats=hal_stats)

@admin.route("/users")
@login_required
def manage_users():
    """Page de gestion des utilisateurs."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Recherche et filtres
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')
    
    query = User.query
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                User.email.ilike(search_pattern),
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern)
            )
        )
    
    if role_filter == 'admin':
        query = query.filter(User.is_admin == True)
    elif role_filter == 'reviewer':
        query = query.filter(User.is_reviewer == True)
    elif role_filter == 'user':
        query = query.filter(db.and_(User.is_admin == False, User.is_reviewer == False))
    
    users = query.order_by(User.email).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/manage_users.html', 
                         users=users, 
                         search=search,
                         role_filter=role_filter)

@admin.route("/admin/users/promote-admin/<int:user_id>", methods=["POST"])
@login_required
def promote_admin(user_id):
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))

    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    flash(f"{user.email} promu administrateur", "success")
    return redirect(url_for("admin.manage_users"))

@admin.route("/admin/users/promote-reviewer/<int:user_id>", methods=["POST"])
@login_required
def promote_reviewer(user_id):
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))

    user = User.query.get_or_404(user_id)
    user.is_reviewer = True
    db.session.commit()
    flash(f"{user.email} promu relecteur", "success")
    return redirect(url_for("admin.manage_users"))

@admin.route("/admin/users/revoke-admin/<int:user_id>", methods=["POST"])
@login_required
def revoke_admin(user_id):
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas révoquer vos propres droits d'administrateur", "danger")
        return redirect(url_for("admin.manage_users"))
        
    user.is_admin = False
    db.session.commit()
    flash(f"Droits d'administrateur révoqués pour {user.email}", "success")
    return redirect(url_for("admin.manage_users"))

@admin.route("/admin/users/revoke-reviewer/<int:user_id>", methods=["POST"])
@login_required
def revoke_reviewer(user_id):
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))

    user = User.query.get_or_404(user_id)
    user.is_reviewer = False
    db.session.commit()
    flash(f"Droits de reviewer révoqués pour {user.email}", "success")
    return redirect(url_for("admin.manage_users"))

@admin.route("/admin/reviews")
@login_required
def manage_reviews():
    """Page de gestion des reviews."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    reviewers = User.query.filter_by(is_reviewer=True).all()
    
    return render_template('admin/manage_reviews.html', 
                         reviewers=reviewers)

@admin.route('/admin/reviews/notify-reviewers', methods=['GET', 'POST'])
@login_required
def notify_reviewers():
    """Page pour envoyer des notifications aux reviewers."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
        
    if request.method == 'POST':
        
        flash('Notifications envoyées avec succès !', 'success')
        return redirect(url_for('admin.manage_reviews'))
    
    # Récupérer la liste des reviewers pour affichage
    reviewers = User.query.filter_by(is_reviewer=True).all()
    
    return render_template('admin/notify_reviewers.html', reviewers=reviewers)

@admin.route('/affiliations')
@login_required
def list_affiliations():
    """Liste toutes les affiliations."""
    
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Recherche
    search = request.args.get('search', '').strip()
    
    query = Affiliation.query
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                Affiliation.sigle.ilike(search_pattern),
                Affiliation.nom_complet.ilike(search_pattern),
                Affiliation.adresse.ilike(search_pattern)
            )
        )
    
    affiliations = query.order_by(Affiliation.sigle).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/list_affiliations.html', 
                         affiliations=affiliations, 
                         search=search)

@admin.route('/affiliations/<int:affiliation_id>')
@login_required
def view_affiliation(affiliation_id):
    """Affiche les détails d'une affiliation."""
    
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
        
    affiliation = Affiliation.query.get_or_404(affiliation_id)
    return render_template('admin/view_affiliation.html', affiliation=affiliation)

@admin.route("/admin/export/users")
@login_required
def export_users_csv():
    """Export des utilisateurs en CSV."""
    if not current_user.is_admin:
        flash("Accès réservé aux administrateurs.", "danger")
        return redirect(url_for("main.index"))

    from io import BytesIO
    import csv
    
    # Utiliser BytesIO au lieu de StringIO
    output = BytesIO()
    
    # Créer le contenu CSV en tant que string d'abord
    csv_content = StringIO()
    writer = csv.writer(csv_content)
    writer.writerow([
        "email", "first_name", "last_name", 
        "idhal", "orcid",  # Nouveaux champs HAL
        "is_admin", "is_reviewer", "created_at"
    ])

    users = User.query.all()
    for user in users:
        writer.writerow([
            user.email, 
            user.first_name or "", 
            user.last_name or "", 
            user.idhal or "",        # ID HAL
            user.orcid or "",        # ORCID
            user.is_admin, 
            user.is_reviewer,
            user.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(user, 'created_at') and user.created_at else ""
        ])

    # Convertir en bytes et l'écrire dans BytesIO
    csv_string = csv_content.getvalue()
    output.write(csv_string.encode('utf-8'))
    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="users_export.csv"
    )

@admin.route("/admin/export/affiliations")
@login_required
def export_affiliations_csv():
    """Export des affiliations en CSV avec support des champs HAL."""
    if not current_user.is_admin:
        flash("Accès réservé aux administrateurs.", "danger")
        return redirect(url_for("main.index"))

    from io import BytesIO
    import csv
    
    # Utiliser BytesIO au lieu de StringIO
    output = BytesIO()
    
    # Créer le contenu CSV en tant que string d'abord
    csv_content = StringIO()
    writer = csv.writer(csv_content)
    
    # En-têtes CSV avec les champs HAL
    writer.writerow([
        "sigle", 
        "nom_complet", 
        "adresse", 
        "citation", 
        "struct_id_hal",       # ID structure HAL spécifique  
        "acronym_hal",         # Acronyme HAL
        "type_hal"             # Type HAL
    ])

    affiliations = Affiliation.query.all()
    for affiliation in affiliations:
        writer.writerow([
            affiliation.sigle,
            affiliation.nom_complet,
            affiliation.adresse or "",
            affiliation.citation or "",
            affiliation.struct_id_hal or "",        
            affiliation.acronym_hal or "",          
            affiliation.type_hal or ""              
        ])

    # Convertir en bytes et l'écrire dans BytesIO
    csv_string = csv_content.getvalue()
    output.write(csv_string.encode('utf-8'))
    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="affiliations_export.csv"
    )

@admin.route("/admin/settings")
@login_required
def system_settings():
    """Page des paramètres système."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    return render_template('admin/system_settings.html')

def process_affiliations_csv(file):
    """Traite le fichier CSV des affiliations avec support des nouveaux champs HAL."""
    
    results = {
        'success': 0,
        'updated': 0,
        'skipped': 0,
        'errors': []
    }
    
    # Lecture du CSV
    try:
        # Décodage en UTF-8
        content = file.read().decode('utf-8')
        csv_reader = csv.DictReader(content.splitlines(), delimiter=';')
        
        # Vérification des colonnes requises
        required_columns = ['sigle', 'nom_complet']
        
        # Colonnes optionnelles pour Conference Flow avec champs HAL
        optional_columns = [
            'adresse', 
            'citation', 
            'struct_id_hal',
            'acronym_hal',
            'type_hal'
        ]
        
        if not all(col in csv_reader.fieldnames for col in required_columns):
            raise ValueError(f"Colonnes requises manquantes. Attendues: {required_columns}")
        
        current_app.logger.info(f"Colonnes détectées: {csv_reader.fieldnames}")
        
        line_number = 1  # En-tête = ligne 1
        
        for row in csv_reader:
            line_number += 1
            
            try:
                # Nettoyage des données existantes
                sigle = row.get('sigle', '').strip().upper()
                nom_complet = row.get('nom_complet', '').strip()
                adresse = row.get('adresse', '').strip() or None
                citation = row.get('citation', '').strip() or None
                
                # Nettoyage des champs HAL
                struct_id_hal = row.get('struct_id_hal', '').strip() or None
                acronym_hal = row.get('acronym_hal', '').strip() or None
                type_hal = row.get('type_hal', '').strip() or None
                
                # Validation des données obligatoires
                if not sigle:
                    results['errors'].append({
                        'line': line_number,
                        'message': 'Sigle manquant'
                    })
                    results['skipped'] += 1
                    continue
                
                if not nom_complet:
                    results['errors'].append({
                        'line': line_number,
                        'message': 'Nom complet manquant'
                    })
                    results['skipped'] += 1
                    continue
                
                # Vérification des doublons
                existing_affiliation = None
                
                # 1. Recherche par sigle (priorité 1)
                if sigle:
                    existing_affiliation = Affiliation.query.filter_by(sigle=sigle).first()
                
                # 2. Si pas trouvé par sigle, recherche par struct_id_hal
                if not existing_affiliation and struct_id_hal:
                    existing_affiliation = Affiliation.query.filter_by(struct_id_hal=struct_id_hal).first()
                
                # Mise à jour ou création
                if existing_affiliation:
                    # Mise à jour de l'affiliation existante
                    existing_affiliation.nom_complet = nom_complet
                    existing_affiliation.adresse = adresse
                    existing_affiliation.citation = citation
                    
                    # Mise à jour des champs HAL
                    if struct_id_hal:
                        existing_affiliation.struct_id_hal = struct_id_hal
                    if acronym_hal:
                        existing_affiliation.acronym_hal = acronym_hal
                    if type_hal:
                        existing_affiliation.type_hal = type_hal
                    
                    results['updated'] += 1
                    current_app.logger.debug(f"Affiliation mise à jour: {sigle}")
                
                else:
                    # Création d'une nouvelle affiliation avec tous les champs
                    new_affiliation = Affiliation(
                        sigle=sigle,
                        nom_complet=nom_complet,
                        adresse=adresse,
                        citation=citation,
                        struct_id_hal=struct_id_hal,          
                        acronym_hal=acronym_hal,              
                        type_hal=type_hal                     
                    )
                    
                    db.session.add(new_affiliation)
                    results['success'] += 1
                    current_app.logger.debug(f"Nouvelle affiliation créée: {sigle}")
                
            except Exception as e:
                results['errors'].append({
                    'line': line_number,
                    'message': f'Erreur de traitement: {str(e)}'
                })
                results['skipped'] += 1
                current_app.logger.error(f"Erreur ligne {line_number}: {e}")
        
        # Commit des changements
        db.session.commit()
        
    except UnicodeDecodeError:
        raise ValueError("Erreur d'encodage du fichier. Utilisez l'encodage UTF-8.")
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Erreur lors du traitement du fichier CSV: {str(e)}")
    
    return results


@admin.route("/admin/thematiques")
@login_required
def manage_thematiques():
    """Page de gestion des thématiques."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    thematiques = Thematique.query.order_by(Thematique.nom).all()
    
    # Statistiques
    stats = {
        'total_thematiques': len(thematiques),
        'total_specialistes': User.query.filter_by(is_reviewer=True).count(),
        'thematiques_sans_specialiste': len([t for t in thematiques if t.nb_specialistes == 0])
    }
    
    return render_template('admin/manage_thematiques.html', 
                         thematiques=thematiques, 
                         stats=stats)

@admin.route("/admin/thematiques/init", methods=["POST"])
@login_required
def init_thematiques():
    """Initialise les thématiques par défaut."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    try:
        from .models import init_thematiques
        init_thematiques()
        flash("Thématiques initialisées avec succès.", "success")
    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'initialisation des thématiques: {e}")
        flash(f"Erreur lors de l'initialisation: {str(e)}", "error")
    
    return redirect(url_for('admin.manage_thematiques'))

@admin.route("/admin/thematiques/<int:thematique_id>/toggle", methods=["POST"])
@login_required
def toggle_thematique(thematique_id):
    """Active/désactive une thématique."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    thematique = Thematique.query.get_or_404(thematique_id)
    thematique.is_active = not thematique.is_active
    db.session.commit()
    
    status = "activée" if thematique.is_active else "désactivée"
    flash(f"Thématique '{thematique.nom}' {status}.", "success")
    
    return redirect(url_for('admin.manage_thematiques'))

@admin.route("/admin/reviewers/specialites")
@login_required
def manage_reviewer_specialites():
    """Page de gestion des spécialités des reviewers."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    reviewers = User.query.filter_by(is_reviewer=True).order_by(User.email).all()
    thematiques = Thematique.get_active()
    
    # Statistiques
    stats = {
        'total_reviewers': len(reviewers),
        'reviewers_sans_specialite': len([r for r in reviewers if len(r.specialites) == 0]),
        'moyenne_specialites': sum(len(r.specialites) for r in reviewers) / len(reviewers) if reviewers else 0
    }
    
    return render_template('admin/manage_reviewer_specialites.html',
                         reviewers=reviewers,
                         thematiques=thematiques,
                         stats=stats)

@admin.route("/admin/reviewers/<int:reviewer_id>/specialites", methods=["POST"])
@login_required
def update_reviewer_specialites(reviewer_id):
    """Met à jour les spécialités d'un reviewer."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    reviewer = User.query.get_or_404(reviewer_id)
    if not reviewer.is_reviewer:
        flash("Cet utilisateur n'est pas un reviewer.", "danger")
        return redirect(url_for('admin.manage_reviewer_specialites'))
    
    # Récupérer les thématiques sélectionnées
    selected_thematiques = request.form.getlist('specialites')
    
    # Vider les spécialités actuelles
    reviewer.specialites.clear()
    
    # Ajouter les nouvelles spécialités
    for thematique_id in selected_thematiques:
        thematique = Thematique.query.get(thematique_id)
        if thematique:
            reviewer.specialites.append(thematique)
    
    db.session.commit()
    
    flash(f"Spécialités mises à jour pour {reviewer.email} ({len(selected_thematiques)} thématiques).", "success")
    
    if request.headers.get('Accept') == 'application/json':
        return jsonify({'success': True, 'message': 'Spécialités mises à jour'})
    
    return redirect(url_for('admin.manage_reviewer_specialites'))

@admin.route("/admin/reviewers/specialites/bulk", methods=["POST"])
@login_required
def bulk_assign_specialites():
    """Affectation en masse des spécialités."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    try:
        # Format attendu: CSV avec colonnes email, thematiques (codes séparés par des virgules)
        file = request.files.get('csv_file')
        if not file:
            flash("Aucun fichier fourni.", "error")
            return redirect(url_for('admin.manage_reviewer_specialites'))
        
        content = file.read().decode('utf-8')
        csv_reader = csv.DictReader(content.splitlines(), delimiter=';')
        
        success_count = 0
        errors = []
        
        for line_num, row in enumerate(csv_reader, 2):
            email = row.get('email', '').strip()
            thematiques_codes = row.get('thematiques', '').strip()
            
            if not email:
                continue
                
            reviewer = User.query.filter_by(email=email, is_reviewer=True).first()
            if not reviewer:
                errors.append(f"Ligne {line_num}: Reviewer {email} non trouvé")
                continue
            
            # Parser les codes de thématiques
            codes = [code.strip() for code in thematiques_codes.split(',') if code.strip()]
            
            # Vider et réassigner les spécialités
            reviewer.specialites.clear()
            
            for code in codes:
                thematique = Thematique.get_by_code(code)
                if thematique:
                    reviewer.specialites.append(thematique)
                else:
                    errors.append(f"Ligne {line_num}: Thématique {code} non trouvée")
            
            success_count += 1
        
        db.session.commit()
        
        if success_count > 0:
            flash(f"{success_count} reviewers mis à jour.", "success")
        
        for error in errors[:5]:  # Limite à 5 erreurs affichées
            flash(error, "warning")
            
    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'affectation en masse: {e}")
        flash(f"Erreur lors de l'import : {str(e)}", "error")
    
    return redirect(url_for('admin.manage_reviewer_specialites'))

@admin.route("/admin/reviews/auto-assign")
@login_required
def auto_assign_reviews():
    """Page d'affectation automatique des reviewers."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Communications sans reviewers ou avec moins de 2 reviewers
    communications_pending = Communication.query.filter(
        Communication.nb_reviewers_assigned < 2
    ).all()
    
    # Statistiques
    stats = {
        'total_communications': Communication.query.count(),
        'communications_sans_reviewers': len([c for c in communications_pending if c.nb_reviewers_assigned == 0]),
        'communications_un_reviewer': len([c for c in communications_pending if c.nb_reviewers_assigned == 1]),
        'reviewers_disponibles': User.query.filter_by(is_reviewer=True).count()
    }
    
    return render_template('admin/auto_assign_reviews.html',
                         communications_pending=communications_pending,
                         stats=stats)

@admin.route("/admin/reviews/auto-assign/run", methods=["POST"])
@login_required
def run_auto_assign():
    """Lance l'affectation automatique."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Options d'affectation
    nb_reviewers = int(request.form.get('nb_reviewers', 2))
    force_reassign = request.form.get('force_reassign') == 'on'
    selected_communications = request.form.getlist('communications')
    
    results = {
        'success': 0,
        'partial': 0,
        'failed': 0,
        'errors': []
    }
    
    try:
        # Si aucune communication sélectionnée, traiter toutes celles qui ont besoin de reviewers
        if not selected_communications:
            communications = Communication.query.filter(
                Communication.nb_reviewers_assigned < nb_reviewers
            ).all()
        else:
            communications = Communication.query.filter(
                Communication.id.in_(selected_communications)
            ).all()
        
        for comm in communications:
            # Réinitialiser si demandé
            if force_reassign:
                comm.assigned_reviewers.clear()
                db.session.commit()
            
            # Tenter l'affectation automatique
            result = comm.auto_assign_reviewers(nb_reviewers)
            
            if result['success']:
                if len(result['assigned_reviewers']) == nb_reviewers - comm.nb_reviewers_assigned:
                    results['success'] += 1
                else:
                    results['partial'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(f"Communication {comm.id}: {result['message']}")
        
        db.session.commit()
        
        # Messages de retour
        if results['success'] > 0:
            flash(f"{results['success']} communications assignées avec succès.", "success")
        
        if results['partial'] > 0:
            flash(f"{results['partial']} communications partiellement assignées.", "info")
        
        if results['failed'] > 0:
            flash(f"{results['failed']} communications non assignées.", "warning")
        
        for error in results['errors'][:5]:
            flash(error, "warning")
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de l'affectation automatique: {e}")
        flash(f"Erreur lors de l'affectation : {str(e)}", "error")
    
    return redirect(url_for('admin.auto_assign_reviews'))

@admin.route("/admin/reviews/assignments")
@login_required
def view_assignments():
    """Vue d'ensemble des affectations de reviewers."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Récupérer toutes les affectations
    assignments = ReviewAssignment.query.join(Communication).join(User).all()
    
    # Grouper par communication
    communications_with_reviews = {}
    for assignment in assignments:
        comm_id = assignment.communication_id
        if comm_id not in communications_with_reviews:
            communications_with_reviews[comm_id] = {
                'communication': assignment.communication,
                'assignments': []
            }
        communications_with_reviews[comm_id]['assignments'].append(assignment)
    
    # Statistiques
    stats = {
        'total_assignments': len(assignments),
        'assignments_completed': len([a for a in assignments if a.status == 'completed']),
        'assignments_overdue': len([a for a in assignments if a.is_overdue]),
        'communications_fully_assigned': len([c for c in communications_with_reviews.values() if len(c['assignments']) >= 2])
    }
    
    return render_template('admin/view_assignments.html',
                         communications_with_reviews=communications_with_reviews,
                         stats=stats)

@admin.route("/admin/reviews/assignment/<int:assignment_id>/update", methods=["POST"])
@login_required
def update_assignment(assignment_id):
    """Met à jour une affectation de review."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    assignment = ReviewAssignment.query.get_or_404(assignment_id)
    
    new_status = request.form.get('status')
    due_date_str = request.form.get('due_date')
    comments = request.form.get('comments')
    
    if new_status:
        assignment.status = new_status
        if new_status == 'completed':
            assignment.completed_at = datetime.utcnow()
    
    if due_date_str:
        try:
            assignment.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            flash("Format de date invalide.", "error")
            return redirect(url_for('admin.view_assignments'))
    
    if comments:
        assignment.comments = comments
    
    db.session.commit()
    flash("Affectation mise à jour.", "success")
    
    return redirect(url_for('admin.view_assignments'))

# ==================== EXPORTS SPÉCIALISÉS ====================

@admin.route("/admin/export/thematiques-reviewers")
@login_required
def export_thematiques_reviewers():
    """Export de la matrice thématiques-reviewers."""
    if not current_user.is_admin:
        flash("Accès réservé aux administrateurs.", "danger")
        return redirect(url_for("main.index"))

    output = StringIO()
    writer = csv.writer(output)
    
    # En-tête
    thematiques = Thematique.get_active()
    header = ['email', 'nom', 'prenom'] + [t.code for t in thematiques]
    writer.writerow(header)

    # Données
    reviewers = User.query.filter_by(is_reviewer=True).all()
    for reviewer in reviewers:
        row = [
            reviewer.email,
            reviewer.last_name or '',
            reviewer.first_name or ''
        ]
        
        # Marquer les spécialités
        reviewer_specialites = {s.id for s in reviewer.specialites}
        for thematique in thematiques:
            row.append('X' if thematique.id in reviewer_specialites else '')
        
        writer.writerow(row)

    output.seek(0)
    return send_file(
        StringIO(output.getvalue()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="thematiques_reviewers.csv"
    )

@admin.route("/admin/export/assignments")
@login_required
def export_assignments():
    """Export des affectations de reviewers."""
    if not current_user.is_admin:
        flash("Accès réservé aux administrateurs.", "danger")
        return redirect(url_for("main.index"))

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "communication_id", "titre", "thematiques", "reviewer_email", 
        "status", "assigned_at", "due_date", "completed_at"
    ])

    assignments = ReviewAssignment.query.join(Communication).join(User).all()
    for assignment in assignments:
        writer.writerow([
            assignment.communication_id,
            assignment.communication.title,
            ','.join(assignment.communication.thematiques_codes),
            assignment.reviewer.email,
            assignment.status,
            assignment.assigned_at.strftime('%Y-%m-%d %H:%M') if assignment.assigned_at else '',
            assignment.due_date.strftime('%Y-%m-%d') if assignment.due_date else '',
            assignment.completed_at.strftime('%Y-%m-%d %H:%M') if assignment.completed_at else ''
        ])

    output.seek(0)
    return send_file(
        StringIO(output.getvalue()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="assignments_export.csv"
    )

@admin.route('/reviewers/pending-activation')
@login_required
def pending_activation_reviewers():
    """Liste des reviewers en attente d'activation."""
    if not current_user.is_admin:
        abort(403)
    
    pending_reviewers = User.query.filter_by(
        is_reviewer=True, 
        is_activated=False
    ).all()
    
    return render_template('admin/pending_activation.html', 
                         reviewers=pending_reviewers)


@admin.route('/reviewers/send-activation/<int:user_id>')
@login_required
def send_activation_email(user_id):
    """Envoie l'email d'activation à un reviewer."""
    if not current_user.is_admin:
        abort(403)
    
    user = User.query.get_or_404(user_id)
    
    if user.is_activated:
        flash(f'{user.email} est déjà activé', 'warning')
        return redirect(url_for('admin.pending_activation_reviewers'))
    
    # Générer le token d'activation
    token = user.generate_activation_token()
    db.session.commit()
    
    # Envoyer l'email avec votre fonction
    try:
        current_app.send_activation_email_to_user(user, token)
        flash(f'Email d\'activation envoyé à {user.email}', 'success')
    except Exception as e:
        flash(f'Erreur lors de l\'envoi de l\'email : {str(e)}', 'danger')
        current_app.logger.error(f"Erreur envoi email activation: {e}")
    
    return redirect(url_for('admin.pending_activation_reviewers'))





@admin.route("/admin/users/import-reviewers", methods=["GET", "POST"])
@login_required
def import_reviewers():
    """Import des reviewers avec création et spécialités depuis un fichier CSV."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))

    # GET : Afficher le formulaire
    if request.method == 'GET':
        return render_template('admin/import_reviewers.html')

    # POST : Traitement du fichier
    file = request.files.get("csv_file")
    if not file:
        flash("Aucun fichier fourni.", "danger")
        return redirect(url_for("admin.import_reviewers"))

    try:
        # Lire le contenu du fichier
        content = file.read().decode("utf-8")
        lines = content.strip().split('\n')
        
        if not lines:
            flash("Fichier CSV vide.", "error")
            return redirect(url_for("admin.import_reviewers"))
        
        # Format attendu : email;nom;prenom;thematiques;affiliation
        csv_reader = csv.DictReader(content.splitlines(), delimiter=';')
        
        # Vérifier les colonnes requises
        required_columns = ['email']
        if not all(col in csv_reader.fieldnames for col in required_columns):
            flash(f"Colonnes requises manquantes. Format attendu : email;nom;prenom;thematiques;affiliation", "error")
            return redirect(url_for("admin.import_reviewers"))
        
        results = {
            'created': 0,
            'updated': 0,
            'specialites_assigned': 0,
            'errors': []
        }
        
        for line_num, row in enumerate(csv_reader, 2):  # Ligne 2 car en-tête = ligne 1
            try:
                email = row.get('email', '').strip()
                if not email:
                    results['errors'].append(f"Ligne {line_num}: Email manquant")
                    continue
                
                # Traiter l'utilisateur complet
                user_result = process_complete_reviewer_import(row, line_num)
                
                # Agréger les résultats
                for key in ['created', 'updated', 'specialites_assigned']:
                    results[key] += user_result.get(key, 0)
                
                if user_result.get('errors'):
                    results['errors'].extend(user_result['errors'])
                    
            except Exception as e:
                results['errors'].append(f"Ligne {line_num}: Erreur de traitement - {str(e)}")
                continue
        
        # Sauvegarder en base
        db.session.commit()
        
        # Affichage des résultats
        if results['created'] > 0:
            flash(f"{results['created']} nouveaux reviewers créés.", "success")
        
        if results['updated'] > 0:
            flash(f"{results['updated']} reviewers mis à jour.", "info")
        
        if results['specialites_assigned'] > 0:
            flash(f"{results['specialites_assigned']} spécialités assignées.", "success")
        
        if results['errors']:
            for error in results['errors'][:5]:  # Limite à 5 erreurs
                flash(error, "warning")
            
            if len(results['errors']) > 5:
                flash(f"... et {len(results['errors']) - 5} autres erreurs.", "warning")
        
        current_app.logger.info(f"Import reviewers terminé: {results}")
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de l'import des reviewers: {e}")
        flash(f"Erreur lors de l'import : {str(e)}", "error")
    
    return redirect(url_for("admin.import_reviewers"))


def process_complete_reviewer_import(row, line_num):
    """Traite l'import complet d'un reviewer avec création et spécialités."""
    
    result = {
        'created': 0,
        'updated': 0,
        'specialites_assigned': 0,
        'errors': []
    }
    
    # Extraire les données de la ligne
    email = row.get('email', '').strip().lower()
    nom = row.get('nom', '').strip()
    prenom = row.get('prenom', '').strip()
    thematiques_codes = row.get('thematiques', '').strip()
    affiliation_sigle = row.get('affiliation', '').strip()
    
    if not email:
        result['errors'].append(f"Ligne {line_num}: Email manquant")
        return result
    
    # Vérifier si l'utilisateur existe
    user = User.query.filter_by(email=email).first()

    if not user:
        # CRÉER un nouveau utilisateur reviewer NON-ACTIVÉ
        try:
            user = User(
                email=email,
                first_name=prenom or None,
                last_name=nom or None,
                is_reviewer=True,
                is_active=True,
                is_activated=False,  # NOUVEAU : Compte non-activé
                created_at=datetime.utcnow()
            )
            # PAS DE VRAI MOT DE PASSE - sera créé à l'activation
            user.password_hash = 'PENDING_ACTIVATION'  # Placeholder
        
            # Gérer l'affiliation si fournie (MULTIPLE maintenant)
            if affiliation_sigle:
                affiliation = Affiliation.query.filter_by(sigle=affiliation_sigle.upper()).first()
                if affiliation:
                    user.affiliations.append(affiliation)  # PLURIEL
                else:
                    result['errors'].append(f"Ligne {line_num}: Affiliation {affiliation_sigle} non trouvée")
        
            db.session.add(user)
            db.session.flush()  # Pour obtenir l'ID
            result['created'] = 1
            current_app.logger.info(f"Nouveau reviewer créé (non-activé): {email}")
        
        except Exception as e:
            result['errors'].append(f"Ligne {line_num}: Erreur création utilisateur - {str(e)}")
            return result
    else:
        # Utilisateur existant
        # Mettre à jour les informations seulement si le compte n'est pas encore activé
        # ou si les champs sont vides
        if nom and (not user.last_name or not user.is_activated):
            user.last_name = nom
        if prenom and (not user.first_name or not user.is_activated):
            user.first_name = prenom
        
            # Promouvoir en reviewer si pas déjà le cas
        if not user.is_reviewer:
            user.is_reviewer = True
        
            # Gérer l'affiliation (MULTIPLE)
        if affiliation_sigle:
            affiliation = Affiliation.query.filter_by(sigle=affiliation_sigle.upper()).first()
            if affiliation:
                # Vérifier si l'affiliation n'est pas déjà présente
                if affiliation not in user.affiliations:
                    user.affiliations.append(affiliation)
            else:
                result['errors'].append(f"Ligne {line_num}: Affiliation {affiliation_sigle} non trouvée")
    
        result['updated'] = 1
        current_app.logger.info(f"Reviewer mis à jour: {email}")

    
    
        # Traiter les spécialités/thématiques
    if thematiques_codes:
        try:
            # Parser les codes de thématiques
            codes = [code.strip().upper() for code in thematiques_codes.split(',') if code.strip()]
            
            if codes:
                # Vérifier les codes valides avec ThematiqueHelper
                valid_codes = []
                invalid_codes = []
                
                for code in codes:
                    if ThematiqueHelper.is_valid_code(code):
                        valid_codes.append(code)
                    else:
                        invalid_codes.append(code)
                
                # Signaler les thématiques non trouvées
                if invalid_codes:
                    result['errors'].append(
                        f"Ligne {line_num}: Thématiques non trouvées: {', '.join(invalid_codes)}"
                    )
                
                # Assigner les spécialités valides
                if valid_codes:
                    user.set_specialites(valid_codes)  # NOUVELLE MÉTHODE
                    result['specialites_assigned'] = len(valid_codes)
                    current_app.logger.info(f"Spécialités assignées à {email}: {valid_codes}")
                
        except Exception as e:
            result['errors'].append(f"Ligne {line_num}: Erreur lors de l'assignation des spécialités - {str(e)}")
    
    return result

@admin.route("/admin/users/import-reviewers/template")
@login_required
def download_reviewers_template():
    """Télécharge un template CSV pour l'import des reviewers."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Récupérer les thématiques actives pour l'exemple
    thematiques = Thematique.query.filter_by(is_active=True).limit(5).all()
    exemple_codes = ','.join([t.code for t in thematiques]) if thematiques else 'COND,MULTI,POREUX'
    
    # Créer le contenu du template
    template_content = f"""email;thematiques
reviewer1@example.com;{exemple_codes}
reviewer2@example.com;BIO,SIMUL
reviewer3@example.com;ECHANG,STOCK,RENOUV
reviewer4@example.com;METRO,SIMUL"""
    
    # Créer la réponse
    output = StringIO()
    output.write(template_content)
    output.seek(0)
    
    return send_file(
        StringIO(template_content),
        mimetype="text/csv",
        as_attachment=True,
        download_name="template_reviewers_specialites.csv"
    )

@admin.route("/admin/users/import-reviewers/help")
@login_required
def reviewers_import_help():
    """Page d'aide pour l'import des reviewers."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    thematiques = Thematique.query.filter_by(is_active=True).order_by(Thematique.code).all()
    
    return render_template('admin/import_reviewers_help.html', thematiques=thematiques)

# Pour l'admin - Édition des spécialités d'un reviewer
@admin.route('/reviewers/<int:user_id>/specialites', methods=['GET', 'POST'])
@login_required
def edit_reviewer_specialites(user_id):
    """Admin peut modifier les spécialités d'un reviewer."""
    if not current_user.is_admin:
        abort(403)
    
    user = User.query.get_or_404(user_id)
    form = UserSpecialitesForm()
    
    if form.validate_on_submit():
        selected_codes = form.specialites.data
        valid_codes = [code for code in selected_codes if ThematiqueHelper.is_valid_code(code)]
        
        user.set_specialites(valid_codes)
        db.session.commit()
        
        flash(f'Spécialités de {user.full_name} mises à jour', 'success')
        return redirect(url_for('admin.reviewers'))
    
    # Pré-remplir
    if request.method == 'GET':
        current_codes = user.specialites_codes.split(',') if user.specialites_codes else []
        form.specialites.data = current_codes
    
    return render_template('admin/edit_reviewer_specialites.html', form=form, user=user)

# Fonction utilitaire pour récupérer les thématiques d'un utilisateur
def get_user_thematiques_display(user):
    """Retourne un affichage formaté des thématiques d'un utilisateur."""
    if not user.specialites_codes:
        return "Aucune spécialité"
    
    thematiques = user.specialites
    if not thematiques:
        return "Aucune spécialité"
    
    return ", ".join([f"{t['nom']} ({t['code']})" for t in thematiques])


@admin.context_processor
def inject_admin_helpers():
    """Helpers pour les templates admin."""
    def get_pending_reviewers_count():
        if current_user.is_authenticated and current_user.is_admin:
            return User.query.filter_by(is_reviewer=True, is_activated=False).count()
        return 0
    
    return dict(get_pending_reviewers_count=get_pending_reviewers_count)

@admin.route('/reviews/send-reminders', methods=['POST'])
@login_required
def send_review_reminders():
    """Envoie des rappels aux reviewers en retard ou avec reviews en attente."""
    if not current_user.is_admin:
        abort(403)
    
    # Récupérer toutes les assignations en attente
    pending_assignments = ReviewAssignment.query.filter_by(status='assigned').all()
    
    if not pending_assignments:
        flash('Aucune review en attente.', 'info')
        return redirect(url_for('admin.communications_ready_for_review'))
    
    # Grouper par reviewer
    reviewers_assignments = {}
    for assignment in pending_assignments:
        reviewer_id = assignment.reviewer_id
        if reviewer_id not in reviewers_assignments:
            reviewers_assignments[reviewer_id] = {
                'reviewer': assignment.reviewer,
                'assignments': []
            }
        reviewers_assignments[reviewer_id]['assignments'].append(assignment)
    
    # Envoyer les rappels
    sent_count = 0
    errors = []
    
    for reviewer_id, data in reviewers_assignments.items():
        try:
            current_app.send_review_reminder_email(data['reviewer'], data['assignments'])
            sent_count += 1
            current_app.logger.info(f"Rappel envoyé à {data['reviewer'].email}")
        except Exception as e:
            error_msg = f"Erreur pour {data['reviewer'].email}: {str(e)}"
            errors.append(error_msg)
            current_app.logger.error(error_msg)
    
    # Messages de retour
    if sent_count > 0:
        flash(f'Rappels envoyés à {sent_count} reviewer(s).', 'success')
    
    if errors:
        for error in errors[:3]:  # Limiter à 3 erreurs affichées
            flash(error, 'warning')
        if len(errors) > 3:
            flash(f"... et {len(errors) - 3} autres erreurs.", 'warning')
    
    return redirect(url_for('admin.communications_ready_for_review'))

@admin.route('/communications/ready-for-review')
@login_required
def communications_ready_for_review():
    """Liste des communications prêtes pour review."""
    if not current_user.is_admin:
        abort(403)

    # Communications qui ont besoin de reviewers
    # 1. Articles soumis pas encore en review
    communications_soumis = Communication.query.filter(
        Communication.type == 'article',
        Communication.status == CommunicationStatus.ARTICLE_SOUMIS
    ).all()

    # 2. Articles en review mais avec des reviewers refusés (moins de 2 reviewers actifs)
    communications_en_review = Communication.query.filter(
        Communication.type == 'article',
        Communication.status == CommunicationStatus.EN_REVIEW
    ).all()

    ready_communications = list(communications_soumis)

    # Vérifier les communications en review
    for comm in communications_en_review:
        # Compter les reviewers actifs (non refusés)
        active_assignments = ReviewAssignment.query.filter(
            ReviewAssignment.communication_id == comm.id,
            ReviewAssignment.status != 'declined'
        ).count()
        
        # Ajouter si elle a besoin de reviewers (moins de 2 reviewers actifs)
        if active_assignments < 2:
            ready_communications.append(comm)

    # Articles par statut avec vérification du nombre de reviewers
    en_review_real = 0
    communications_en_review_status = Communication.query.filter_by(
        type='article', 
        status=CommunicationStatus.EN_REVIEW
    ).all()

    for comm in communications_en_review_status:
        # Compter les reviewers actifs (non refusés)
        active_assignments = ReviewAssignment.query.filter(
            ReviewAssignment.communication_id == comm.id,
            ReviewAssignment.status != 'declined'
        ).count()
        
        # Compter comme "vraiment en review" seulement si 2+ reviewers actifs
        if active_assignments >= 2:
            en_review_real += 1

    articles_stats = {
        'soumis_non_assignes': len(ready_communications),
        'en_review': en_review_real,
        'acceptes': Communication.query.filter_by(
            type='article', 
            status=CommunicationStatus.ACCEPTE
        ).count(),
        'rejetes': Communication.query.filter_by(
            type='article', 
            status=CommunicationStatus.REJETE
        ).count()
    }
        
    # Reviewers disponibles
    reviewers_stats = {
        'total_reviewers': User.query.filter_by(is_reviewer=True, is_activated=True).count(),
        'avec_specialites': User.query.filter(
            User.is_reviewer == True,
            User.is_activated == True,
            User.specialites_codes.isnot(None),
            User.specialites_codes != ''
        ).count(),
        'sans_specialites': User.query.filter(
            User.is_reviewer == True,
            User.is_activated == True,
            db.or_(User.specialites_codes.is_(None), User.specialites_codes == '')
        ).count()
    }
    
    # Assignations en cours
    assignments_stats = {
        'en_attente': ReviewAssignment.query.filter_by(status='assigned').count(),
        'terminees': ReviewAssignment.query.filter_by(status='completed').count(),
        'en_retard': ReviewAssignment.query.filter(
            ReviewAssignment.due_date < datetime.utcnow(),
            ReviewAssignment.status == 'assigned'
        ).count()
    }
    
    # Thématiques des articles en attente
    thematiques_count = {}
    for comm in ready_communications:
        if comm.thematiques_codes:
            codes = comm.thematiques_codes.split(',')
            for code in codes:
                code = code.strip()
                if code:
                    thematique = ThematiqueHelper.get_by_code(code)
                    if thematique:
                        thematique_name = f"{thematique['code']} - {thematique['nom']}"
                        thematiques_count[thematique_name] = thematiques_count.get(thematique_name, 0) + 1
    
    # Top 5 des thématiques
    top_thematiques = sorted(thematiques_count.items(), key=lambda x: x[1], reverse=True)[:5]
    
    stats = {
        'articles': articles_stats,
        'reviewers': reviewers_stats,
        'assignments': assignments_stats,
        'thematiques': dict(thematiques_count),
        'top_thematiques': top_thematiques
    }
    
    return render_template('admin/communications_ready_for_review.html', 
                         communications=ready_communications,
                         stats=stats)


@admin.route('/communications/<int:comm_id>/suggest-reviewers')
@login_required
def suggest_reviewers(comm_id):
    """Page de suggestion automatique de reviewers."""
    if not current_user.is_admin:
        abort(403)
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Obtenir les suggestions automatiques
    suggestions = communication.suggest_reviewers(nb_reviewers=2)
    
    # Récupérer les assignations actuelles
    current_assignments = ReviewAssignment.query.filter(
        ReviewAssignment.communication_id == comm_id,
        ReviewAssignment.status != 'declined'
    ).all()

    
    return render_template('admin/suggest_reviewers.html',
                         communication=communication,
                         suggestions=suggestions,
                         current_assignments=current_assignments)

@admin.route('/communications/<int:comm_id>/assign-reviewers', methods=['POST'])
@login_required
def assign_reviewers(comm_id):
    """Assigne les reviewers sélectionnés à une communication."""
    if not current_user.is_admin:
        abort(403)
    
    communication = Communication.query.get_or_404(comm_id)
    reviewer_ids = request.form.getlist('reviewer_ids')
    
    if not reviewer_ids:
        flash('Sélectionnez au moins un reviewer.', 'danger')
        return redirect(url_for('admin.suggest_reviewers', comm_id=comm_id))
    
    # Calculer la date d'échéance (par exemple, 3 semaines)
    from datetime import timedelta
    due_date = datetime.utcnow() + timedelta(weeks=3)
    
    assigned_reviewers = []
    
    for reviewer_id in reviewer_ids:
        reviewer = User.query.get(int(reviewer_id))
        if not reviewer:
            continue
        
        # Vérifier qu'il n'est pas déjà assigné
        existing = ReviewAssignment.query.filter_by(
            communication_id=comm_id,
            reviewer_id=reviewer_id
        ).first()
        
        if existing:
            continue  # Skip si déjà assigné
        
        # Créer l'assignation
        assignment = ReviewAssignment(
            communication_id=comm_id,
            reviewer_id=reviewer_id,
            assigned_by_id=current_user.id,
            due_date=due_date,
            auto_suggested=True,  # Car c'est via le système automatique
            status='assigned'
        )
        
        db.session.add(assignment)
        assigned_reviewers.append(reviewer.email)
    
    if assigned_reviewers:
        # Changer le statut de la communication
        communication.status = CommunicationStatus.EN_REVIEW
        db.session.commit()
        
        flash(f'Reviewers assignés: {", ".join(assigned_reviewers)}', 'success')
    else:
        flash('Aucun reviewer assigné.', 'warning')
    
    return redirect(url_for('admin.suggest_reviewers', comm_id=comm_id))

@admin.route('/communications/<int:comm_id>/notify-reviewers', methods=['POST'])
@login_required
def send_review_notifications(comm_id):
    """Envoie les notifications par email aux reviewers assignés."""
    if not current_user.is_admin:
        abort(403)
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Récupérer les assignations sans notification
    assignments = ReviewAssignment.query.filter_by(
        communication_id=comm_id,
        notification_sent_at=None
    ).all()
    
    if not assignments:
        flash('Tous les reviewers ont déjà été notifiés.', 'info')
        return redirect(url_for('admin.suggest_reviewers', comm_id=comm_id))
    
    notified_count = 0
    
    for assignment in assignments:
        try:
            # Créer l'objet Review s'il n'existe pas
            review = assignment.get_or_create_review()
            
            # Envoyer l'email de notification
            current_app.send_review_notification_email(assignment.reviewer, communication, assignment)
            
            # Marquer comme notifié
            assignment.notification_sent_at = datetime.utcnow()
            notified_count += 1
            
        except Exception as e:
            current_app.logger.error(f"Erreur notification reviewer {assignment.reviewer.email}: {e}")
    
    db.session.commit()
    
    if notified_count > 0:
        flash(f'{notified_count} reviewer(s) notifié(s) par email.', 'success')
    else:
        flash('Erreur lors de l\'envoi des notifications.', 'danger')
    
    return redirect(url_for('admin.suggest_reviewers', comm_id=comm_id))

@admin.route("/affiliations/import", methods=["GET", "POST"])
@login_required
def import_affiliations():
    """Page unifiée pour l'import des affiliations."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    if request.method == 'POST':
        source = request.form.get('source', 'upload')
        
        if source == 'upload':
            # Import via upload de fichier
            if 'csv_file' not in request.files:
                flash('Aucun fichier sélectionné.', 'error')
                return redirect(request.url)
            
            file = request.files['csv_file']
            if file.filename == '':
                flash('Aucun fichier sélectionné.', 'error')
                return redirect(request.url)
            
            if not file.filename.lower().endswith('.csv'):
                flash('Veuillez sélectionner un fichier CSV.', 'error')
                return redirect(request.url)
            
            try:
                import_results = process_affiliations_csv(file)
                flash_import_results(import_results)
                return redirect(url_for('admin.list_affiliations'))
                
            except Exception as e:
                current_app.logger.error(f"Erreur lors de l'import des affiliations: {e}")
                flash(f"Erreur lors de l'import : {str(e)}", 'error')
                return redirect(request.url)
        
        elif source == 'default':
            # Import depuis le fichier par défaut dans app/static/content/
            try:
                csv_path = os.path.join(current_app.static_folder, 'content', 'affiliations.csv')
                
                if not os.path.exists(csv_path):
                    flash(f"Fichier affiliations.csv non trouvé dans app/static/content/", "error")
                    flash("Veuillez d'abord placer votre fichier affiliations.csv dans le dossier app/static/content/", "info")
                    return redirect(request.url)
                
                # Compter avant import
                count_before = Affiliation.query.count()
                
                # Lire le fichier et l'importer
                with open(csv_path, 'rb') as f:
                    import_results = process_affiliations_csv(f)
                
                # Messages de retour
                flash_import_results(import_results)
                flash(f"Import depuis {csv_path}", "info")
                
                return redirect(url_for('admin.list_affiliations'))
                
            except Exception as e:
                import traceback
                flash(f"Erreur lors de l'import : {str(e)}", "error")
                current_app.logger.error(f"Erreur import affiliations: {e}")
                current_app.logger.error(traceback.format_exc())
                return redirect(request.url)
    
    # GET : Affichage du formulaire
    total_affiliations = Affiliation.query.count()
    
    # Vérifier si le fichier par défaut existe
    default_file_path = os.path.join(current_app.static_folder, 'content', 'affiliations.csv')
    default_file_exists = os.path.exists(default_file_path)
    
    return render_template('admin/import_affiliations.html', 
                         total_affiliations=total_affiliations,
                         default_file_exists=default_file_exists,
                         default_file_path=default_file_path)


def flash_import_results(import_results):
    """Affiche les messages flash pour les résultats d'import."""
    if import_results['success'] > 0:
        flash(f"Import réussi : {import_results['success']} affiliations importées.", 'success')
    
    if import_results['updated'] > 0:
        flash(f"{import_results['updated']} affiliations mises à jour.", 'info')
    
    if import_results['errors']:
        for error in import_results['errors'][:5]: 
            flash(f"Erreur ligne {error['line']}: {error['message']}", 'warning')
        
        if len(import_results['errors']) > 5:
            flash(f"... et {len(import_results['errors']) - 5} autres erreurs.", 'warning')
    
    if import_results['skipped'] > 0:
        flash(f"{import_results['skipped']} lignes ignorées (doublons ou erreurs).", 'info')



##############  Test  #################

@admin.route("/generate-test-data")
@login_required
def generate_test_data():
    """Génère des données de test pour les utilisateurs et reviewers."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    from faker import Faker
    import random
    
    fake = Faker('fr_FR')
    
    try:
        created_users = 0
        created_reviewers = 0
        
        # Récupérer quelques affiliations existantes
        affiliations = Affiliation.query.limit(10).all()
        if not affiliations:
            flash("Créez d'abord quelques affiliations avant de générer les données de test.", "warning")
            return redirect(url_for("admin.admin_dashboard"))
        
        # =========================
        # 1. UTILISATEURS CLASSIQUES
        # =========================
        
        # 1 utilisateur avec votre email actif
        real_user = User(
            email="farges.olivier@gmail.com",  # Remplacez par votre vrai email
            first_name="Test",
            last_name="Actif",
            idhal="test-actif-123",
            orcid="0000-0000-0000-0001",
            is_active=True,
            is_activated=True,
        )
        real_user.set_password("password123")
        real_user.affiliations.append(random.choice(affiliations))
        db.session.add(real_user)
        created_users += 1
        
        # 10 utilisateurs avec faux emails
        for i in range(10):
            user = User(
                email=f"user{i+1}@faux-email-test.com",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                idhal=f"user-test-{i+1}-{random.randint(100, 999)}" if random.choice([True, False]) else None,
                orcid=f"0000-0000-0000-{i+1:04d}" if random.choice([True, False]) else None,
                is_active=True,
                is_activated=True,
            )
            user.set_password("password123")
            
            # Assigner 1-3 affiliations aléatoires
            num_affiliations = random.randint(1, 3)
            selected_affiliations = random.sample(affiliations, min(num_affiliations, len(affiliations)))
            for aff in selected_affiliations:
                user.affiliations.append(aff)
            
            db.session.add(user)
            created_users += 1
        
        # =========================
        # 2. REVIEWERS
        # =========================
        
        # 1 reviewer avec email actif
        real_reviewer = User(
            email="olivier@olivier-farges.xyz", 
            first_name="Reviewer",
            last_name="Actif",
            idhal="reviewer-actif-456",
            orcid="0000-0000-0000-0100",
            is_reviewer=True,
            is_active=True,
            is_activated=True,
        )
        real_reviewer.set_password("password123")
        real_reviewer.affiliations.append(random.choice(affiliations))
        
        # Assigner des spécialités aléatoires
        all_codes = ThematiqueHelper.get_codes()
        num_specialites = random.randint(2, 5)
        selected_codes = random.sample(all_codes, num_specialites)
        real_reviewer.set_specialites(selected_codes)
        
        db.session.add(real_reviewer)
        created_reviewers += 1
        
        # 10 reviewers avec faux emails
        for i in range(10):
            reviewer = User(
                email=f"reviewer{i+1}@faux-email-test.com",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                idhal=f"reviewer-test-{i+1}-{random.randint(100, 999)}" if random.choice([True, True, False]) else None,  # 2/3 ont un IDHAL
                orcid=f"0000-0000-0001-{i+1:04d}" if random.choice([True, False]) else None,
                is_reviewer=True,
                is_active=True,
                is_activated=True,
            )
            reviewer.set_password("password123")
            
            # Assigner 1-2 affiliations
            num_affiliations = random.randint(1, 2)
            selected_affiliations = random.sample(affiliations, min(num_affiliations, len(affiliations)))
            for aff in selected_affiliations:
                reviewer.affiliations.append(aff)
            
            # Assigner 2-6 spécialités aléatoires
            num_specialites = random.randint(2, 6)
            selected_codes = random.sample(all_codes, num_specialites)
            reviewer.set_specialites(selected_codes)
            
            db.session.add(reviewer)
            created_reviewers += 1
        
        # Sauvegarder tout
        db.session.commit()
        
        flash(f"✅ Données de test créées : {created_users} utilisateurs et {created_reviewers} reviewers", "success")
        flash("🔑 Mot de passe pour tous : 'password123'", "info")
        flash("📧 Emails actifs : test.actif@sft2026.fr et reviewer.actif@sft2026.fr", "info")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erreur lors de la génération : {str(e)}", "danger")
        current_app.logger.error(f"Erreur génération données test: {e}")
    
    return redirect(url_for("admin.admin_dashboard"))


@admin.route("/cleanup-test-data")
@login_required 
def cleanup_test_data():
    """Supprime les données de test générées."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    try:
        # Supprimer les utilisateurs de test
        test_users = User.query.filter(
            db.or_(
                User.email.like('%@faux-email-test.com'),
                User.email.like('%@sft2026.fr')
            )
        ).all()
        
        deleted_count = len(test_users)
        
        for user in test_users:
            # Supprimer les communications liées
            for comm in user.authored_communications:
                db.session.delete(comm)
            db.session.delete(user)
        
        db.session.commit()
        
        flash(f"🧹 {deleted_count} utilisateurs de test supprimés", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Erreur lors du nettoyage : {str(e)}", "danger")
    
    return redirect(url_for("admin.admin_dashboard"))


# Script pour générer des PDF de test
@admin.route("/generate-test-pdfs")
@login_required
def generate_test_pdfs():
    """Génère des PDF de test pour les différents types de documents."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    try:
        from weasyprint import HTML, CSS
        import os
        
        # Créer le dossier de destination
        test_pdfs_dir = os.path.join(current_app.static_folder, "uploads", "test_pdfs")
        os.makedirs(test_pdfs_dir, exist_ok=True)
        
        generated_files = []
        
        # =========================
        # 1. RÉSUMÉ (ABSTRACT)
        # =========================
        abstract_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 2cm; font-size: 11pt; line-height: 1.4; }
        .header { text-align: center; margin-bottom: 20px; }
        .title { font-size: 14pt; font-weight: bold; margin-bottom: 10px; }
        .authors { font-size: 12pt; margin-bottom: 10px; }
        .affiliation { font-size: 10pt; font-style: italic; margin-bottom: 20px; }
        .keywords { margin-top: 15px; }
        .section { margin-bottom: 15px; text-align: justify; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">Étude numérique des transferts thermiques dans un échangeur à plaques ondulées pour la récupération de chaleur industrielle</div>
        <div class="authors">J. Dupont¹, M. Martin², S. Bernard¹</div>
        <div class="affiliation">
            ¹ LEMTA, Université de Lorraine, Nancy, France<br>
            ² LRGP, CNRS, Nancy, France
        </div>
    </div>
    
    <div class="section">
        <strong>Résumé :</strong> Cette étude présente une analyse numérique détaillée des performances thermiques d'un échangeur de chaleur à plaques ondulées destiné à la récupération de chaleur fatale industrielle. L'objectif est d'optimiser la géométrie des plaques pour maximiser le transfert thermique tout en minimisant les pertes de charge.
    </div>
    
    <div class="section">
        La modélisation CFD utilise le logiciel ANSYS Fluent avec un maillage structuré de 2.5 millions d'éléments. Les équations de Navier-Stokes sont résolues en régime stationnaire avec le modèle de turbulence k-ε réalisable. Les conditions aux limites imposent une température d'entrée de 80°C côté chaud et 20°C côté froid, avec des débits volumiques variables de 0.1 à 1 m³/h.
    </div>
    
    <div class="section">
        Les résultats montrent qu'une ondulation sinusoïdale avec une amplitude de 5 mm et une longueur d'onde de 20 mm permet d'augmenter le coefficient d'échange thermique de 35% par rapport à des plaques lisses, pour une augmentation des pertes de charge de seulement 15%. L'efficacité thermique atteint 85% dans les conditions optimales.
    </div>
    
    <div class="section">
        Cette configuration permet de récupérer jusqu'à 12 kW de puissance thermique pour une installation industrielle type, avec un temps de retour sur investissement estimé à 2.3 ans.
    </div>
    
    <div class="keywords">
        <strong>Mots-clés :</strong> échangeur de chaleur, récupération thermique, CFD, plaques ondulées, optimisation
    </div>
</body>
</html>
        """
        
        # =========================
        # 2. ARTICLE COMPLET
        # =========================
        article_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Times, serif; margin: 2cm; font-size: 10pt; line-height: 1.5; }
        .header { text-align: center; margin-bottom: 30px; }
        .title { font-size: 14pt; font-weight: bold; margin-bottom: 15px; }
        .authors { font-size: 11pt; margin-bottom: 10px; }
        .affiliation { font-size: 9pt; font-style: italic; margin-bottom: 20px; }
        h2 { font-size: 12pt; font-weight: bold; margin-top: 20px; margin-bottom: 10px; }
        h3 { font-size: 11pt; font-weight: bold; margin-top: 15px; margin-bottom: 8px; }
        .section { margin-bottom: 15px; text-align: justify; }
        .equation { text-align: center; margin: 15px 0; font-style: italic; }
        .figure { text-align: center; margin: 20px 0; }
        .caption { font-size: 9pt; font-style: italic; margin-top: 5px; }
        .references { font-size: 9pt; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">Optimisation thermodynamique d'un cycle de Rankine organique pour la valorisation de chaleur fatale à basse température</div>
        <div class="authors">A. Thermique¹, P. Énergétique², C. Renouvelable¹</div>
        <div class="affiliation">
            ¹ Institut de Recherche en Énergie, Université de Lorraine<br>
            ² Laboratoire de Thermodynamique Appliquée, CNRS
        </div>
    </div>
    
    <h2>1. Introduction</h2>
    <div class="section">
        La récupération de chaleur fatale industrielle représente un enjeu majeur pour l'amélioration de l'efficacité énergétique. Les cycles de Rankine organiques (ORC) constituent une solution prometteuse pour valoriser des sources de chaleur à basse température (80-150°C) en électricité.
    </div>
    
    <h2>2. Méthodologie</h2>
    <h3>2.1. Modélisation thermodynamique</h3>
    <div class="section">
        Le cycle ORC est modélisé par les équations thermodynamiques classiques. Le rendement thermique est défini par :
    </div>
    <div class="equation">η = (W_net) / (Q_in) = (h₁ - h₂) / (h₁ - h₄)</div>
    
    <h3>2.2. Optimisation multi-critères</h3>
    <div class="section">
        L'optimisation vise à maximiser simultanément le rendement thermique et la puissance nette, tout en minimisant la surface d'échange total. Les fluides organiques étudiés sont : R245fa, R1234ze(E), et cyclopentane.
    </div>
    
    <h2>3. Résultats et discussion</h2>
    <div class="section">
        Pour une source chaude à 120°C et un débit de 5 kg/s, le R1234ze(E) présente les meilleures performances avec un rendement de 12.8% et une puissance nette de 185 kW. La surface d'échange totale requise est de 850 m².
    </div>
    
    <div class="figure">
        [Figure 1 : Diagramme T-s du cycle optimisé]
        <div class="caption">Figure 1 : Diagramme température-entropie du cycle ORC optimisé avec R1234ze(E)</div>
    </div>
    
    <h2>4. Conclusion</h2>
    <div class="section">
        Cette étude démontre la faisabilité technique et économique de cycles ORC pour la valorisation de chaleur fatale industrielle. Le fluide R1234ze(E) offre le meilleur compromis performance/impact environnemental.
    </div>
    
    <h2>Références</h2>
    <div class="references">
        [1] Dumont, O., et al. (2021). "Organic Rankine cycle efficiency optimization." Energy, 185, 985-996.<br>
        [2] Tchanche, B.F., et al. (2020). "Low-grade heat conversion." Renewable Energy, 76, 142-150.
    </div>
</body>
</html>
        """
        
        # =========================
        # 3. WORK IN PROGRESS (WIP)
        # =========================
        wip_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 2cm; font-size: 11pt; line-height: 1.4; }
        .header { text-align: center; margin-bottom: 25px; }
        .title { font-size: 13pt; font-weight: bold; margin-bottom: 10px; }
        .authors { font-size: 11pt; margin-bottom: 8px; }
        .affiliation { font-size: 10pt; font-style: italic; margin-bottom: 20px; }
        h2 { font-size: 12pt; font-weight: bold; margin-top: 18px; margin-bottom: 8px; color: #d63384; }
        .section { margin-bottom: 12px; text-align: justify; }
        .progress-note { background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 15px 0; }
        .next-steps { background-color: #d1ecf1; padding: 10px; border-left: 4px solid #17a2b8; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">Développement d'un capteur de flux thermique innovant basé sur des nanofils de silicium</div>
        <div class="authors">L. Nanothermal¹, R. Capteur², M. Innovation¹</div>
        <div class="affiliation">
            ¹ Laboratoire de Micro-Thermique, INSA Lyon<br>
            ² Institut des Nanotechnologies, Grenoble
        </div>
    </div>
    
    <h2>1. Contexte et objectifs</h2>
    <div class="section">
        Ce projet vise à développer un capteur de flux thermique miniaturisé utilisant des nanofils de silicium pour des applications en microélectronique et biomédical. L'objectif est d'atteindre une sensibilité de 10 mV/W.m⁻² avec un temps de réponse inférieur à 1 ms.
    </div>
    
    <h2>2. Avancement actuel</h2>
    <div class="section">
        La fabrication des nanofils par gravure plasma a été maîtrisée. Les premiers prototypes présentent des diamètres de 50-100 nm et des longueurs de 2-5 μm. La caractérisation thermique préliminaire montre des résultats prometteurs.
    </div>
    
    <div class="progress-note">
        <strong>État d'avancement :</strong> Fabrication des échantillons complétée (70%). Tests de caractérisation en cours (40%). Modélisation numérique initiée (30%).
    </div>
    
    <h2>3. Résultats préliminaires</h2>
    <div class="section">
        Les mesures de conductivité thermique des nanofils montrent une réduction de 80% par rapport au silicium massif, due aux effets de confinement quantique. La sensibilité mesurée atteint actuellement 6.5 mV/W.m⁻².
    </div>
    
    <h2>4. Difficultés rencontrées</h2>
    <div class="section">
        - Reproductibilité des processus de fabrication<br>
        - Calibration précise des instruments de mesure<br>
        - Intégration électronique complexe
    </div>
    
    <div class="next-steps">
        <strong>Prochaines étapes :</strong><br>
        - Optimisation des paramètres de gravure (décembre 2025)<br>
        - Développement du circuit de conditionnement (janvier 2026)<br>
        - Tests en conditions réelles (février 2026)
    </div>
    
    <h2>5. Perspectives</h2>
    <div class="section">
        Les résultats préliminaires sont encourageants. Une collaboration avec l'industrie est envisagée pour le transfert technologique. Un brevet sera déposé avant avril 2026.
    </div>
</body>
</html>
        """
        
        # =========================
        # 4. POSTER 1
        # =========================
        poster1_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 1cm; font-size: 24pt; line-height: 1.3; }
        .poster-header { text-align: center; background: linear-gradient(135deg, #007bff, #0056b3); color: white; padding: 40px; margin-bottom: 30px; }
        .title { font-size: 36pt; font-weight: bold; margin-bottom: 20px; }
        .authors { font-size: 28pt; margin-bottom: 15px; }
        .affiliation { font-size: 20pt; }
        .section { margin-bottom: 30px; background: #f8f9fa; padding: 20px; border-radius: 10px; }
        .section-title { font-size: 28pt; font-weight: bold; color: #007bff; margin-bottom: 15px; }
        .highlight-box { background: #e3f2fd; border: 3px solid #2196f3; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .equation { text-align: center; font-size: 20pt; margin: 20px 0; background: white; padding: 10px; border-radius: 5px; }
        .conclusion { background: #c8e6c9; border: 3px solid #4caf50; padding: 20px; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="poster-header">
        <div class="title">Stockage thermique par matériaux à changement de phase pour l'habitat résidentiel</div>
        <div class="authors">V. Stockage • T. Habitat • E. Durable</div>
        <div class="affiliation">Centre de Recherche en Efficacité Énergétique - Université de Savoie</div>
    </div>
    
    <div class="section">
        <div class="section-title">🎯 Objectifs</div>
        • Développer un système de stockage thermique intégré<br>
        • Réduire la consommation énergétique de 30%<br>
        • Améliorer le confort thermique des occupants
    </div>
    
    <div class="section">
        <div class="section-title">🔬 Méthode</div>
        <strong>Matériau :</strong> Paraffine RT28HC (Tf = 28°C)<br>
        <strong>Configuration :</strong> Panneaux muraux de 5 cm d'épaisseur<br>
        <strong>Instrumentation :</strong> 24 thermocouples + capteurs de flux
    </div>
    
    <div class="highlight-box">
        <div class="section-title">📊 Résultats clés</div>
        ✅ <strong>Capacité de stockage :</strong> 185 kJ/kg<br>
        ✅ <strong>Régulation thermique :</strong> ±1.5°C<br>
        ✅ <strong>Économie d'énergie :</strong> 32% mesurée
    </div>
    
    <div class="section">
        <div class="section-title">🏠 Application pratique</div>
        Installation dans maison test de 120 m²<br>
        Monitoring sur 12 mois complets<br>
        Comparaison avec maison témoin identique
    </div>
    
    <div class="conclusion">
        <div class="section-title">🎉 Conclusion</div>
        Le système MCP permet une réduction significative des besoins de chauffage/climatisation tout en améliorant le confort. Potentiel de déploiement à grande échelle validé.
    </div>
</body>
</html>
        """
        
        # =========================
        # 5. POSTER 2
        # =========================
        poster2_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 1cm; font-size: 22pt; line-height: 1.4; }
        .poster-header { text-align: center; background: linear-gradient(135deg, #28a745, #1e7e34); color: white; padding: 35px; margin-bottom: 25px; }
        .title { font-size: 32pt; font-weight: bold; margin-bottom: 18px; }
        .authors { font-size: 26pt; margin-bottom: 12px; }
        .affiliation { font-size: 18pt; }
        .three-col { display: flex; gap: 20px; }
        .col { flex: 1; background: #f8f9fa; padding: 15px; border-radius: 8px; }
        .section-title { font-size: 24pt; font-weight: bold; color: #28a745; margin-bottom: 12px; }
        .data-box { background: #fff3cd; border: 2px solid #ffc107; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }
        .innovation { background: #d4edda; border: 2px solid #28a745; padding: 15px; border-radius: 8px; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="poster-header">
        <div class="title">Pompe à chaleur géothermique innovante avec échangeur hélicoïdal optimisé</div>
        <div class="authors">G. Géothermie • H. Innovation • P. Efficacité</div>
        <div class="affiliation">Institut de Génie Énergétique - École Centrale de Nantes</div>
    </div>
    
    <div class="three-col">
        <div class="col">
            <div class="section-title">🌍 Contexte</div>
            La géothermie de surface représente une solution d'avenir pour le chauffage résidentiel. Notre innovation : échangeur hélicoïdal vertical optimisé pour sols argileux.
        </div>
        
        <div class="col">
            <div class="section-title">⚙️ Innovation</div>
            <div class="innovation">
                <strong>Échangeur hélicoïdal :</strong><br>
                • Diamètre : 1.2 m<br>
                • Profondeur : 30 m<br>
                • Pas : 0.8 m<br>
                • Surface : +40% vs vertical classique
            </div>
        </div>
        
        <div class="col">
            <div class="section-title">📈 Performances</div>
            <div class="data-box">
                <strong>COP mesuré : 4.8</strong><br>
                <small>(vs 3.2 système standard)</small>
            </div>
            <div class="data-box">
                <strong>Puissance : 12 kW</strong><br>
                <small>pour maison 150 m²</small>
            </div>
        </div>
    </div>
    
    <div style="margin-top: 25px; background: #e3f2fd; padding: 20px; border-radius: 10px;">
        <div class="section-title">🏆 Avantages démontrés</div>
        ✅ <strong>Efficacité :</strong> +50% par rapport aux sondes verticales classiques<br>
        ✅ <strong>Coût :</strong> -25% sur l'installation (forage moins profond)<br>
        ✅ <strong>Emprise :</strong> Réduite de 60% au sol<br>
        ✅ <strong>ROI :</strong> 6.5 ans (vs 8.5 ans système standard)
    </div>
    
    <div style="margin-top: 20px; text-align: center; background: #28a745; color: white; padding: 15px; border-radius: 10px;">
        <strong style="font-size: 26pt;">Brevet déposé • Industrialisation en cours • Contact : geothermie-innovation@ec-nantes.fr</strong>
    </div>
</body>
</html>
        """
        
        # Génération des PDFs
        documents = [
            ("abstract_test.pdf", abstract_html, "Résumé"),
            ("article_test.pdf", article_html, "Article"),
            ("wip_test.pdf", wip_html, "Work in Progress"),
            ("poster1_test.pdf", poster1_html, "Poster 1"),
            ("poster2_test.pdf", poster2_html, "Poster 2")
        ]
        
        for filename, html_content, doc_type in documents:
            file_path = os.path.join(test_pdfs_dir, filename)
            HTML(string=html_content).write_pdf(file_path)
            generated_files.append(f"{doc_type}: {filename}")
        
        flash(f"✅ {len(generated_files)} PDF générés avec succès dans static/uploads/test_pdfs/", "success")
        for file_info in generated_files:
            flash(f"📄 {file_info}", "info")
        
    except ImportError:
        flash("❌ WeasyPrint non installé. Installez avec: pip install weasyprint", "danger")
    except Exception as e:
        flash(f"❌ Erreur lors de la génération : {str(e)}", "danger")
        import traceback
        flash(f"Détail : {traceback.format_exc()}", "warning")
    
    return redirect(url_for("admin.admin_dashboard"))


# À ajouter dans routes.py

@admin.route("/test-zone")
@login_required
def test_zone():
    """Zone de test pour les administrateurs."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Statistiques actuelles pour affichage
    stats = {
        'affiliations': Affiliation.query.count(),
        'users_total': User.query.count(),
        'users_reviewers': User.query.filter_by(is_reviewer=True).count(),
        'users_test': User.query.filter(User.email.like('%@faux-email-test.com')).count(),
        'communications': Communication.query.count(),
        'files_uploaded': SubmissionFile.query.count(),
    }
    
    # Vérifier la présence des fichiers importants
    import os
    csv_path = os.path.join(current_app.root_path, 'static', 'content', 'affiliations.csv')
    pdfs_dir = os.path.join(current_app.static_folder, "uploads", "test_pdfs")
    
    file_status = {
        'affiliations_csv_exists': os.path.exists(csv_path),
        'test_pdfs_exist': os.path.exists(pdfs_dir) and len(os.listdir(pdfs_dir)) > 0 if os.path.exists(pdfs_dir) else False,
        'csv_path': csv_path,
        'pdfs_dir': pdfs_dir
    }
    
    return render_template("admin/test_zone.html", stats=stats, file_status=file_status)

@admin.route("/setup-status")
@login_required
def setup_status():
    """Affiche le statut du setup de la base de données."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    status = {
        'affiliations': Affiliation.query.count(),
        'users_total': User.query.count(),
        'users_reviewers': User.query.filter_by(is_reviewer=True).count(),
        'users_admins': User.query.filter_by(is_admin=True).count(),
        'communications': Communication.query.count(),
        'test_users': User.query.filter(User.email.like('%@faux-email-test.com')).count(),
    }
    
    # Messages d'information
    if status['affiliations'] == 0:
        flash("⚠️ Aucune affiliation. Importez d'abord avec /admin/import-affiliations-csv", "warning")
    
    if status['users_reviewers'] == 0:
        flash("⚠️ Aucun reviewer. Créez des données de test avec /admin/generate-test-data", "warning")
    
    for key, count in status.items():
        flash(f"📊 {key.replace('_', ' ').title()} : {count}", "info")
    
    return redirect(url_for("admin.admin_dashboard"))


@admin.route("/send-qr-reminders", methods=["POST"])
@login_required
def send_qr_reminders():
    """Envoie des rappels QR code à tous les auteurs principaux."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    try:
        
        # Récupérer tous les auteurs principaux (premier auteur de chaque communication)
        communications = Communication.query.all()
        authors_communications = {}
        
        # Grouper les communications par auteur principal
        for comm in communications:
            if comm.authors:  # S'assurer qu'il y a des auteurs
                main_author = comm.authors[0]  # Premier auteur = auteur principal
                if main_author.id not in authors_communications:
                    authors_communications[main_author.id] = {
                        'user': main_author,
                        'communications': []
                    }
                authors_communications[main_author.id]['communications'].append(comm)
        
        # Envoyer les emails
        sent_count = 0
        errors = []
        
        for author_data in authors_communications.values():
            try:
                current_app.send_qr_code_reminder_email(
                    author_data['user'], 
                    author_data['communications']
                )
                sent_count += 1
                current_app.logger.info(f"Email QR envoyé à {author_data['user'].email}")
            except Exception as e:
                error_msg = f"Erreur pour {author_data['user'].email}: {str(e)}"
                errors.append(error_msg)
                current_app.logger.error(error_msg)
        
        # Messages de retour
        if sent_count > 0:
            flash(f'Rappels QR code envoyés à {sent_count} auteur(s) principal(aux).', 'success')
        
        if errors:
            for error in errors[:3]:  # Limiter à 3 erreurs affichées
                flash(error, 'warning')
            if len(errors) > 3:
                flash(f"... et {len(errors) - 3} autres erreurs.", 'warning')
                
    except Exception as e:
        current_app.logger.error(f"Erreur générale envoi QR reminders: {e}")
        flash(f"Erreur lors de l'envoi : {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_dashboard'))


@admin.route('/reviews/completed')
@login_required
def completed_reviews():
    """Page de gestion des communications avec reviews terminées."""
    if not current_user.is_admin:
        abort(403)
    
    # Communications avec au moins une review terminée
    communications_with_reviews = db.session.query(Communication).join(
        ReviewAssignment
    ).join(Review).filter(
        Review.completed == True
    ).distinct().all()
    
    # Construire les données pour chaque communication
    communications_data = []
    for comm in communications_with_reviews:
        # Récupérer toutes les reviews de cette communication
        reviews = Review.query.filter_by(
            communication_id=comm.id,
            completed=True
        ).all()
        
        # Statistiques des reviews
        total_reviews = len(reviews)
        avg_score = sum(r.score for r in reviews if r.score) / total_reviews if total_reviews > 0 else 0
        recommendations = [r.recommendation.value for r in reviews if r.recommendation]
        biot_fourier_nominations = sum(1 for r in reviews if r.recommend_for_biot_fourier)
        
        communications_data.append({
            'communication': comm,
            'reviews': reviews,
            'total_reviews': total_reviews,
            'avg_score': round(avg_score, 1),
            'recommendations': recommendations,
            'biot_fourier_nominations': biot_fourier_nominations,
            'decision_made': hasattr(comm, 'final_decision') and comm.final_decision is not None
        })
    
    # Trier par score moyen décroissant
    communications_data.sort(key=lambda x: x['avg_score'], reverse=True)
    
    return render_template('admin/completed_reviews.html', 
                         communications_data=communications_data)


@admin.route('/reviews/communication/<int:comm_id>/details')
@login_required
def review_communication_details(comm_id):
    """Affiche les détails complets d'une communication et ses reviews."""
    if not current_user.is_admin:
        abort(403)
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Récupérer toutes les reviews terminées
    reviews = Review.query.filter_by(
        communication_id=comm_id,
        completed=True
    ).all()
    
    if not reviews:
        flash('Aucune review terminée pour cette communication.', 'warning')
        return redirect(url_for('admin.completed_reviews'))
    
    # Statistiques détaillées
    stats = {
        'total_reviews': len(reviews),
        'avg_score': sum(r.score for r in reviews if r.score) / len(reviews) if reviews else 0,
        'recommendations': {
            'accepter': len([r for r in reviews if r.recommendation and r.recommendation.value == 'accepter']),
            'rejeter': len([r for r in reviews if r.recommendation and r.recommendation.value == 'rejeter']),
            'réviser': len([r for r in reviews if r.recommendation and r.recommendation.value == 'réviser'])
        },
        'biot_fourier_count': len([r for r in reviews if r.recommend_for_biot_fourier])
    }
    
    return render_template('admin/review_details.html',
                         communication=communication,
                         reviews=reviews,
                         stats=stats)


# Étape 3 : Dans admin.py, ajoutez cette route (à la fin du fichier)

@admin.route('/communications/<int:comm_id>/decision', methods=['POST'])
@login_required
def make_communication_decision(comm_id):
    """Prend une décision finale sur une communication."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Vérifier qu'on peut prendre une décision
    if not communication.can_make_decision():
        flash('Impossible de prendre une décision sur cette communication.', 'warning')
        return redirect(url_for('admin.review_communication_details', comm_id=comm_id))
    
    # Récupérer les données du formulaire
    decision = request.form.get('decision')
    comments = request.form.get('comments', '').strip()
    
    # Validation
    if decision not in ['accepter', 'rejeter', 'reviser']:
        flash('Décision invalide.', 'danger')
        return redirect(url_for('admin.review_communication_details', comm_id=comm_id))
    
    try:
        # Prendre la décision (SANS envoi automatique)
        communication.make_final_decision(
            decision=decision,
            admin_user=current_user,
            comments=comments if comments else None
        )
        
        db.session.commit()
        
        decision_text = {
            'accepter': 'acceptée',
            'rejeter': 'rejetée', 
            'reviser': 'envoyée en révision'
        }
        
        flash(f'Communication {decision_text[decision]} avec succès.', 'success')
        return redirect(url_for('admin.review_communication_details', comm_id=comm_id))
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de la décision: {e}")
        flash(f'Erreur lors de l\'enregistrement de la décision: {str(e)}', 'danger')
        return redirect(url_for('admin.review_communication_details', comm_id=comm_id))


@admin.route('/communications/<int:comm_id>/send-notification', methods=['POST'])
@login_required
def send_decision_notification(comm_id):
    """Envoie la notification de décision aux auteurs."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Vérifier qu'une décision a été prise
    if not communication.decision_made:
        flash('Aucune décision à notifier.', 'warning')
        return redirect(url_for('admin.review_communication_details', comm_id=comm_id))
    
    # Vérifier si déjà envoyée
    if communication.decision_notification_sent:
        flash('Notification déjà envoyée.', 'info')
        return redirect(url_for('admin.review_communication_details', comm_id=comm_id))
    
    try:
        current_app.send_decision_notification_email(
            communication, 
            communication.final_decision, 
            communication.decision_comments
        )
        
        # Marquer comme envoyée
        communication.decision_notification_sent = True
        communication.decision_notification_sent_at = datetime.utcnow()
        communication.decision_notification_error = None
        
        db.session.commit()
        
        # Compter les auteurs notifiés
        author_count = len([a for a in communication.authors if a.email])
        flash(f'Notification envoyée à {author_count} auteur(s).', 'success')
        
    except Exception as e:
        # Enregistrer l'erreur
        communication.decision_notification_error = str(e)
        db.session.commit()
        
        current_app.logger.error(f"Erreur envoi notification: {e}")
        flash(f'Erreur lors de l\'envoi : {str(e)}', 'danger')
    
    return redirect(url_for('admin.review_communication_details', comm_id=comm_id))

@admin.route('/communications/<int:comm_id>/decision/reset', methods=['POST'])
@login_required
def reset_communication_decision(comm_id):
    """Annule une décision prise sur une communication (pour correction)."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    communication = Communication.query.get_or_404(comm_id)
    
    if not communication.decision_made:
        flash('Aucune décision à annuler sur cette communication.', 'warning')
        return redirect(url_for('admin.review_communication_details', comm_id=comm_id))
    
    try:
        # Annuler la décision
        old_decision = communication.final_decision
        communication.reset_decision(current_user)
        
        db.session.commit()
        
        flash(f'Décision "{old_decision}" annulée. Communication remise en review.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de l'annulation: {e}")
        flash(f'Erreur lors de l\'annulation de la décision: {str(e)}', 'danger')
    
    return redirect(url_for('admin.review_communication_details', comm_id=comm_id))


@admin.route('/reviews/biot-fourier-candidates')
@login_required
def biot_fourier_candidates():
    """Page des candidats au prix Biot-Fourier."""
    if not current_user.is_admin:
        abort(403)
    
    # Récupérer toutes les communications avec au moins une nomination Biot-Fourier
    candidates_data = []
    
    # Requête pour trouver les communications avec reviews contenant recommend_for_biot_fourier = True
    communications_with_nominations = db.session.query(Communication).join(
        Review
    ).filter(
        Review.completed == True,
        Review.recommend_for_biot_fourier == True
    ).distinct().all()
    
    for comm in communications_with_nominations:
        # Récupérer toutes les reviews de cette communication
        reviews = Review.query.filter_by(
            communication_id=comm.id,
            completed=True
        ).all()
        
        # Compter les nominations Biot-Fourier
        nominations_count = len([r for r in reviews if r.recommend_for_biot_fourier])
        total_reviews = len(reviews)
        
        # Calculer le score moyen
        avg_score = sum(r.score for r in reviews if r.score) / total_reviews if total_reviews > 0 else 0
        
        # Récupérer les reviewers qui ont nominé
        nominating_reviewers = [r.reviewer.full_name for r in reviews if r.recommend_for_biot_fourier]
        
        candidates_data.append({
            'communication': comm,
            'nominations_count': nominations_count,
            'total_reviews': total_reviews,
            'nomination_percentage': (nominations_count / total_reviews * 100) if total_reviews > 0 else 0,
            'avg_score': round(avg_score, 1),
            'nominating_reviewers': nominating_reviewers,
            'reviews': reviews
        })
    
    # Trier par nombre de nominations puis par score moyen
    candidates_data.sort(key=lambda x: (-x['nominations_count'], -x['avg_score']))
    
    # Statistiques
    stats = {
        'total_candidates': len(candidates_data),
        'unanimous_nominations': len([c for c in candidates_data if c['nomination_percentage'] == 100]),
        'majority_nominations': len([c for c in candidates_data if c['nomination_percentage'] >= 50]),
        'total_nominations': sum(c['nominations_count'] for c in candidates_data)
    }
    
    return render_template('admin/biot_fourier_candidates.html',
                         candidates_data=candidates_data,
                         stats=stats)



@admin.route('/communications/<int:comm_id>/biot-fourier-audition', methods=['POST'])
@login_required
def select_for_biot_fourier_audition(comm_id):
    """Sélectionne une communication pour l'audition Prix Biot-Fourier."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Vérifier qu'elle est bien candidate (au moins une nomination)
    nominations_count = Review.query.filter_by(
        communication_id=comm_id,
        completed=True,
        recommend_for_biot_fourier=True
    ).count()
    
    if nominations_count == 0:
        flash('Cette communication n\'a pas été nominée pour le prix Biot-Fourier.', 'warning')
        return redirect(url_for('admin.biot_fourier_candidates'))
    
    # Vérifier si déjà sélectionnée
    if communication.biot_fourier_audition_selected:
        flash('Cette communication est déjà sélectionnée pour l\'audition.', 'info')
        return redirect(url_for('admin.biot_fourier_candidates'))
    
    try:
        # Sélectionner pour l'audition
        communication.biot_fourier_audition_selected = True
        communication.biot_fourier_audition_selected_at = datetime.utcnow()
        communication.biot_fourier_audition_selected_by_id = current_user.id
        
        db.session.commit()
        
        flash(f'Communication sélectionnée pour l\'audition Prix Biot-Fourier.', 'success')
        
        # Proposer d'envoyer la notification
        return redirect(url_for('admin.biot_fourier_candidates'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur sélection audition: {e}")
        flash(f'Erreur lors de la sélection: {str(e)}', 'danger')
        return redirect(url_for('admin.biot_fourier_candidates'))


@admin.route('/communications/<int:comm_id>/biot-fourier-notify', methods=['POST'])
@login_required
def notify_biot_fourier_audition(comm_id):
    """Envoie la notification d'audition à l'auteur principal."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Vérifier qu'elle est sélectionnée pour l'audition
    if not communication.biot_fourier_audition_selected:
        flash('Cette communication n\'est pas sélectionnée pour l\'audition.', 'warning')
        return redirect(url_for('admin.biot_fourier_candidates'))
    
    # Vérifier si notification déjà envoyée
    if communication.biot_fourier_audition_notification_sent:
        flash('Notification d\'audition déjà envoyée.', 'info')
        return redirect(url_for('admin.biot_fourier_candidates'))
    
    try:
        # Envoyer la notification
        current_app.send_biot_fourier_audition_notification(communication)
        
        # Marquer comme envoyée
        communication.biot_fourier_audition_notification_sent = True
        communication.biot_fourier_audition_notification_sent_at = datetime.utcnow()
        
        db.session.commit()
        
        # Récupérer l'auteur principal
        main_author = communication.authors[0] if communication.authors else None
        author_name = main_author.full_name if main_author else "auteur principal"
        
        flash(f'Notification d\'audition envoyée à {author_name}.', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Erreur notification audition: {e}")
        flash(f'Erreur lors de l\'envoi: {str(e)}', 'danger')
    
    return redirect(url_for('admin.biot_fourier_candidates'))


@admin.route('/communications/<int:comm_id>/biot-fourier-unselect', methods=['POST'])
@login_required
def unselect_biot_fourier_audition(comm_id):
    """Annule la sélection pour l'audition (si erreur)."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    communication = Communication.query.get_or_404(comm_id)
    
    if not communication.biot_fourier_audition_selected:
        flash('Cette communication n\'est pas sélectionnée pour l\'audition.', 'info')
        return redirect(url_for('admin.biot_fourier_candidates'))
    
    try:
        # Réinitialiser la sélection
        communication.biot_fourier_audition_selected = False
        communication.biot_fourier_audition_selected_at = None
        communication.biot_fourier_audition_selected_by_id = None
        communication.biot_fourier_audition_notification_sent = False
        communication.biot_fourier_audition_notification_sent_at = None
        
        db.session.commit()
        
        flash('Sélection pour l\'audition annulée.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur annulation sélection: {e}")
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('admin.biot_fourier_candidates'))


# À ajouter dans admin.py

@admin.route('/reviews/send-grouped-notifications', methods=['GET', 'POST'])
@login_required
def send_grouped_notifications():
    """Page pour envoyer les notifications groupées aux reviewers."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Récupérer les assignations en attente (pas encore notifiées)
    pending_assignments = ReviewAssignment.query.filter_by(
        status='assigned',
        notification_sent_at=None
    ).all()
    
    # Grouper par reviewer pour l'affichage
    reviewers_preview = {}
    for assignment in pending_assignments:
        reviewer_id = assignment.reviewer_id
        if reviewer_id not in reviewers_preview:
            reviewers_preview[reviewer_id] = {
                'reviewer': assignment.reviewer,
                'assignments': []
            }
        reviewers_preview[reviewer_id]['assignments'].append(assignment)
    
    if request.method == 'POST':
        try:
            from .emails import send_grouped_review_notifications
            result = send_grouped_review_notifications()
            
            # Sauvegarder les marquages de notification
            db.session.commit()
            
            # Messages de retour
            if result['sent'] > 0:
                flash(f"✅ {result['sent']} reviewer(s) notifié(s) pour {result['total_assignments']} assignation(s).", "success")
            
            if result['errors']:
                for error in result['errors'][:3]:  # Limite à 3 erreurs affichées
                    flash(f"⚠️ {error}", "warning")
                
                if len(result['errors']) > 3:
                    flash(f"... et {len(result['errors']) - 3} autres erreurs.", "warning")
            
            if result['sent'] == 0:
                flash("Aucune notification envoyée.", "info")
            
            return redirect(url_for('admin.send_grouped_notifications'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur envoi notifications groupées: {e}")
            flash(f"❌ Erreur lors de l'envoi : {str(e)}", "danger")
    
    # Statistiques pour l'affichage
    stats = {
        'total_reviewers': len(reviewers_preview),
        'total_assignments': len(pending_assignments),
        'avg_per_reviewer': len(pending_assignments) / len(reviewers_preview) if reviewers_preview else 0
    }
    
    return render_template('admin/send_grouped_notifications.html', 
                         reviewers_preview=reviewers_preview,
                         stats=stats)


@admin.route('/reviews/preview-grouped-email/<int:reviewer_id>')
@login_required
def preview_grouped_email(reviewer_id):
    """Prévisualise l'email groupé pour un reviewer spécifique."""
    if not current_user.is_admin:
        abort(403)
    
    reviewer = User.query.get_or_404(reviewer_id)
    
    # Récupérer ses assignations en attente
    assignments = ReviewAssignment.query.filter_by(
        reviewer_id=reviewer_id,
        status='assigned',
        notification_sent_at=None
    ).all()
    
    if not assignments:
        flash("Aucune assignation en attente pour ce reviewer.", "info")
        return redirect(url_for('admin.send_grouped_notifications'))
    
    return render_template('admin/preview_grouped_email.html', 
                         reviewer=reviewer, 
                         assignments=assignments)







# À ajouter dans app/admin.py

@admin.route('/communications-dashboard')
@login_required
def communications_dashboard():
    """Tableau de bord synthétique de toutes les communications."""
    if not current_user.is_admin:
        abort(403)
    
    # Utiliser le système de statistiques unifié
    from app.statistics import StatisticsManager
    
    # Récupérer tous les articles et WIPs
    articles = Communication.query.filter_by(type='article').order_by(
        Communication.created_at.desc()
    ).all()
    
    wips = Communication.query.filter_by(type='wip').order_by(
        Communication.created_at.desc()
    ).all()
    
    # Statistiques harmonisées
    stats = StatisticsManager.get_communications_dashboard_stats()
    
    # Préparer les données pour les cartes de statistiques
    stats_cards = [
        StatisticsManager.get_stat_card_data(
            'articles', 
            stats['communications']['articles']['total'],
            'articles',
            'primary'
        ),
        StatisticsManager.get_stat_card_data(
            'wips', 
            stats['communications']['wips']['total'],
            'wips', 
            'purple'
        ),
        StatisticsManager.get_stat_card_data(
            'en_review', 
            stats['reviews']['en_cours'],
            'reviews',
            'orange'
        ),
        StatisticsManager.get_stat_card_data(
            'acceptés', 
            stats['communications']['articles']['acceptés'],
            'acceptes',
            'success'
        ),
    ]
    
    # Charger les thématiques pour les filtres
    from app.config_loader import ThematiqueLoader
    thematiques = ThematiqueLoader.load_themes()
    
    return render_template('admin/communications_dashboard.html',
                         articles=articles,
                         wips=wips,
                         stats=stats,
                         stats_cards=stats_cards,
                         thematiques=thematiques)

# Vers la ligne 2850-2890 dans admin.py, remplacez cette section :

@admin.route('/send-bulk-email', methods=['POST'])
@login_required
def send_bulk_email():
    """Envoi d'emails groupés aux auteurs ou reviewers."""
    if not current_user.is_admin:
        abort(403)
    
    try:
        data = request.get_json()
        recipient_type = data.get('recipient')  # 'authors' ou 'reviewers'
        subject = data.get('subject')
        content = data.get('content')
        article_ids = data.get('articles', [])
        wip_ids = data.get('wips', [])
        
        if not subject or not content:
            return jsonify({'success': False, 'message': 'Sujet et contenu requis'})
        
        emails_sent = 0
        errors = []
        
        # Traiter les articles
        for article_id in article_ids:
            article = Communication.query.get(article_id)
            if not article:
                continue
                
            try:
                if recipient_type == 'authors':
                    # Envoyer aux auteurs
                    for author in article.authors:
                        if author.email:
                            send_bulk_email_to_user(author, subject, content, [article])
                            emails_sent += 1
                            
                elif recipient_type == 'reviewers':
                    # Envoyer aux reviewers
                    for review in article.reviews:
                        if review.reviewer.email:
                            send_bulk_email_to_user(review.reviewer, subject, content, [article])
                            emails_sent += 1
                            
            except Exception as e:
                errors.append(f"Article {article_id}: {str(e)}")
        
        # Traiter les WIPs
        for wip_id in wip_ids:
            wip = Communication.query.get(wip_id)
            if not wip:
                continue
                
            try:
                if recipient_type == 'authors':
                    # Envoyer aux auteurs (WIP n'ont pas de reviewers)
                    for author in wip.authors:
                        if author.email:
                            send_bulk_email_to_user(author, subject, content, [wip])
                            emails_sent += 1
                            
            except Exception as e:
                errors.append(f"WIP {wip_id}: {str(e)}")
        
        # Log de l'action
        current_app.logger.info(f"Email groupé envoyé par {current_user.email}: {emails_sent} emails")
        
        if errors:
            return jsonify({
                'success': True, 
                'message': f'{emails_sent} emails envoyés avec {len(errors)} erreurs',
                'errors': errors
            })
        else:
            return jsonify({
                'success': True, 
                'message': f'{emails_sent} emails envoyés avec succès'
            })
            
    except Exception as e:
        current_app.logger.error(f"Erreur envoi email groupé: {str(e)}")
        return jsonify({'success': False, 'message': f'Erreur serveur: {str(e)}'})


def send_bulk_email_to_user(user, subject, content, communications=None):
    """Fonction utilitaire pour envoyer un email groupé avec template HTML."""
    from flask_mail import Message
    from app import mail
    from flask import render_template
    
    try:
        # Utiliser le template d'email groupé
        html_body = render_template('emails/bulk_email.html',
                                  recipient=user,
                                  email_subject=subject,
                                  email_content=content,
                                  communications=communications or [])
        
        # Personnaliser le contenu texte
        personalized_content = content.replace('[NOM]', user.last_name or '')
        personalized_content = personalized_content.replace('[PRENOM]', user.first_name or '')
        
        # Ajouter les titres des communications pour la version texte
        if communications:
            comm_titles = '\n'.join([f"- {comm.title} (ID: {comm.id})" for comm in communications])
            personalized_content += f"\n\nCommunication(s) concernée(s):\n{comm_titles}"
        
        msg = Message(
            subject=subject,
            recipients=[user.email],
            body=personalized_content,  # Version texte
            html=html_body,  # Version HTML avec template
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        
        mail.send(msg)
        
    except Exception as e:
        current_app.logger.error(f"Erreur envoi email groupé à {user.email}: {str(e)}")
        raise

def send_email_to_user(user, subject, content, communication=None):
    """Fonction utilitaire pour envoyer un email à un utilisateur avec le nouveau système centralisé."""
    try:
        # Utiliser le nouveau système centralisé d'emails
        from app.emails import send_any_email_with_themes
        
        # Préparer le contexte de base
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'EMAIL_CONTENT': content,
            'call_to_action_url': url_for('main.mes_communications', _external=True)
        }
        
        # Si c'est lié à une communication
        if communication:
            base_context.update({
                'COMMUNICATION_TITLE': communication.title,
                'COMMUNICATION_ID': communication.id,
                'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True)
            })
        
        # Envoyer via le système centralisé - utilise automatiquement emails.yml
        # On peut créer un template générique pour ce type d'email admin
        send_custom_admin_email(user.email, subject, content, base_context, communication)
        
        current_app.logger.info(f"Email admin envoyé à {user.email}")
        
    except Exception as e:
        current_app.logger.error(f"Erreur envoi email admin à {user.email}: {str(e)}")
        raise

# Remplacer dans app/admin.py la fonction send_email_to_user

def send_email_to_user(user, subject, content, communication=None):
    """Fonction utilitaire pour envoyer un email à un utilisateur avec le nouveau système centralisé."""
    try:
        # Utiliser le nouveau système centralisé d'emails
        from app.emails import send_any_email_with_themes
        
        # Préparer le contexte de base
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'EMAIL_CONTENT': content,
            'call_to_action_url': url_for('main.mes_communications', _external=True)
        }
        
        # Si c'est lié à une communication
        if communication:
            base_context.update({
                'COMMUNICATION_TITLE': communication.title,
                'COMMUNICATION_ID': communication.id,
                'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True)
            })
        
        # Envoyer via le système centralisé - utilise automatiquement emails.yml
        # On peut créer un template générique pour ce type d'email admin
        send_custom_admin_email(user.email, subject, content, base_context, communication)
        
        current_app.logger.info(f"Email admin envoyé à {user.email}")
        
    except Exception as e:
        current_app.logger.error(f"Erreur envoi email admin à {user.email}: {str(e)}")
        raise

def send_custom_admin_email(recipient_email, subject, content, context, communication=None):
    """Envoie un email personnalisé d'admin en utilisant le système centralisé."""
    try:
        from app.emails import send_email, _build_html_email, _build_text_email, prepare_email_context
        
        # Préparer le contexte avec conversion des thématiques
        full_context = prepare_email_context(context, communication=communication)
        
        # Construire le contenu personnalisé  
        personalized_content = content.replace('[PRENOM]', full_context.get('USER_FIRST_NAME', ''))
        personalized_content = personalized_content.replace('[NOM]', full_context.get('USER_LAST_NAME', ''))
        personalized_content = personalized_content.replace('[TITRE_COMMUNICATION]', full_context.get('COMMUNICATION_TITLE', ''))
        personalized_content = personalized_content.replace('[ID_COMMUNICATION]', str(full_context.get('COMMUNICATION_ID', '')))
        
        # Construire l'email avec le style standard
        config_loader = current_app.config_loader
        signature = config_loader.get_email_signature('default', **full_context)
        
        # Version texte
        text_parts = [
            f"Bonjour {full_context.get('USER_FIRST_NAME', '')},",
            f"\n\n{personalized_content}"
        ]
        
        if communication:
            text_parts.append(f"\n\nCommunication : {communication.title} (ID: {communication.id})")
            if hasattr(communication, 'thematiques') and communication.thematiques:
                from app.emails import _convert_codes_to_names
                themes_text = _convert_codes_to_names(communication.thematiques)
                text_parts.append(f"Thématiques : {themes_text}")
        
        if full_context.get('call_to_action_url'):
            text_parts.append(f"\n\nAccéder à la plateforme : {full_context['call_to_action_url']}")
            
        if signature:
            text_parts.append(f"\n\n{signature}")
        
        text_body = ''.join(text_parts)
        
        # Version HTML
        html_parts = [
            f"<p><strong>Bonjour {full_context.get('USER_FIRST_NAME', '')},</strong></p>",
            f"<p>{personalized_content.replace(chr(10), '<br>')}</p>"
        ]
        
        if communication:
            html_parts.append(f"""
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #007bff;">
                <h4 style="margin-top: 0; color: #007bff;">Communication concernée :</h4>
                <ul>
                    <li><strong>Titre :</strong> {communication.title}</li>
                    <li><strong>ID :</strong> {communication.id}</li>
            """)
            
            if hasattr(communication, 'thematiques') and communication.thematiques:
                from app.emails import _convert_codes_to_names
                themes_html = _convert_codes_to_names(communication.thematiques)
                html_parts.append(f"<li><strong>Thématiques :</strong> {themes_html}</li>")
            
            html_parts.append("</ul></div>")
        
        if full_context.get('call_to_action_url'):
            html_parts.append(f'''
            <div style="text-align: center; margin: 30px 0;">
                <a href="{full_context['call_to_action_url']}" 
                   style="background-color: #007bff; color: white; padding: 12px 25px; 
                          text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                    Accéder à mes communications
                </a>
            </div>
            ''')
        
        if signature:
            signature_html = signature.replace('\n', '<br>')
            html_parts.append(f"<hr><p>{signature_html}</p>")
        
        html_body = ''.join(html_parts)
        
        # Envoyer l'email
        send_email(subject, [recipient_email], text_body, html_body)
        
    except Exception as e:
        current_app.logger.error(f"Erreur envoi email admin personnalisé: {e}")
        raise

@admin.route('/email-authors/<int:comm_id>')
@login_required
def email_authors(comm_id):
    """Page pour composer et envoyer un email aux auteurs d'une communication."""
    if not current_user.is_admin:
        abort(403)
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Importer la fonction depuis emails.py
    from app.emails import get_admin_email_templates
    
    # Récupérer les templates depuis la configuration
    email_templates = get_admin_email_templates()
    
    # Ajouter des variables spécifiques à cette communication dans les templates
    # pour que les placeholders soient correctement remplacés
    context_variables = {
        'COMMUNICATION_TITLE': communication.title,
        'COMMUNICATION_ID': communication.id,
        'COMMUNICATION_TYPE': communication.type.title()
    }
    
    # Remplacer les variables dans les templates pour l'affichage JavaScript
    processed_templates = {}
    for template_key, template_data in email_templates.items():
        processed_templates[template_key] = {
            'subject': template_data['subject'],
            'content': template_data['content']
        }
        
        # Remplacer les variables spécifiques à cette communication
        for var_name, var_value in context_variables.items():
            placeholder = f'[{var_name}]'
            if placeholder in processed_templates[template_key]['subject']:
                processed_templates[template_key]['subject'] = processed_templates[template_key]['subject'].replace(placeholder, str(var_value))
            if placeholder in processed_templates[template_key]['content']:
                processed_templates[template_key]['content'] = processed_templates[template_key]['content'].replace(placeholder, str(var_value))
    
    return render_template('admin/email_authors.html', 
                         communication=communication,
                         email_templates=processed_templates)



@admin.route('/email-reviewers/<int:comm_id>')
@login_required
def email_reviewers(comm_id):
    """Page pour composer et envoyer un email aux reviewers d'une communication."""
    if not current_user.is_admin:
        abort(403)
    
    communication = Communication.query.get_or_404(comm_id)
    
    if not communication.reviews:
        flash('Cette communication n\'a pas de reviewers assignés.', 'warning')
        return redirect(url_for('admin.communications_dashboard'))
    
    # Templates d'emails prédéfinis pour reviewers
    email_templates = {
        'assignation': {
            'subject': f'Nouvelle review assignée: {communication.title}',
            'content': '''Une nouvelle review vous a été assignée pour la communication "[TITRE_COMMUNICATION]" (ID: [ID_COMMUNICATION]).

Vous pouvez accéder à votre espace reviewer pour effectuer cette évaluation.

Merci pour votre contribution au processus de relecture.'''
        },
        'rappel': {
            'subject': f'Rappel - Review en attente: {communication.title}',
            'content': '''Nous vous rappelons qu'une review est en attente de votre part pour la communication "[TITRE_COMMUNICATION]" (ID: [ID_COMMUNICATION]).

Merci de bien vouloir effectuer cette évaluation dans les meilleurs délais.'''
        },
        'rappel_urgent': {
            'subject': f'URGENT - Review en attente: {communication.title}',
            'content': '''Nous vous rappelons de manière urgente qu'une review est en attente depuis plusieurs jours pour la communication "[TITRE_COMMUNICATION]" (ID: [ID_COMMUNICATION]).

Cette évaluation est importante pour respecter nos délais. Merci de l'effectuer au plus vite ou de nous signaler si vous rencontrez des difficultés.'''
        },
        'remerciement': {
            'subject': f'Merci pour votre review: {communication.title}',
            'content': '''Nous vous remercions pour avoir effectué la review de la communication "[TITRE_COMMUNICATION]" (ID: [ID_COMMUNICATION]).

Votre contribution est précieuse pour maintenir la qualité scientifique de notre congrès.'''
        },
        'information': {
            'subject': f'Information reviewer - SFT 2026',
            'content': '''Nous souhaitons vous informer concernant la communication "[TITRE_COMMUNICATION]" (ID: [ID_COMMUNICATION]).

[Votre information ici]'''
        }
    }
    
    return render_template('admin/email_reviewers.html', 
                         communication=communication,
                         email_templates=email_templates)


@admin.route('/communication/<int:comm_id>')
@login_required
def view_communication_details(comm_id):
    """Page de détails d'une communication."""
    if not current_user.is_admin:
        abort(403)
    
    communication = Communication.query.get_or_404(comm_id)
    
    # Récupérer les informations supplémentaires
    review_assignments = ReviewAssignment.query.filter_by(
        communication_id=comm_id
    ).all()
    
    return render_template('admin/communication_details.html',
                         communication=communication,
                         review_assignments=review_assignments)


@admin.route('/export-communications-csv')
@login_required
def export_communications_csv():
    """Exporte toutes les communications en CSV."""
    if not current_user.is_admin:
        abort(403)
    
    import csv
    import io
    from flask import make_response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # En-têtes
    writer.writerow([
        'ID', 'Type', 'Titre', 'Statut', 'Auteurs', 'Thématiques', 
        'Date création', 'Date soumission résumé', 'Date soumission article',
        'Reviewers', 'Décision finale', 'Date décision'
    ])
    
    # Récupérer toutes les communications
    communications = Communication.query.order_by(Communication.id).all()
    
    for comm in communications:
        # Formater les auteurs
        auteurs = '; '.join([f"{a.first_name} {a.last_name}" for a in comm.authors])
        
        # Formater les thématiques
        thematiques = ''
        if comm.thematiques:
            thematiques = '; '.join([f"{t['code']}-{t['nom']}" for t in comm.thematiques])
        
        # Formater les reviewers
        reviewers = ''
        if comm.reviews:
            reviewers = '; '.join([f"{r.reviewer.first_name} {r.reviewer.last_name}" for r in comm.reviews])
        
        writer.writerow([
            comm.id,
            comm.type,
            comm.title,
            comm.status.value,
            auteurs,
            thematiques,
            comm.created_at.strftime('%Y-%m-%d %H:%M') if comm.created_at else '',
            comm.resume_submitted_at.strftime('%Y-%m-%d %H:%M') if comm.resume_submitted_at else '',
            comm.article_submitted_at.strftime('%Y-%m-%d %H:%M') if comm.article_submitted_at else '',
            reviewers,
            comm.final_decision or '',
            comm.decision_date.strftime('%Y-%m-%d %H:%M') if comm.decision_date else ''
        ])
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=communications_sft2026_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
    
    return response


@admin.route('/stats-communications')
@login_required
def stats_communications():
    """Page de statistiques détaillées des communications."""
    if not current_user.is_admin:
        abort(403)
    
    # Statistiques par statut
    stats_status = {}
    for status in CommunicationStatus:
        count = Communication.query.filter_by(status=status).count()
        stats_status[status.value] = count
    
    # Statistiques par thématique
    from app.config_loader import ThematiqueLoader
    thematiques = ThematiqueLoader.load_themes()
    stats_thematiques = {}
    
    for theme in thematiques:
        count = Communication.query.filter(
            Communication.thematiques_codes.like(f'%{theme["code"]}%')
        ).count()
        stats_thematiques[theme['code']] = {
            'nom': theme['nom'],
            'count': count
        }
    
    # Évolution des soumissions par mois
    from sqlalchemy import func, extract
    monthly_stats = db.session.query(
        extract('year', Communication.created_at).label('year'),
        extract('month', Communication.created_at).label('month'),
        func.count(Communication.id).label('count')
    ).group_by('year', 'month').order_by('year', 'month').all()
    
    # Statistiques des reviews
    review_stats = {
        'total_reviews': Review.query.count(),
        'completed_reviews': Review.query.filter_by(completed=True).count(),
        'pending_reviews': Review.query.filter_by(completed=False).count(),
        'avg_review_time': 'À calculer'  # Vous pouvez ajouter le calcul
    }
    
    return render_template('admin/communications_stats.html',
                         stats_status=stats_status,
                         stats_thematiques=stats_thematiques,
                         monthly_stats=monthly_stats,
                         review_stats=review_stats)


@admin.route('/send-individual-email', methods=['POST'])
@login_required
def send_individual_email():
    """Envoi d'email individuel aux auteurs ou reviewers d'une communication."""
    if not current_user.is_admin:
        abort(403)
    
    try:
        communication_id = request.form.get('communication_id')
        recipient_type = request.form.get('recipient_type')  # 'authors' ou 'reviewers'
        subject = request.form.get('subject')
        content = request.form.get('content')
        copy_admin = request.form.get('copy_admin') == 'on'
        selected_reviewers = request.form.get('selected_reviewers', '')
        
        if not all([communication_id, recipient_type, subject, content]):
            flash('Tous les champs sont requis.', 'danger')
            return redirect(request.referrer)
        
        communication = Communication.query.get_or_404(communication_id)
        emails_sent = 0
        recipients = []
        
        if recipient_type == 'authors':
            # Envoyer aux auteurs
            for author in communication.authors:
                if author.email:
                    send_email_to_user(author, subject, content, communication)
                    emails_sent += 1
                    recipients.append(f"{author.first_name} {author.last_name} ({author.email})")
                    
        elif recipient_type == 'reviewers':
            # Envoyer aux reviewers sélectionnés
            if selected_reviewers:
                reviewer_ids = [int(id) for id in selected_reviewers.split(',') if id.strip()]
            else:
                reviewer_ids = [review.reviewer.id for review in communication.reviews]
            
            for review in communication.reviews:
                if review.reviewer.id in reviewer_ids and review.reviewer.email:
                    send_email_to_user(review.reviewer, subject, content, communication)
                    emails_sent += 1
                    recipients.append(f"{review.reviewer.first_name} {review.reviewer.last_name} ({review.reviewer.email})")
        
        # Envoyer une copie à l'admin si demandé
        if copy_admin and current_user.email:
            copy_subject = f"[COPIE] {subject}"
            copy_content = f"COPIE de l'email envoyé concernant la communication #{communication.id}\n\nDestinataires: {', '.join(recipients)}\n\n" + content
            
            from flask_mail import Message
            from app import mail
            
            msg = Message(
                subject=copy_subject,
                recipients=[current_user.email],
                body=copy_content,
                sender=current_app.config.get('MAIL_DEFAULT_SENDER')
            )
            mail.send(msg)
        
        # Log de l'action
        current_app.logger.info(f"Email individuel envoyé par {current_user.email} pour communication {communication_id}: {emails_sent} destinataires")
        
        flash(f'Email envoyé avec succès à {emails_sent} destinataire(s).', 'success')
        
        if copy_admin:
            flash('Une copie vous a été envoyée.', 'info')
            
    except Exception as e:
        current_app.logger.error(f"Erreur envoi email individuel: {str(e)}")
        flash(f'Erreur lors de l\'envoi: {str(e)}', 'danger')
    
    return redirect(url_for('admin.communications_dashboard'))

# À remplacer dans app/admin.py - fonction manage_content

@admin.route("/content")
@login_required
def manage_content():
    """Page de gestion du contenu du site."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Chemin du dossier de contenu
    content_dir = Path(current_app.root_path) / "static" / "content"
    
    # Lister les fichiers CSV disponibles
    csv_files = []
    if content_dir.exists():
        for file_path in content_dir.glob("*.csv"):
            csv_files.append({
                'name': file_path.name,
                'size': os.path.getsize(file_path),
                'modified': os.path.getmtime(file_path)
            })
    
    # Vérifier l'existence du fichier conference.yml
    conference_file = content_dir / "conference.yml"
    conference_exists = conference_file.exists()
    conference_info = None
    
    if conference_exists:
        conference_info = {
            'size': os.path.getsize(conference_file),
            'modified': os.path.getmtime(conference_file)
        }
    
    # Vérifier l'existence des images
    images_info = {}
    image_types = ['ville', 'site', 'bandeau']
    filename_map = {
        'ville': 'ville.png',
        'site': 'site.png', 
        'bandeau': 'bandeau.png'
    }
    
    for img_type in image_types:
        filename = filename_map[img_type]
        file_path = content_dir / filename
        
        if file_path.exists():
            images_info[img_type] = {
                'exists': True,
                'filename': filename,
                'size': os.path.getsize(file_path),
                'modified': os.path.getmtime(file_path),
                'url': f"/static/content/{filename}"
            }
        else:
            images_info[img_type] = {
                'exists': False,
                'filename': filename,
                'url': None
            }
    
    return render_template('admin/manage_content.html',
                         csv_files=csv_files,
                         conference_exists=conference_exists,
                         conference_info=conference_info,
                         images_info=images_info)

@admin.route("/content/upload-csv", methods=["POST"])
@login_required
def upload_csv():
    """Upload/remplacement d'un fichier CSV."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nom de fichier vide'}), 400
    
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'success': False, 'message': 'Seuls les fichiers CSV sont autorisés'}), 400
    
    try:
        # Sécuriser le nom de fichier
        filename = secure_filename(file.filename)
        
        # Chemin de destination
        content_dir = Path(current_app.root_path) / "static" / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        file_path = content_dir / filename
        
        # Sauvegarder l'ancien fichier s'il existe
        if file_path.exists():
            backup_path = content_dir / f"{filename}.backup"
            os.rename(file_path, backup_path)
        
        # Sauvegarder le nouveau fichier
        file.save(file_path)
        
        # Valider le format CSV
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            csv.reader(csvfile, delimiter=';')  # Test de lecture
        
        current_app.logger.info(f"Fichier CSV uploadé par {current_user.email}: {filename}")
        
        return jsonify({
            'success': True, 
            'message': f'Fichier {filename} uploadé avec succès'
        })
        
    except Exception as e:
        current_app.logger.error(f"Erreur upload CSV: {e}")
        return jsonify({
            'success': False, 
            'message': f'Erreur lors de l\'upload: {str(e)}'
        }), 500


@admin.route("/content/download-csv/<filename>")
@login_required
def download_csv(filename):
    """Télécharger un fichier CSV."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Sécuriser le nom de fichier
    filename = secure_filename(filename)
    if not filename.endswith('.csv'):
        flash("Fichier non autorisé.", "danger")
        return redirect(url_for("admin.manage_content"))
    
    content_dir = Path(current_app.root_path) / "static" / "content"
    file_path = content_dir / filename
    
    if not file_path.exists():
        flash("Fichier non trouvé.", "danger")
        return redirect(url_for("admin.manage_content"))
    
    return send_file(file_path, as_attachment=True, download_name=filename)

@admin.route("/content/preview-csv/<filename>")
@login_required
def preview_csv(filename):
    """Prévisualiser le contenu d'un fichier CSV."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    # Sécuriser le nom de fichier
    filename = secure_filename(filename)
    if not filename.endswith('.csv'):
        return jsonify({'success': False, 'message': 'Fichier non autorisé'}), 400
    
    content_dir = Path(current_app.root_path) / "static" / "content"
    file_path = content_dir / filename
    
    if not file_path.exists():
        return jsonify({'success': False, 'message': 'Fichier non trouvé'}), 404
    
    try:
        # Lire le CSV et créer un aperçu HTML
        rows = []
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';')
            headers = reader.fieldnames
            
            # Limiter à 10 lignes pour l'aperçu
            for i, row in enumerate(reader):
                if i >= 10:
                    break
                rows.append(row)
        
        # Générer le HTML du tableau
        html = '<div class="table-responsive">'
        html += '<table class="table table-sm table-bordered">'
        
        # En-têtes
        html += '<thead class="table-dark"><tr>'
        for header in headers:
            html += f'<th style="white-space: nowrap;">{header}</th>'
        html += '</tr></thead>'
        
        # Lignes de données
        html += '<tbody>'
        for row in rows:
            html += '<tr>'
            for header in headers:
                value = row.get(header, '')[:50]  # Limiter à 50 caractères
                if len(row.get(header, '')) > 50:
                    value += '...'
                html += f'<td style="white-space: nowrap;">{value}</td>'
            html += '</tr>'
        html += '</tbody>'
        
        html += '</table>'
        
        # Information sur le nombre total de lignes
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            total_lines = sum(1 for line in csvfile) - 1  # -1 pour l'en-tête
        
        if total_lines > 10:
            html += f'<div class="text-muted mt-2">Aperçu des 10 premières lignes sur {total_lines} au total.</div>'
        
        html += '</div>'
        
        return jsonify({'success': True, 'html': html})
        
    except Exception as e:
        current_app.logger.error(f"Erreur prévisualisation CSV {filename}: {e}")
        return jsonify({'success': False, 'message': f'Erreur de lecture: {str(e)}'}), 500

@admin.route("/content/download-yaml")
@login_required
def download_yaml():
    """Télécharger le fichier conference.yml."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    content_dir = Path(current_app.root_path) / "static" / "content"
    file_path = content_dir / "conference.yml"
    
    if not file_path.exists():
        flash("Fichier conference.yml non trouvé.", "danger")
        return redirect(url_for("admin.manage_content"))
    
    return send_file(file_path, as_attachment=True, download_name="conference.yml")

@admin.route("/content/get-yaml")
@login_required
def get_yaml_content():
    """Récupérer le contenu du fichier YAML pour l'édition."""
    if not current_user.is_admin:
        return "Accès refusé", 403
    
    content_dir = Path(current_app.root_path) / "static" / "content"
    file_path = content_dir / "conference.yml"
    
    if not file_path.exists():
        return "Fichier non trouvé", 404
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        current_app.logger.error(f"Erreur lecture YAML: {e}")
        return "Erreur de lecture", 500


@admin.route("/content/save-yaml", methods=["POST"])
@login_required
def save_yaml():
    """Sauvegarder le contenu du fichier YAML après édition."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        if not content:
            return jsonify({'success': False, 'message': 'Contenu vide'}), 400
        
        # Valider la syntaxe YAML
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            return jsonify({
                'success': False, 
                'message': f'Erreur de syntaxe YAML: {str(e)}'
            }), 400
        
        content_dir = Path(current_app.root_path) / "static" / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        file_path = content_dir / "conference.yml"
        
        # Sauvegarder l'ancien fichier s'il existe
        if file_path.exists():
            backup_path = content_dir / f"conference.yml.backup.{int(datetime.now().timestamp())}"
            os.rename(file_path, backup_path)
        
        # Écrire le nouveau contenu
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        current_app.logger.info(f"Fichier conference.yml modifié par {current_user.email}")
        
        return jsonify({
            'success': True, 
            'message': 'Fichier sauvegardé avec succès'
        })
        
    except Exception as e:
        current_app.logger.error(f"Erreur sauvegarde YAML: {e}")
        return jsonify({
            'success': False, 
            'message': f'Erreur lors de la sauvegarde: {str(e)}'
        }), 500

@admin.route("/content/validate-yaml", methods=["POST"])
@login_required
def validate_yaml():
    """Valider la syntaxe d'un contenu YAML."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        if not content:
            return jsonify({'success': False, 'message': 'Contenu vide'}), 400
        
        # Tenter de parser le YAML
        parsed = yaml.safe_load(content)
        
        # Compter les éléments principaux
        sections = []
        if isinstance(parsed, dict):
            sections = list(parsed.keys())
        
        return jsonify({
            'success': True, 
            'message': f'Syntaxe YAML valide. {len(sections)} sections trouvées: {", ".join(sections[:5])}{"..." if len(sections) > 5 else ""}'
        })
        
    except yaml.YAMLError as e:
        return jsonify({
            'success': False, 
            'message': f'Erreur de syntaxe YAML: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Erreur de validation: {str(e)}'
        }), 500

@admin.route("/content/upload-yaml", methods=["POST"])
@login_required
def upload_yaml():
    """Upload/remplacement du fichier conference.yml."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nom de fichier vide'}), 400
    
    if not file.filename.lower().endswith(('.yml', '.yaml')):
        return jsonify({'success': False, 'message': 'Seuls les fichiers YAML sont autorisés'}), 400
    
    try:
        # Lire et valider le contenu
        content = file.read().decode('utf-8')
        
        # Valider la syntaxe YAML
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            return jsonify({
                'success': False, 
                'message': f'Fichier YAML invalide: {str(e)}'
            }), 400
        
        content_dir = Path(current_app.root_path) / "static" / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        file_path = content_dir / "conference.yml"
        
        # Sauvegarder l'ancien fichier s'il existe
        if file_path.exists():
            backup_path = content_dir / f"conference.yml.backup.{int(datetime.now().timestamp())}"
            os.rename(file_path, backup_path)
        
        # Sauvegarder le nouveau fichier
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        current_app.logger.info(f"Fichier conference.yml uploadé par {current_user.email}")
        
        return jsonify({
            'success': True, 
            'message': 'Fichier conference.yml uploadé avec succès'
        })
        
    except Exception as e:
        current_app.logger.error(f"Erreur upload YAML: {e}")
        return jsonify({
            'success': False, 
            'message': f'Erreur lors de l\'upload: {str(e)}'
        }), 500

@admin.route("/content/reload-config", methods=["POST"])
@login_required
def reload_config():
    """Recharge la configuration de l'application à chaud."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    try:
        from app.config_loader import ConfigLoader
        
        # Créer une nouvelle instance du loader
        config_loader = ConfigLoader()
        
        # Recharger toutes les configurations
        result = config_loader.reload_all_configs()
        
        if result['success']:
            # Mettre à jour la configuration de l'application
            current_app.conference_config = config_loader.load_conference_config()
            current_app.themes_config = config_loader.load_themes()
            current_app.email_config = config_loader.load_email_config()
            
            # Log de l'action
            current_app.logger.info(f"Configuration rechargée par {current_user.email}")
            current_app.logger.info(f"Détails: {result['details']}")
            
            return jsonify({
                'success': True,
                'message': result['message'],
                'details': result['details'],
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify(result), 500
            
    except Exception as e:
        current_app.logger.error(f"Erreur rechargement config: {e}")
        return jsonify({
            'success': False,
            'message': f'Erreur lors du rechargement: {str(e)}'
        }), 500

@admin.route("/content/config-status")
@login_required
def config_status():
    """Retourne le statut actuel de la configuration."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    try:
        from app.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        status = config_loader.get_config_status()
        
        return jsonify({
            'success': True,
            'status': status,
            'app_config': {
                'conference_loaded': hasattr(current_app, 'conference_config'),
                'themes_count': len(current_app.themes_config) if hasattr(current_app, 'themes_config') else 0,
                'email_loaded': hasattr(current_app, 'email_config')
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@admin.route("/content/upload-image", methods=["POST"])
@login_required
def upload_image():
    """Upload/remplacement d'une image (ville.png, site.png, bandeau.png)."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'}), 400
    
    file = request.files['file']
    image_type = request.form.get('image_type')
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nom de fichier vide'}), 400
    
    # Vérifier le type d'image
    allowed_types = ['ville', 'site', 'bandeau']
    if image_type not in allowed_types:
        return jsonify({'success': False, 'message': 'Type d\'image non valide'}), 400
    
    # Vérifier l'extension
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        return jsonify({'success': False, 'message': 'Seuls les fichiers PNG et JPG sont autorisés'}), 400
    
    try:
        # Définir le nom de fichier selon le type
        filename_map = {
            'ville': 'ville.png',
            'site': 'site.png', 
            'bandeau': 'bandeau.png'
        }
        filename = filename_map[image_type]
        
        # Chemin de destination
        content_dir = Path(current_app.root_path) / "static" / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        file_path = content_dir / filename
        
        # Pour le bandeau, on sauvegarde aussi dans images/
        images_dir = Path(current_app.root_path) / "static" / "images"
        if image_type == 'bandeau':
            images_dir.mkdir(parents=True, exist_ok=True)
            bandeau_path = images_dir / "bandeau_sft2026.png"
        
        # Sauvegarder l'ancien fichier s'il existe
        if file_path.exists():
            backup_path = content_dir / f"{filename}.backup.{int(datetime.now().timestamp())}"
            os.rename(file_path, backup_path)
        
        # Sauvegarder le nouveau fichier
        file.save(file_path)
        
        # Pour le bandeau, copier aussi dans images/
        if image_type == 'bandeau' and file_path.exists():
            import shutil
            shutil.copy2(file_path, bandeau_path)
        
        current_app.logger.info(f"Image {filename} uploadée par {current_user.email}")
        
        return jsonify({
            'success': True, 
            'message': f'Image {filename} uploadée avec succès'
        })
        
    except Exception as e:
        current_app.logger.error(f"Erreur upload image: {e}")
        return jsonify({
            'success': False, 
            'message': f'Erreur lors de l\'upload: {str(e)}'
        }), 500

@admin.route("/content/download-image/<image_type>")
@login_required
def download_image(image_type):
    """Télécharger une image."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Vérifier le type d'image
    allowed_types = ['ville', 'site', 'bandeau']
    if image_type not in allowed_types:
        flash("Type d'image non valide.", "danger")
        return redirect(url_for("admin.manage_content"))
    
    filename_map = {
        'ville': 'ville.png',
        'site': 'site.png', 
        'bandeau': 'bandeau.png'
    }
    filename = filename_map[image_type]
    
    content_dir = Path(current_app.root_path) / "static" / "content"
    file_path = content_dir / filename
    
    if not file_path.exists():
        flash("Image non trouvée.", "danger")
        return redirect(url_for("admin.manage_content"))
    
    return send_file(file_path, as_attachment=True, download_name=filename)

@admin.route("/content/get-images-info")
@login_required
def get_images_info():
    """Récupérer les informations sur les images existantes."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    try:
        content_dir = Path(current_app.root_path) / "static" / "content"
        images_info = {}
        
        for image_type in ['ville', 'site', 'bandeau']:
            image_path = content_dir / f"{image_type}.png"
            if image_path.exists():
                images_info[image_type] = {
                    'exists': True,
                    'size': os.path.getsize(image_path),
                    'modified': os.path.getmtime(image_path),
                    'url': f"/static/content/{image_type}.png"
                }
            else:
                images_info[image_type] = {
                    'exists': False,
                    'url': None
                }
        
        return jsonify({
            'success': True,
            'images': images_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


# À ajouter dans app/admin.py

@admin.route("/test-emails")
@login_required
def test_emails_form():
    """Page pour configurer et lancer les tests d'emails."""
    if not current_user.is_admin:
        abort(403)
    
    return render_template('admin/test_emails.html')


@admin.route("/test-emails/run", methods=["POST"])
@login_required
def run_email_tests():
    """Exécute les tests d'emails selon la configuration."""
    if not current_user.is_admin:
        abort(403)
    
    try:
        test_email = request.form.get('test_email')
        selected_tests = request.form.getlist('email_tests')
        dry_run = request.form.get('dry_run') == 'on'
        
        if not test_email:
            return jsonify({
                'success': False,
                'message': 'Adresse email de test requise'
            }), 400
        
        if not selected_tests:
            return jsonify({
                'success': False,
                'message': 'Sélectionnez au moins un test'
            }), 400
        
        # Résultats des tests
        results = []
        
        # Créer des objets de test
        test_objects = create_test_objects_for_admin(test_email)
        
        # Exécuter les tests sélectionnés
        if 'activation' in selected_tests:
            result = run_activation_test(test_objects['user'], dry_run)
            results.append(result)
        
        if 'coauthor_new' in selected_tests:
            result = run_coauthor_new_test(test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
            
        if 'coauthor_existing' in selected_tests:
            result = run_coauthor_existing_test(test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
        
        if 'review_reminder' in selected_tests:
            result = run_review_reminder_test(test_objects['reviewer'], test_objects['assignment'], dry_run)
            results.append(result)
        
        if 'qr_code' in selected_tests:
            result = run_qr_code_test(test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
        
        if 'decision_accept' in selected_tests:
            result = run_decision_test(test_objects['communication'], 'accepter', dry_run)
            results.append(result)
            
        if 'decision_reject' in selected_tests:
            result = run_decision_test(test_objects['communication'], 'rejeter', dry_run)
            results.append(result)
            
        if 'decision_revise' in selected_tests:
            result = run_decision_test(test_objects['communication'], 'reviser', dry_run)
            results.append(result)
        
        if 'biot_fourier' in selected_tests:
            result = run_biot_fourier_test(test_objects['communication'], dry_run)
            results.append(result)

        if 'hal_collection' in selected_tests:
            result = run_hal_collection_test(test_email, dry_run) 
            results.append(result)

        if 'resume_confirmation' in selected_tests:
            result = run_submission_confirmation_test('résumé', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
        
        if 'article_confirmation' in selected_tests:
            result = run_submission_confirmation_test('article', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
        
        if 'wip_confirmation' in selected_tests:
            result = run_submission_confirmation_test('wip', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
        
        if 'poster_confirmation' in selected_tests:
            result = run_submission_confirmation_test('poster', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
        
        if 'revision_confirmation' in selected_tests:
            result = run_submission_confirmation_test('revision', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
        
        if 'reviewer_welcome' in selected_tests:
            result = run_reviewer_welcome_test(test_objects['reviewer'], dry_run)
            results.append(result)
        
        if 'admin_weekly_summary' in selected_tests:
            result = run_admin_weekly_summary_test(test_email, dry_run)
            results.append(result)
        
        if 'admin_alert' in selected_tests:
            result = run_admin_alert_test(test_email, dry_run)
            results.append(result)
            
        # Test de configuration
        config_result = test_email_configuration()
        results.append(config_result)
        
        # Compter les succès/échecs
        success_count = len([r for r in results if r['success']])
        total_count = len(results)
        
        return jsonify({
            'success': True,
            'message': f'{success_count}/{total_count} tests réussis',
            'results': results,
            'dry_run': dry_run
        })
        
    except Exception as e:
        current_app.logger.error(f"Erreur test emails: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


def create_test_objects_for_admin(test_email):
    """Crée des objets factices pour les tests admin."""
    from datetime import datetime
    
    # Utilisateur test
    test_user = type('MockUser', (), {
        'email': test_email,
        'first_name': 'Jean',
        'last_name': 'Dupont',
        'full_name': 'Jean Dupont',
        'specialites_codes': 'COND,MULTI',
        'is_reviewer': True,
        'affiliations': []
    })()
    
    # Communication test
    test_communication = type('MockCommunication', (), {
        'id': 999,
        'title': 'Test de communication pour validation du système d\'emails',
        'type': 'article',
        'status': type('MockStatus', (), {'value': 'submitted'})(),
        'authors': [test_user],
        'thematiques_codes': 'COND,SIMUL'
    })()
    
    # Assignment de review test
    test_assignment = type('MockAssignment', (), {
        'communication': test_communication,
        'reviewer': test_user,
        'due_date': datetime(2025, 9, 15),
        'is_overdue': False
    })()
    
    return {
        'user': test_user,
        'communication': test_communication,
        'reviewer': test_user,
        'assignment': test_assignment
    }


def run_activation_test(user, dry_run):
    """Test email d'activation."""
    try:
        if not dry_run:
            from app.emails import send_activation_email_to_user
            send_activation_email_to_user(user, "test_token_12345")
        
        return {
            'test': 'Email d\'activation',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Email d\'activation',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }


def run_coauthor_new_test(user, communication, dry_run):
    """Test email co-auteur nouveau."""
    try:
        if not dry_run:
            from app.emails import send_coauthor_notification_email
            send_coauthor_notification_email(user, communication, "coauthor_token_67890")
        
        return {
            'test': 'Email co-auteur (nouveau)',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Email co-auteur (nouveau)',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }


def run_coauthor_existing_test(user, communication, dry_run):
    """Test email co-auteur existant."""
    try:
        if not dry_run:
            from app.emails import send_existing_coauthor_notification_email
            send_existing_coauthor_notification_email(user, communication)
        
        return {
            'test': 'Email co-auteur (existant)',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Email co-auteur (existant)',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }


def run_review_reminder_test(reviewer, assignment, dry_run):
    """Test email rappel review."""
    try:
        if not dry_run:
            from app.emails import send_review_reminder_email
            send_review_reminder_email(reviewer, [assignment])
        
        return {
            'test': 'Email rappel review',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Email rappel review',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }


def run_qr_code_test(user, communication, dry_run):
    """Test email QR code."""
    try:
        if not dry_run:
            from app.emails import send_qr_code_reminder_email
            send_qr_code_reminder_email(user, [communication])
        
        return {
            'test': 'Email QR code',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Email QR code',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }


def run_decision_test(communication, decision, dry_run):
    """Test email de décision."""
    try:
        if not dry_run:
            from app.emails import send_decision_notification_email
            send_decision_notification_email(communication, decision, f"Commentaires de test pour {decision}")
        
        return {
            'test': f'Email décision ({decision})',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': f'Email décision ({decision})',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }


def run_biot_fourier_test(communication, dry_run):
    """Test email Biot-Fourier."""
    try:
        if not dry_run:
            from app.emails import send_biot_fourier_audition_notification
            send_biot_fourier_audition_notification(communication)
        
        return {
            'test': 'Email Biot-Fourier',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Email Biot-Fourier',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }


def test_email_configuration():
    """Test de la configuration emails."""
    try:
        config_loader = current_app.config_loader
        
        # Test chargement configuration
        email_config = config_loader.load_email_config()
        variables = config_loader.get_email_template_variables()
        
        # Vérifications
        checks = []
        
        # Vérifier les sujets
        subjects = email_config.get('templates', {}).get('subjects', {})
        checks.append(f"{len(subjects)} sujets d'emails configurés")
        
        # Vérifier les variables
        conference_name = variables.get('CONFERENCE_SHORT_NAME', 'NON TROUVÉ')
        checks.append(f"CONFERENCE_SHORT_NAME: {conference_name}")
        
        # Test d'un template
        test_subject = config_loader.get_email_subject('welcome', USER_FIRST_NAME="Test")
        checks.append(f"Template de test: {test_subject[:50]}...")
        
        return {
            'test': 'Configuration emails',
            'success': True,
            'message': ' | '.join(checks)
        }
        
    except Exception as e:
        return {
            'test': 'Configuration emails',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }
    
def run_hal_collection_test(test_email, dry_run):
    """Test de l'email de demande de collection HAL."""
    try:
        if dry_run:
            return {
                'test': 'Demande collection HAL',
                'success': True,
                'message': f'Email de demande collection HAL prêt à envoyer à {test_email}'
            }
        
        # Charger la configuration
        from app.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        config = config_loader.load_conference_config()
        
        # Créer les données d'email (même logique que dans hal_routes.py)
        import os
        admin_first_name = os.getenv('ADMIN_FIRST_NAME', 'Admin')
        admin_last_name = os.getenv('ADMIN_LAST_NAME', 'Test')
        admin_email = os.getenv('ADMIN_EMAIL', test_email)
        
        organizing_lab = config.get('conference', {}).get('organizing_lab', {})
        lab_short_name = organizing_lab.get('short_name', 'LEMTA')
        
        email_data = {
            'contact_name': f"{admin_first_name} {admin_last_name}",
            'contact_title': f"Responsable du congrès, {lab_short_name}",
            'contact_email': admin_email,
            'hal_login': os.getenv('HAL_LOGIN', 'test-login'),
            'conference_name': config.get('conference', {}).get('full_name', 'SFT 2026'),
            'conference_dates': '2-5 juin 2026',
            'conference_location': config.get('conference', {}).get('location', {}).get('city', 'Nancy'),
            'organizing_lab_name': organizing_lab.get('name', 'LEMTA'),
            'collection_id': 'SFT2026',
            'estimated_docs': 200,
            'submission_deadline': 'Mars 2026',
            'deposit_start': 'Avril 2026'
        }
        
        # Envoyer l'email de test
        from app.emails import send_hal_collection_request
        send_hal_collection_request(
            recipient_email=test_email,
            email_data=email_data,
            custom_message="[TEST] Email de test automatique depuis l'interface admin"
        )
        
        return {
            'test': 'Demande collection HAL',
            'success': True,
            'message': f'Email de demande collection HAL envoyé à {test_email}'
        }
        
    except Exception as e:
        return {
            'test': 'Demande collection HAL',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }


@admin.route("/send-test-email")
@login_required
def send_test_email():
    """Page de test des emails."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    # Rediriger vers la page de test des emails
    return redirect(url_for('admin.test_emails'))


@admin.route("/affiliations/enrich-hal", methods=["GET", "POST"])
@login_required
def enrich_affiliations_hal():
    """Enrichit les affiliations avec les données HAL via l'API."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for("main.index"))
    
    if request.method == "POST":
        # Lancer l'enrichissement
        try:
            results = hal_enrich_affiliations()
            
            if results['enriched'] > 0:
                flash(f"✅ {results['enriched']} laboratoires enrichis avec les données HAL", "success")
            if results['duplicates_avoided'] > 0:
                flash(f"🔍 {results['duplicates_avoided']} doublons d'ID HAL évités", "info")
            if results['errors']:
                flash(f"⚠️ {len(results['errors'])} erreurs lors de l'enrichissement", "warning")
                for error in results['errors'][:3]:  # Afficher les 3 premières erreurs
                    flash(f"• {error}", "warning")
            if results['not_found'] > 0:
                flash(f"ℹ️ {results['not_found']} laboratoires non trouvés dans HAL", "info")
                
        except Exception as e:
            flash(f"❌ Erreur lors de l'enrichissement : {str(e)}", "danger")
        
        return redirect(url_for('admin.enrich_affiliations_hal'))
    
    # GET : Afficher la page avec preview
    affiliations_to_enrich = get_affiliations_needing_enrichment()
    
    return render_template('admin/enrich_affiliations_hal.html', 
                         affiliations=affiliations_to_enrich,
                         total=len(affiliations_to_enrich))



def get_affiliations_needing_enrichment():
    """Retourne les affiliations qui pourraient être enrichies."""
    return Affiliation.query.filter(
        db.or_(
            Affiliation.struct_id_hal.is_(None),
            Affiliation.struct_id_hal == '',
            Affiliation.acronym_hal.is_(None),
            Affiliation.acronym_hal == ''
        )
    ).all()


def hal_enrich_affiliations():
    """Enrichit les affiliations en appelant l'API HAL."""
    import requests
    import time
    from urllib.parse import quote
    
    results = {
        'enriched': 0,
        'not_found': 0,
        'errors': []
    }
    
    # API HAL pour recherche de structures
    HAL_API_BASE = "https://api.archives-ouvertes.fr/search/"
    
    affiliations_to_enrich = get_affiliations_needing_enrichment()
    
    for affiliation in affiliations_to_enrich:
        try:
            # Recherche par nom complet d'abord
            search_terms = [
                affiliation.nom_complet,
                affiliation.sigle
            ]
            
            hal_data = None
            
            for term in search_terms:
                if not term:
                    continue
                    
                # Recherche dans HAL
                hal_data = search_hal_structure(term)
                if hal_data:
                    break
                
                # Pause pour éviter de surcharger l'API
                time.sleep(0.5)
            
            if hal_data:
                # Enrichir l'affiliation avec les données HAL
                affiliation.struct_id_hal = hal_data.get('struct_id')
                affiliation.acronym_hal = hal_data.get('acronym')
                affiliation.type_hal = hal_data.get('type', 'laboratory')
                
                db.session.commit()
                results['enriched'] += 1
                
                current_app.logger.info(f"Enrichi {affiliation.sigle} avec HAL ID {hal_data.get('struct_id')}")
            else:
                results['not_found'] += 1
                
        except Exception as e:
            error_msg = f"Erreur pour {affiliation.sigle}: {str(e)}"
            results['errors'].append(error_msg)
            current_app.logger.error(error_msg)
    
    return results

def search_hal_structure(search_term):
    """Recherche une structure dans HAL via l'API avec une meilleure précision."""
    import requests
    from urllib.parse import quote
    
    try:
        # URL de recherche HAL
        encoded_term = quote(search_term)
        url = f"https://api.archives-ouvertes.fr/search/?q=structName_s:({encoded_term})&fl=structId_i,structAcronym_s,structName_s,structType_s&rows=10"
        
        headers = {
            'User-Agent': 'Conference-Flow/1.0 (contact@example.com)'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('response', {}).get('numFound', 0) > 0:
            docs = data['response']['docs']
            
            # Fonction pour calculer un score de correspondance
            def calculate_match_score(doc, search_term):
                struct_name = doc.get('structName_s', [''])[0].lower()
                struct_acronym = doc.get('structAcronym_s', [''])[0].lower()
                search_lower = search_term.lower()
                
                score = 0
                
                # Score pour correspondance exacte du sigle/acronyme (priorité maximale)
                if struct_acronym and struct_acronym == search_lower:
                    score += 100
                elif struct_acronym and search_lower == struct_acronym:
                    score += 90
                
                # Score pour correspondance exacte dans le nom complet
                if search_lower in struct_name:
                    # Correspondance exacte du terme complet
                    if search_lower == struct_name:
                        score += 80
                    # Le terme apparaît comme mot complet
                    elif f" {search_lower} " in f" {struct_name} ":
                        score += 60
                    # Le terme apparaît au début ou à la fin
                    elif struct_name.startswith(search_lower) or struct_name.endswith(search_lower):
                        score += 50
                    # Le terme apparaît quelque part
                    else:
                        score += 30
                
                # Pénalité si le nom est très différent (évite les faux positifs)
                search_words = set(search_lower.split())
                name_words = set(struct_name.split())
                common_words = search_words.intersection(name_words)
                
                if len(search_words) > 0:
                    word_match_ratio = len(common_words) / len(search_words)
                    if word_match_ratio < 0.3:  # Moins de 30% de mots en commun
                        score -= 20
                
                return score
            
            # Calculer les scores pour tous les résultats
            scored_results = []
            for doc in docs:
                score = calculate_match_score(doc, search_term)
                if score > 20:  # Seuil minimum de pertinence
                    scored_results.append((score, doc))
            
            # Trier par score décroissant
            scored_results.sort(key=lambda x: x[0], reverse=True)
            
            if scored_results:
                best_score, best_doc = scored_results[0]
                
                # Log pour debugging
                struct_name = best_doc.get('structName_s', [''])[0]
                struct_acronym = best_doc.get('structAcronym_s', [''])[0]
                current_app.logger.info(f"HAL match pour '{search_term}': '{struct_name}' ({struct_acronym}) - Score: {best_score}")
                
                # Vérification finale : éviter les correspondances trop faibles
                if best_score < 40:
                    current_app.logger.warning(f"Score trop faible pour '{search_term}': {best_score} - Résultat rejeté")
                    return None
                
                return {
                    'struct_id': best_doc.get('structId_i', [None])[0],
                    'acronym': struct_acronym,
                    'name': struct_name,
                    'type': best_doc.get('structType_s', ['laboratory'])[0],
                    'match_score': best_score
                }
        
        return None
        
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Erreur API HAL pour '{search_term}': {e}")
        return None
    except Exception as e:
        current_app.logger.error(f"Erreur parsing HAL pour '{search_term}': {e}")
        return None


def hal_enrich_affiliations():
    """Version améliorée avec vérification des doublons d'ID HAL."""
    import requests
    import time
    from urllib.parse import quote
    
    results = {
        'enriched': 0,
        'not_found': 0,
        'errors': [],
        'duplicates_avoided': 0
    }
    
    affiliations_to_enrich = get_affiliations_needing_enrichment()
    used_hal_ids = set()  # Pour éviter les doublons
    
    # D'abord, récupérer tous les struct_id_hal déjà utilisés
    existing_hal_ids = db.session.query(Affiliation.struct_id_hal).filter(
        Affiliation.struct_id_hal.isnot(None),
        Affiliation.struct_id_hal != ''
    ).all()
    used_hal_ids.update([hal_id[0] for hal_id in existing_hal_ids])
    
    for affiliation in affiliations_to_enrich:
        try:
            # Recherche par nom complet d'abord, puis par sigle
            search_terms = []
            
            # Prioriser le sigle s'il est assez spécifique
            if affiliation.sigle and len(affiliation.sigle) >= 3:
                search_terms.append(affiliation.sigle)
            
            # Ajouter le nom complet
            if affiliation.nom_complet:
                search_terms.append(affiliation.nom_complet)
            
            hal_data = None
            best_match = None
            
            for term in search_terms:
                if not term:
                    continue
                    
                # Recherche dans HAL
                hal_result = search_hal_structure(term)
                if hal_result:
                    # Vérifier que cet ID HAL n'est pas déjà utilisé
                    struct_id = str(hal_result.get('struct_id'))
                    if struct_id in used_hal_ids:
                        current_app.logger.warning(f"ID HAL {struct_id} déjà utilisé, ignoré pour {affiliation.sigle}")
                        results['duplicates_avoided'] += 1
                        continue
                    
                    # Garder le meilleur match (score le plus élevé)
                    if not best_match or hal_result.get('match_score', 0) > best_match.get('match_score', 0):
                        best_match = hal_result
                
                # Pause pour éviter de surcharger l'API
                time.sleep(0.7)
            
            if best_match:
                # Enrichir l'affiliation avec les meilleures données HAL
                affiliation.struct_id_hal = str(best_match.get('struct_id'))
                affiliation.acronym_hal = best_match.get('acronym')
                affiliation.type_hal = best_match.get('type', 'laboratory')
                
                # Ajouter l'ID à la liste des utilisés
                used_hal_ids.add(str(best_match.get('struct_id')))
                
                db.session.commit()
                results['enriched'] += 1
                
                current_app.logger.info(f"Enrichi {affiliation.sigle} avec HAL ID {best_match.get('struct_id')} (score: {best_match.get('match_score')})")
            else:
                results['not_found'] += 1
                current_app.logger.info(f"Aucun résultat HAL satisfaisant pour {affiliation.sigle}")
                
        except Exception as e:
            error_msg = f"Erreur pour {affiliation.sigle}: {str(e)}"
            results['errors'].append(error_msg)
            current_app.logger.error(error_msg)
    
    return results

def run_submission_confirmation_test(file_type, user, communication, dry_run):
    """Test email de confirmation de soumission."""
    try:
        # Créer un faux SubmissionFile
        fake_submission_file = type('MockSubmissionFile', (), {
            'filename': f'test_{file_type}.pdf',
            'version': 1
        })()
        
        if not dry_run:
            from app.emails import send_submission_confirmation_email
            send_submission_confirmation_email(communication, file_type, fake_submission_file)
        
        return {
            'test': f'Email confirmation {file_type}',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': f'Email confirmation {file_type}',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }

def run_reviewer_welcome_test(user, dry_run):
    """Test email de bienvenue reviewer."""
    try:
        if not dry_run:
            from app.emails import send_activation_email_to_user
            # Utilise la fonction d'activation qui peut servir de bienvenue
            send_activation_email_to_user(user, "welcome_token_test")
        
        return {
            'test': 'Email bienvenue reviewer',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Email bienvenue reviewer',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }

def run_admin_weekly_summary_test(test_email, dry_run):
    """Test email résumé hebdomadaire admin."""
    try:
        if not dry_run:
            # Créer un faux contexte de résumé
            fake_context = {
                'ADMIN_NAME': 'Admin Test',
                'NEW_SUBMISSIONS': 5,
                'TOTAL_SUBMISSIONS': 42,
                'PENDING_ABSTRACTS': 12,
                'PENDING_ARTICLES': 8,
                'NEW_USERS': 3,
                'TOTAL_USERS': 156,
                'ACTIVE_REVIEWERS': 23,
                'ASSIGNED_REVIEWS': 15,
                'COMPLETED_REVIEWS': 12,
                'OVERDUE_REVIEWS': 2,
                'COMPLETION_RATE': 80,
                'ATTENTION_POINTS': 'Quelques reviews en retard à suivre',
                'RECOMMENDED_ACTIONS': 'Relancer les reviewers en retard'
            }
            
            from app.emails import _build_text_email, _build_html_email, send_email
            from flask import current_app
            
            config_loader = current_app.config_loader
            subject = config_loader.get_email_subject('admin_weekly_summary', **fake_context)
            content_config = config_loader.get_email_content('admin_weekly_summary', **fake_context)
            signature = config_loader.get_email_signature('system', **fake_context)
            
            body = _build_text_email(content_config, fake_context, signature)
            html = _build_html_email(content_config, fake_context, signature, '#6c757d')
            
            send_email(subject, [test_email], body, html)
        
        return {
            'test': 'Email résumé hebdomadaire',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Email résumé hebdomadaire',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }

def run_admin_alert_test(test_email, dry_run):
    """Test email alerte admin."""
    try:
        if not dry_run:
            fake_context = {
                'ADMIN_NAME': 'Admin Test',
                'ALERT_TYPE': 'Review refusée',
                'ALERT_TIMESTAMP': '24/08/2025 à 14:30',
                'ALERT_PRIORITY': 'Élevée',
                'ALERT_DESCRIPTION': 'Un reviewer a refusé une assignation',
                'SUGGESTED_ACTIONS': 'Réassigner à un autre reviewer'
            }
            
            from app.emails import _build_text_email, _build_html_email, send_email
            from flask import current_app
            
            config_loader = current_app.config_loader
            subject = config_loader.get_email_subject('admin_alert', **fake_context)
            content_config = config_loader.get_email_content('admin_alert', **fake_context)
            signature = config_loader.get_email_signature('system', **fake_context)
            
            body = _build_text_email(content_config, fake_context, signature)
            html = _build_html_email(content_config, fake_context, signature, '#dc3545', 'Alerte système')
            
            send_email(subject, [test_email], body, html)
        
        return {
            'test': 'Email alerte admin',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Email alerte admin',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }


# Corrections à apporter dans app/admin.py

def create_test_objects_for_admin(test_email):
    """Crée des objets factices pour les tests admin."""
    from datetime import datetime
    
    # Utilisateur test
    test_user = type('MockUser', (), {
        'email': test_email,
        'first_name': 'Jean',
        'last_name': 'Dupont',
        'full_name': 'Jean Dupont',
        'specialites_codes': 'COND,MULTI',
        'is_reviewer': True,
        'affiliations': []
    })()
    
    # Communication test - CORRIGÉE avec user au lieu de email
    test_communication = type('MockCommunication', (), {
        'id': 999,
        'title': 'Test de communication pour validation du système d\'emails',
        'type': 'article',
        'status': type('MockStatus', (), {'value': 'submitted'})(),
        'authors': [test_user],
        'thematiques': 'COND,SIMUL',  # Ajouté
        'thematiques_codes': 'COND,SIMUL',
        'user': test_user,  # IMPORTANT: ajout de l'attribut user
        'last_modified': datetime.now()  # Ajouté pour les emails de confirmation
    })()
    
    # Assignment de review test
    test_assignment = type('MockAssignment', (), {
        'communication': test_communication,
        'reviewer': test_user,
        'due_date': datetime(2025, 9, 15),
        'is_overdue': False
    })()
    
    return {
        'user': test_user,
        'communication': test_communication,
        'reviewer': test_user,
        'assignment': test_assignment
    }

# Ajouter les fonctions de test manquantes pour les confirmations

def run_submission_confirmation_test(submission_type, user, communication, dry_run):
    """Test email de confirmation de soumission."""
    try:
        if not dry_run:
            from app.emails import send_submission_confirmation_email
            send_submission_confirmation_email(user, communication, submission_type)
        
        return {
            'test': f'Email confirmation {submission_type}',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': f'Email confirmation {submission_type}',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }

# Dans la fonction run_email_tests(), ajouter les nouveaux tests :

@admin.route("/test-emails/run", methods=["POST"])
@login_required  
def run_email_tests():
    """Exécute les tests d'emails selon la configuration."""
    if not current_user.is_admin:
        abort(403)
    
    try:
        test_email = request.form.get('test_email')
        selected_tests = request.form.getlist('email_tests')
        dry_run = request.form.get('dry_run') == 'on'
        
        if not test_email:
            return jsonify({
                'success': False,
                'message': 'Adresse email de test requise'
            }), 400
        
        if not selected_tests:
            return jsonify({
                'success': False,
                'message': 'Sélectionnez au moins un test'
            }), 400
        
        # Résultats des tests
        results = []
        
        # Créer des objets de test
        test_objects = create_test_objects_for_admin(test_email)
        
        # Tests existants...
        if 'activation' in selected_tests:
            result = run_activation_test(test_objects['user'], dry_run)
            results.append(result)
        
        # NOUVEAUX TESTS DE CONFIRMATION
        if 'submission_resume' in selected_tests:
            result = run_submission_confirmation_test('résumé', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
            
        if 'submission_article' in selected_tests:
            result = run_submission_confirmation_test('article', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
            
        if 'submission_wip' in selected_tests:
            result = run_submission_confirmation_test('wip', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
            
        if 'submission_poster' in selected_tests:
            result = run_submission_confirmation_test('poster', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
            
        if 'submission_revision' in selected_tests:
            result = run_submission_confirmation_test('revision', test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
        
        if 'reviewer_welcome' in selected_tests:
            result = run_reviewer_welcome_test(test_objects['user'], dry_run)
            results.append(result)
            
        if 'admin_summary' in selected_tests:
            result = run_admin_summary_test(test_email, dry_run)
            results.append(result)
            
        if 'admin_alert' in selected_tests:
            result = run_admin_alert_test(test_email, dry_run)
            results.append(result)
        
        # Tests existants continuent...
        if 'coauthor_new' in selected_tests:
            result = run_coauthor_new_test(test_objects['user'], test_objects['communication'], dry_run)
            results.append(result)
            
        # ... reste du code existant
        
        # Test de configuration
        config_result = test_email_configuration()
        results.append(config_result)
        
        # Compter les succès/échecs
        success_count = len([r for r in results if r['success']])
        total_count = len(results)
        
        return jsonify({
            'success': True,
            'message': f'{success_count}/{total_count} tests réussis',
            'results': results,
            'dry_run': dry_run
        })
        
    except Exception as e:
        current_app.logger.error(f"Erreur test emails: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

# Ajouter les nouvelles fonctions de test manquantes

def run_reviewer_welcome_test(user, dry_run):
    """Test email bienvenue reviewer."""
    try:
        if not dry_run:
            from app.emails import send_reviewer_welcome_email
            send_reviewer_welcome_email(user)
        
        return {
            'test': 'Bienvenue reviewer',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Bienvenue reviewer',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }

def run_admin_summary_test(test_email, dry_run):
    """Test résumé hebdomadaire admin."""
    try:
        if not dry_run:
            from app.emails import send_admin_weekly_summary
            stats = {
                'submissions': 42,
                'reviews': 28,
                'pending_reviews': 14,
                'overdue_reviews': 3
            }
            send_admin_weekly_summary(test_email, stats)
        
        return {
            'test': 'Résumé hebdomadaire admin',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Résumé hebdomadaire admin',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }

def run_admin_alert_test(test_email, dry_run):
    """Test alerte admin."""
    try:
        if not dry_run:
            from app.emails import send_admin_alert_email
            send_admin_alert_email(test_email, 'URGENT', 'Test d\'alerte système depuis l\'interface admin')
        
        return {
            'test': 'Alerte admin',
            'success': True,
            'message': 'Envoyé avec succès' if not dry_run else 'Test simulé'
        }
    except Exception as e:
        return {
            'test': 'Alerte admin',
            'success': False,
            'message': f'Erreur: {str(e)}'
        }
