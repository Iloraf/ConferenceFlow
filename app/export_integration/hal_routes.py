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

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import Communication, db, HALDeposit, CommunicationStatus
from .hal_client import HALClient, HALConfigError
from .hal_xml_generator import HALXMLGenerator, HALConfigError as HALXMLConfigError
from datetime import datetime
import json

hal_bp = Blueprint('hal', __name__)

def _get_hal_collection_info():
    """
    Récupère les informations de collection HAL depuis conference.yml
    LÈVE UNE EXCEPTION si la configuration est incorrecte
    """
    try:
        config = current_app.conference_config
        hal_config = config.get('integrations', {}).get('hal', {})
        
        if not hal_config:
            raise HALConfigError("Configuration HAL manquante dans conference.yml")
        
        collection_id = hal_config.get('collection_id')
        if not collection_id:
            raise HALConfigError("collection_id manquant dans la configuration HAL")
        
        conference_info = config.get('conference', {})
        conference_name = conference_info.get('full_name', 'Conférence inconnue')
        
        return {
            'collection_id': collection_id.strip(),
            'conference_name': conference_name,
            'enabled': hal_config.get('enabled', False),
            'test_mode': hal_config.get('test_mode', True)
        }
    except Exception as e:
        raise HALConfigError(f"Erreur configuration HAL: {e}")

@hal_bp.route('/admin/hal/dashboard')
@login_required
def dashboard():
    """Tableau de bord HAL"""
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))
    
    try:
        # Récupérer les infos de collection depuis conference.yml
        collection_info = _get_hal_collection_info()
        
        # Statistiques des dépôts HAL
        total_communications = Communication.query.filter(
            Communication.status.in_([
                CommunicationStatus.ACCEPTE,
                CommunicationStatus.WIP_SOUMIS,
                CommunicationStatus.POSTER_SOUMIS
            ])
        ).count()
        
        hal_deposits = HALDeposit.query.all()
        
        stats = {
            'total_communications': total_communications,
            'total_deposits': len(hal_deposits),
            'pending_deposits': len([d for d in hal_deposits if d.status == 'pending']),
            'successful_deposits': len([d for d in hal_deposits if d.status == 'success']),
            'failed_deposits': len([d for d in hal_deposits if d.status == 'error']),
        }
        
        return render_template('admin/hal/dashboard.html', 
                             stats=stats, 
                             recent_deposits=hal_deposits[:10],
                             collection_info=collection_info)
    
    except HALConfigError as e:
        flash(f"Erreur configuration HAL: {e}", "danger")
        return redirect(url_for("admin.dashboard"))

@hal_bp.route('/admin/hal/test-connection')
@login_required 
def test_connection():
    """Test de connexion HAL"""
    if not current_user.is_admin:
        return jsonify({'error': 'Accès refusé'}), 403
    
    try:
        client = HALClient(test_mode=True)
        success, message = client.check_connection()
        
        # Ajouter les infos de collection
        collection_info = client.get_collection_info()
        
        return jsonify({
            'success': success,
            'message': message,
            'collection_info': collection_info
        })
        
    except HALConfigError as e:
        return jsonify({
            'success': False,
            'message': f'Erreur configuration HAL: {e}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        })

@hal_bp.route('/admin/hal/communications')
@login_required
def list_communications():
    """Liste des communications avec statut HAL"""
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))
    
    try:
        # Vérifier la configuration HAL
        collection_info = _get_hal_collection_info()
        
        # Récupérer toutes les communications acceptées selon votre enum
        communications = Communication.query.filter(
            Communication.status.in_([
                CommunicationStatus.ACCEPTE,
                CommunicationStatus.WIP_SOUMIS,
                CommunicationStatus.POSTER_SOUMIS
            ])
        ).all()
        
        # Enrichir avec les données HAL
        comm_with_hal = []
        for comm in communications:
            hal_deposit = HALDeposit.query.filter_by(communication_id=comm.id).first()
            
            # Vérifier l'IDHAL de l'auteur principal
            main_author = comm.authors[0] if comm.authors else None
            has_idhal = main_author and hasattr(main_author, 'idhal') and main_author.idhal
            
            comm_data = {
                'communication': comm,
                'hal_deposit': hal_deposit,
                'can_deposit': comm.hal_authorization and has_idhal,
                'missing_idhal': not has_idhal
            }
            comm_with_hal.append(comm_data)
        
        return render_template('admin/hal/communications.html', 
                             communications=comm_with_hal,
                             collection_info=collection_info)
    
    except HALConfigError as e:
        flash(f"Erreur configuration HAL: {e}", "danger")
        return redirect(url_for("admin.dashboard"))

