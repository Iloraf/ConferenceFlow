# app/export_integration/export_routes.py
"""
Routes pour la gestion des exports (HAL + DOI)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from ..models import Communication, db
from .export_manager import ExportManager

export_bp = Blueprint('export', __name__)

@export_bp.route('/admin/export/dashboard')
@login_required
def dashboard():
    """Tableau de bord des exports"""
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))
    
    export_manager = ExportManager()
    
    # Statistiques globales
    total_communications = Communication.query.count()
    communications_with_doi = Communication.query.filter(Communication.doi.isnot(None)).count()
    communications_on_hal = Communication.query.filter(Communication.hal_url.isnot(None)).count()
    
    stats = {
        'total_communications': total_communications,
        'with_doi': communications_with_doi,
        'on_hal': communications_on_hal,
        'ready_for_export': Communication.query.filter(
            Communication.abstract.isnot(None),
            Communication.doi.isnot(None)
        ).count()
    }
    
    return render_template('admin/export/dashboard.html', stats=stats)

@export_bp.route('/admin/export/communication/<int:comm_id>')
@login_required
def communication_export_detail(comm_id):
    """Détail d'export d'une communication"""
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))
    
    export_manager = ExportManager()
    status = export_manager.get_export_status(comm_id)
    
    if not status:
        flash("Communication introuvable", "error")
        return redirect(url_for('export.dashboard'))
    
    return render_template('admin/export/communication_detail.html', status=status)

@export_bp.route('/admin/export/prepare/<int:comm_id>', methods=['POST'])
@login_required
def prepare_communication(comm_id):
    """Prépare une communication pour l'export"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    export_manager = ExportManager()
    comm, message = export_manager.prepare_communication_for_export(comm_id)
    
    if comm:
        return jsonify({'success': True, 'message': message, 'doi': comm.doi})
    else:
        return jsonify({'success': False, 'message': message})

@export_bp.route('/admin/export/hal/<int:comm_id>', methods=['POST'])
@login_required
def export_to_hal(comm_id):
    """Exporte vers HAL"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    
    export_manager = ExportManager()
    success, message = export_manager.export_to_hal(comm_id)
    
    return jsonify({'success': success, 'message': message})

@export_bp.route('/admin/export/doi-xml/<int:comm_id>')
@login_required
def download_doi_xml(comm_id):
    """Télécharge le XML DataCite"""
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))
    
    export_manager = ExportManager()
    xml_content, message = export_manager.generate_doi_xml(comm_id)
    
    if xml_content:
        comm = Communication.query.get(comm_id)
        filename = f"datacite_{comm.doi.replace('/', '_')}.xml"
        
        return Response(
            xml_content,
            mimetype='application/xml',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    else:
        flash(message, "error")
        return redirect(url_for('export.communication_export_detail', comm_id=comm_id))
