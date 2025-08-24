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

# Nouveau fichier : app/registration_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask_mail import Message
from werkzeug.utils import secure_filename
import json
import os
from datetime import datetime

from .models import db, Registration
from . import mail

registration = Blueprint("registration", __name__)

PARTICIPANT_TYPES = [
    ('auteur', 'Auteur de communication'),
    ('auditeur', 'Auditeur'),
    ('etudiant', 'Étudiant/Doctorant'),
    ('accompagnant', 'Accompagnant'),
    ('industriel', 'Industriel/Partenaire'),
]

ACCOMMODATION_TYPES = [
    ('hotel_3', 'Hôtel 3 étoiles'),
    ('hotel_4', 'Hôtel 4 étoiles'),
    ('residence', 'Résidence universitaire'),
    ('autre', 'Autre (à préciser)'),
]

@registration.route("/inscription", methods=["GET", "POST"])
def register_conference():
    """Formulaire d'inscription à la conférence."""
    
    if request.method == "POST":
        try:
            # Création de l'inscription
            reg = Registration()
            
            # Informations personnelles
            reg.title = request.form.get('title', '').strip()
            reg.first_name = request.form.get('first_name', '').strip()
            reg.last_name = request.form.get('last_name', '').strip()
            reg.email = request.form.get('email', '').strip().lower()
            reg.phone = request.form.get('phone', '').strip()
            
            # Validation des champs obligatoires
            if not all([reg.first_name, reg.last_name, reg.email]):
                flash("Les champs nom, prénom et email sont obligatoires.", "danger")
                return render_template("registration/form.html", 
                                     participant_types=PARTICIPANT_TYPES,
                                     accommodation_types=ACCOMMODATION_TYPES)
            
            # Vérifier si email déjà utilisé
            existing = Registration.query.filter_by(email=reg.email).first()
            if existing:
                flash("Cette adresse email est déjà utilisée pour une inscription.", "danger")
                return render_template("registration/form.html", 
                                     participant_types=PARTICIPANT_TYPES,
                                     accommodation_types=ACCOMMODATION_TYPES)
            
            # Affiliation
            reg.institution = request.form.get('institution', '').strip()
            reg.department = request.form.get('department', '').strip()
            reg.position = request.form.get('position', '').strip()
            
            if not reg.institution:
                flash("L'institution est obligatoire.", "danger")
                return render_template("registration/form.html", 
                                     participant_types=PARTICIPANT_TYPES,
                                     accommodation_types=ACCOMMODATION_TYPES)
            
            # Adresse
            reg.address = request.form.get('address', '').strip()
            reg.city = request.form.get('city', '').strip()
            reg.postal_code = request.form.get('postal_code', '').strip()
            reg.country = request.form.get('country', '').strip()
            
            # Type de participation
            reg.participant_type = request.form.get('participant_type', '')
            if reg.participant_type not in [t[0] for t in PARTICIPANT_TYPES]:
                flash("Type de participant invalide.", "danger")
                return render_template("registration/form.html", 
                                     participant_types=PARTICIPANT_TYPES,
                                     accommodation_types=ACCOMMODATION_TYPES)
            
            # Gestion du justificatif étudiant
            if reg.participant_type == 'etudiant':
                file = request.files.get('student_proof')
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    file_path = os.path.join('static/uploads/student_proofs', 
                                           f"{reg.email}_{filename}")
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    file.save(file_path)
                    reg.student_proof = file_path
            
            # Choix de participation
            reg.attendance_days = {
                'jour1': bool(request.form.get('day1')),
                'jour2': bool(request.form.get('day2')),
                'jour3': bool(request.form.get('day3')),
            }
            
            reg.poster_session = bool(request.form.get('poster_session'))
            reg.gala_dinner = bool(request.form.get('gala_dinner'))
            
            reg.lunch_options = {
                'jour1': bool(request.form.get('lunch_day1')),
                'jour2': bool(request.form.get('lunch_day2')),
                'jour3': bool(request.form.get('lunch_day3')),
            }
            
            # Hébergement
            reg.accommodation_needed = bool(request.form.get('accommodation_needed'))
            if reg.accommodation_needed:
                reg.accommodation_type = request.form.get('accommodation_type', '')
                reg.accommodation_dates = {
                    'debut': request.form.get('accommodation_start', ''),
                    'fin': request.form.get('accommodation_end', ''),
                }
            
            # Besoins spéciaux
            reg.dietary_requirements = request.form.get('dietary_requirements', '').strip()
            reg.accessibility_needs = request.form.get('accessibility_needs', '').strip()
            reg.special_requests = request.form.get('special_requests', '').strip()
            
            # Facturation
            reg.billing_name = request.form.get('billing_name', '').strip()
            reg.billing_address = request.form.get('billing_address', '').strip()
            reg.billing_vat = request.form.get('billing_vat', '').strip()
            reg.purchase_order = request.form.get('purchase_order', '').strip()
            
            # Lier à l'utilisateur connecté si applicable
            if current_user.is_authenticated:
                reg.user_id = current_user.id
            
            # Calculer le montant total
            reg.calculate_total()
            
            # Sauvegarder en base
            db.session.add(reg)
            db.session.commit()
            
            # Envoyer les emails de confirmation
            send_registration_emails(reg)
            
            flash("Inscription enregistrée avec succès ! Un email de confirmation vous a été envoyé.", "success")
            return redirect(url_for('registration.confirmation', reg_id=reg.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de l'inscription : {str(e)}", "danger")
    
    return render_template("registration/form.html", 
                         participant_types=PARTICIPANT_TYPES,
                         accommodation_types=ACCOMMODATION_TYPES)

@registration.route("/confirmation/<int:reg_id>")
def confirmation(reg_id):
    """Page de confirmation d'inscription."""
    reg = Registration.query.get_or_404(reg_id)
    return render_template("registration/confirmation.html", registration=reg)

@registration.route("/admin/inscriptions")
@login_required
def admin_registrations():
    """Administration des inscriptions (admin seulement)."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.index'))
    
    registrations = Registration.query.order_by(Registration.registration_date.desc()).all()
    
    # Statistiques
    stats = {
        'total': len(registrations),
        'by_type': {},
        'total_amount': sum(r.total_amount for r in registrations),
        'paid': len([r for r in registrations if r.payment_status == 'paid']),
    }
    
    for reg in registrations:
        if reg.participant_type not in stats['by_type']:
            stats['by_type'][reg.participant_type] = 0
        stats['by_type'][reg.participant_type] += 1
    
    return render_template("registration/admin.html", 
                         registrations=registrations, 
                         stats=stats)

@registration.route("/admin/export-inscriptions")
@login_required 
def export_registrations():
    """Export JSON des inscriptions."""
    if not current_user.is_admin:
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.index'))
    
    registrations = Registration.query.all()
    data = {
        'export_date': datetime.utcnow().isoformat(),
        'total_registrations': len(registrations),
        'registrations': [reg.to_json() for reg in registrations]
    }
    
    return jsonify(data)

def send_registration_emails(registration):
    """Envoie les emails de confirmation d'inscription."""
    try:
        # Email au participant
        send_participant_email(registration)
        
        # Email aux organisateurs
        send_organizer_email(registration)
        
        # Marquer comme envoyé
        registration.confirmation_sent = True
        db.session.commit()
        
    except Exception as e:
        print(f"Erreur envoi email : {e}")

def send_participant_email(registration):
    """Email de confirmation au participant."""
    subject = "Confirmation d'inscription - Congrès SFT 2026"
    
    # Générer le JSON pour l'email
    json_data = json.dumps(registration.to_json(), indent=2, ensure_ascii=False)
    
    body = f"""
Bonjour {registration.first_name} {registration.last_name},

Votre inscription au Congrès SFT 2026 a été enregistrée avec succès.

Numéro d'inscription : {registration.id}
Type de participant : {dict(PARTICIPANT_TYPES).get(registration.participant_type, registration.participant_type)}
Montant total : {registration.total_amount}€

Récapitulatif de votre inscription :
{json_data}

Prochaines étapes :
1. Vous recevrez prochainement les informations de paiement
2. Un programme détaillé vous sera envoyé
3. Les informations pratiques seront communiquées avant l'événement

Pour toute question : contact@sft2026.fr

Cordialement,
L'équipe d'organisation SFT 2026
"""

    msg = Message(
        subject=subject,
        recipients=[registration.email],
        body=body
    )
    
    mail.send(msg)

def send_organizer_email(registration):
    """Email aux organisateurs avec les détails de l'inscription."""
    subject = f"Nouvelle inscription SFT 2026 - {registration.first_name} {registration.last_name}"
    
    # JSON complet pour les organisateurs
    json_data = json.dumps(registration.to_json(), indent=2, ensure_ascii=False)
    
    body = f"""
Nouvelle inscription reçue :

ID : {registration.id}
Nom : {registration.first_name} {registration.last_name}
Email : {registration.email}
Institution : {registration.institution}
Type : {dict(PARTICIPANT_TYPES).get(registration.participant_type, registration.participant_type)}
Montant : {registration.total_amount}€

Données complètes en JSON :
{json_data}
"""

    # Email aux organisateurs (à configurer dans les variables d'environnement)
    #organizer_emails = ["inscription2026@congres-sft.fr"]
    organizer_emails = ["farges.olivier@gmail.com"]
    
    msg = Message(
        subject=subject,
        recipients=organizer_emails,
        body=body
    )
    
    # Attacher le JSON comme fichier
    filename = f"inscription_{registration.id}_{registration.last_name}.json"
    msg.attach(filename, "application/json", json_data)
    
    mail.send(msg)

@registration.route("/api/details/<int:reg_id>")
@login_required
def api_registration_details(reg_id):
    """API pour récupérer les détails d'une inscription."""
    if not current_user.is_admin:
        return jsonify({'error': 'Accès refusé'}), 403
    
    reg = Registration.query.get_or_404(reg_id)
    return jsonify(reg.to_json())

@registration.route("/api/mark-paid/<int:reg_id>", methods=["POST"])
@login_required
def api_mark_paid(reg_id):
    """API pour marquer une inscription comme payée."""
    if not current_user.is_admin:
        return jsonify({'error': 'Accès refusé'}), 403
    
    reg = Registration.query.get_or_404(reg_id)
    reg.payment_status = 'paid'
    db.session.commit()
    
    return jsonify({'success': True})

@registration.route("/api/json/<int:reg_id>")
@login_required
def api_download_json(reg_id):
    """API pour télécharger le JSON d'une inscription."""
    if not current_user.is_admin:
        return jsonify({'error': 'Accès refusé'}), 403
    
    reg = Registration.query.get_or_404(reg_id)
    
    from flask import Response
    import json
    
    json_data = json.dumps(reg.to_json(), indent=2, ensure_ascii=False)
    
    return Response(
        json_data,
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename=inscription_{reg.id}_{reg.last_name}.json'
        }
    )