@hal_bp.route('/admin/hal/deposit/<int:communication_id>', methods=['POST'])
@login_required
def deposit_communication(communication_id):
    """Déposer une communication sur HAL"""
    if not current_user.is_admin:
        return jsonify({'error': 'Accès refusé'}), 403
    
    communication = Communication.query.get_or_404(communication_id)
    
    # Vérifications
    if not communication.hal_authorization:
        return jsonify({'error': 'Dépôt HAL non autorisé'}), 400
    
    if not communication.user.idhal:
        return jsonify({'error': 'IDHAL manquant pour l\'auteur'}), 400
    
    # Vérifier s'il y a déjà un dépôt
    existing_deposit = HALDeposit.query.filter_by(communication_id=communication_id).first()
    if existing_deposit and existing_deposit.status == 'success':
        return jsonify({'error': 'Communication déjà déposée'}), 400
    
    try:
        # Vérifier la configuration HAL avant de procéder
        collection_info = _get_hal_collection_info()
        
        # Générer le XML
        xml_generator = HALXMLGenerator()
        xml_content = xml_generator.generate_for_communication(communication)
        
        # Créer ou mettre à jour l'enregistrement
        if not existing_deposit:
            deposit = HALDeposit(
                communication_id=communication_id,
                xml_content=xml_content,
                test_mode=True,
                collection_id=collection_info['collection_id']  # NOUVEAU : utiliser la collection configurée
            )
            db.session.add(deposit)
        else:
            deposit = existing_deposit
            deposit.xml_content = xml_content
            deposit.status = 'pending'
            deposit.error_message = None
            deposit.collection_id = collection_info['collection_id']  # NOUVEAU : mettre à jour
        
        # Effectuer le dépôt
        client = HALClient(test_mode=True)
        success, result = client.test_deposit_metadata(xml_content)
        
        if success:
            deposit.status = 'success'
            deposit.hal_id = result.get('id')
            deposit.hal_version = result.get('version')
            deposit.hal_password = result.get('password')
            deposit.hal_url = result.get('url')
            deposit.response_data = json.dumps(result)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Dépôt HAL réussi dans la collection {collection_info["collection_id"]}',
                'hal_id': deposit.hal_id,
                'hal_url': deposit.hal_url,
                'collection_id': collection_info['collection_id']
            })
        else:
            deposit.status = 'error'
            deposit.error_message = result.get('error', 'Erreur inconnue')
            deposit.response_data = json.dumps(result)
            
            db.session.commit()
            
            return jsonify({
                'success': False,
                'message': f'Échec dépôt HAL: {deposit.error_message}'
            })
    
    except (HALConfigError, HALXMLConfigError) as e:
        return jsonify({
            'success': False,
            'message': f'Erreur configuration HAL: {e}'
        })
    except Exception as e:
        if 'deposit' in locals():
            deposit.status = 'error'
            deposit.error_message = str(e)
            db.session.commit()
        
        return jsonify({
            'success': False,
            'message': f'Erreur technique: {str(e)}'
        })

@hal_bp.route('/admin/hal/status/<int:deposit_id>')
@login_required
def check_deposit_status(deposit_id):
    """Vérifier le statut d'un dépôt HAL"""
    if not current_user.is_admin:
        return jsonify({'error': 'Accès refusé'}), 403
    
    deposit = HALDeposit.query.get_or_404(deposit_id)
    
    if not deposit.hal_id:
        return jsonify({'error': 'Pas d\'ID HAL pour ce dépôt'}), 400
    
    try:
        client = HALClient(test_mode=True)
        success, status_data = client.get_deposit_status(deposit.hal_id, deposit.hal_version)
        
        if success:
            # Mettre à jour le statut local
            deposit.hal_status = status_data.get('status')
            deposit.last_check = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'success': True,
                'status': status_data
            })
        else:
            return jsonify({
                'success': False,
                'message': status_data.get('error')
            })
    
    except HALConfigError as e:
        return jsonify({
            'success': False,
            'message': f'Erreur configuration HAL: {e}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@hal_bp.route('/admin/hal/request-collection', methods=['GET', 'POST'])
@login_required
def request_collection():
    """Page pour demander la création de la collection HAL"""
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))
    
    try:
        # Charger la configuration depuis conference.yml
        config = current_app.conference_config
        collection_info = _get_hal_collection_info()
        
        # Extraire les informations du responsable depuis .env (générées par configure.py)
        import os
        
        # Utiliser les variables admin générées par configure.py
        admin_first_name = os.getenv('ADMIN_FIRST_NAME', 'Admin')
        admin_last_name = os.getenv('ADMIN_LAST_NAME', 'Responsable')
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        
        # Construire le nom complet et titre depuis conference.yml
        contact_name = f"{admin_first_name} {admin_last_name}"
        
        # Construire le titre à partir des infos du laboratoire organisateur
        organizing_lab = config.get('conference', {}).get('organizing_lab', {})
        lab_short_name = organizing_lab.get('short_name', 'Laboratoire organisateur')
        contact_title = f"Responsable du congrès, {lab_short_name}"
        
        # Login HAL - à ajouter manuellement dans .env si nécessaire
        hal_login = os.getenv('HAL_LOGIN', os.getenv('HAL_USERNAME', 'organizer-login'))
        
        # Données pour le template d'email
        email_data = {
            'contact_name': contact_name,
            'contact_title': contact_title,
            'contact_email': admin_email,
            'hal_login': hal_login,
            'conference_name': collection_info['conference_name'],
            'conference_dates': f"{config.get('dates', {}).get('conference', {}).get('start', '2026-06-02')} au {config.get('dates', {}).get('conference', {}).get('end', '2026-06-05')}",
            'conference_location': config.get('conference', {}).get('location', {}).get('city', 'Ville non spécifiée'),
            'organizing_lab_name': organizing_lab.get('name', 'Laboratoire organisateur'),
            'organizing_lab_short': lab_short_name,
            'collection_id': collection_info['collection_id'],  # NOUVEAU : utiliser la collection configurée
            'estimated_docs': 200,
            'submission_deadline': config.get('dates', {}).get('submission', {}).get('final', 'Mars 2026'),
            'deposit_start': config.get('dates', {}).get('conference', {}).get('start', 'Avril 2026')
        }
        
        if request.method == 'POST':
            # Récupérer les données du formulaire
            recipient_email = request.form.get('recipient_email', 'hal@ccsd.cnrs.fr')
            custom_message = request.form.get('custom_message', '')
            
            try:
                # Envoyer l'email
                from app.emails import send_hal_collection_request
                send_hal_collection_request(
                    recipient_email=recipient_email,
                    email_data=email_data,
                    custom_message=custom_message
                )
                
                flash(f'Demande de collection HAL {collection_info["collection_id"]} envoyée avec succès !', 'success')
                return redirect(url_for('hal.dashboard'))
                
            except Exception as e:
                flash(f'Erreur lors de l\'envoi : {str(e)}', 'danger')
        
        return render_template('admin/hal/request_collection.html', 
                             email_data=email_data,
                             collection_info=collection_info)
    
    except HALConfigError as e:
        flash(f"Erreur configuration HAL: {e}", "danger")
        return redirect(url_for("admin.dashboard"))

