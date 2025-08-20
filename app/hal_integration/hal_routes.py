from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Communication, db, HALDeposit, CommunicationStatus
from .hal_client import HALClient
from .hal_xml_generator import HALXMLGenerator
from datetime import datetime
import json

hal_bp = Blueprint('hal', __name__)

@hal_bp.route('/admin/hal/dashboard')
@login_required
def dashboard():
    """Tableau de bord HAL"""
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))
    
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
                         recent_deposits=hal_deposits[:10])

@hal_bp.route('/admin/hal/test-connection')
@login_required 
def test_connection():
    """Test de connexion HAL"""
    if not current_user.is_admin:
        return jsonify({'error': 'Accès refusé'}), 403
    
    try:
        client = HALClient(test_mode=True)
        success, message = client.check_connection()
        
        return jsonify({
            'success': success,
            'message': message
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
    
    # Récupérer toutes les communications acceptées selon votre enum
    from app.models import CommunicationStatus
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
                         communications=comm_with_hal)

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
        # Générer le XML
        xml_generator = HALXMLGenerator()
        xml_content = xml_generator.generate_for_communication(communication)
        
        # Créer ou mettre à jour l'enregistrement
        if not existing_deposit:
            deposit = HALDeposit(
                communication_id=communication_id,
                xml_content=xml_content,
                test_mode=True
            )
            db.session.add(deposit)
        else:
            deposit = existing_deposit
            deposit.xml_content = xml_content
            deposit.status = 'pending'
            deposit.error_message = None
        
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
                'message': 'Dépôt HAL réussi',
                'hal_id': deposit.hal_id,
                'hal_url': deposit.hal_url
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
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

# Template pour le dashboard HAL
hal_dashboard_template = '''
{% extends "admin/base.html" %}

{% block title %}Tableau de bord HAL{% endblock %}

{% block content %}
<div class="container-fluid">
    <div class="row">
        <div class="col-md-12">
            <h2><i class="fas fa-database"></i> Intégration HAL - SFT 2026</h2>
            <p class="text-muted">Gestion des dépôts dans la collection SFT2026 (Mode TEST)</p>
        </div>
    </div>
    
    <!-- Test de connexion -->
    <div class="row mb-4">
        <div class="col-md-12">
            <div class="card">
                <div class="card-header">
                    <h5>Test de connexion HAL</h5>
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
                    <a href="https://hal.science/SFT2026" target="_blank" class="btn btn-info">
                        <i class="fas fa-external-link-alt"></i> Voir collection SFT2026
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
                result.innerHTML = '<div class="alert alert-success"><i class="fas fa-check"></i> ' + data.message + '</div>';
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