# NOUVEAU : Template de dashboard mis à jour
def get_hal_dashboard_template():
    """Template du dashboard HAL avec configuration dynamique"""
    return '''
{% extends "admin/base.html" %}

{% block title %}Tableau de bord HAL{% endblock %}

{% block content %}
<div class="container-fluid">
    <div class="row">
        <div class="col-md-12">
            <h2><i class="fas fa-database"></i> Intégration HAL - {{ collection_info.conference_name }}</h2>
            <p class="text-muted">
                Gestion des dépôts dans la collection {{ collection_info.collection_id }}
                {% if collection_info.test_mode %}<span class="badge bg-warning">Mode TEST</span>{% endif %}
            </p>
        </div>
    </div>
    
    <!-- Test de connexion -->
    <div class="row mb-4">
        <div class="col-md-12">
            <div class="card">
                <div class="card-header">
                    <h5>Test de connexion HAL - Collection {{ collection_info.collection_id }}</h5>
                </div>
                <div class="card-body">
                    <button id="test-connection" class="btn btn-primary">
                        <i class="fas fa-plug"></i> Tester la connexion
                    </button>
                    <div id="connection-result" class="mt-3"></div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Statistiques -->
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card text-white bg-info">
                <div class="card-body">
                    <h4>{{ stats.total_communications }}</h4>
                    <p>Communications totales</p>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-success">
                <div class="card-body">
                    <h4>{{ stats.successful_deposits }}</h4>
                    <p>Dépôts réussis</p>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-warning">
                <div class="card-body">
                    <h4>{{ stats.pending_deposits }}</h4>
                    <p>En attente</p>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-danger">
                <div class="card-body">
                    <h4>{{ stats.failed_deposits }}</h4>
                    <p>Échecs</p>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Actions rapides -->
    <div class="row">
        <div class="col-md-12">
            <div class="card">
                <div class="card-header">
                    <h5>Actions rapides</h5>
                </div>
                <div class="card-body">
                    <a href="{{ url_for('hal.list_communications') }}" class="btn btn-primary">
                        <i class="fas fa-list"></i> Gérer les communications
                    </a>
                    <a href="https://hal.science/{{ collection_info.collection_id }}" target="_blank" class="btn btn-info">
                        <i class="fas fa-external-link-alt"></i> Voir collection {{ collection_info.collection_id }}
                    </a>
                    <a href="{{ url_for('hal.request_collection') }}" class="btn btn-secondary">
                        <i class="fas fa-envelope"></i> Demander la collection
                    </a>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
document.getElementById('test-connection').addEventListener('click', function() {
    const button = this;
    const result = document.getElementById('connection-result');
    
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Test en cours...';
    
    fetch('/admin/hal/test-connection')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                let message = data.message;
                if (data.collection_info) {
                    message += '<br><small>Collection: ' + data.collection_info.collection_id + '</small>';
                }
                result.innerHTML = '<div class="alert alert-success"><i class="fas fa-check"></i> ' + message + '</div>';
            } else {
                result.innerHTML = '<div class="alert alert-danger"><i class="fas fa-times"></i> ' + data.message + '</div>';
            }
        })
        .catch(error => {
            result.innerHTML = '<div class="alert alert-danger"><i class="fas fa-times"></i> Erreur: ' + error + '</div>';
        })
        .finally(() => {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-plug"></i> Tester la connexion';
        });
});
</script>
{% endblock %}
'''

