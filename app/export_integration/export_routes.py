# app/export_integration/export_routes.py
"""
Routes pour la gestion des exports (HAL + DOI)
"""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, Response, current_app)
from datetime import datetime
from flask_login import login_required, current_user
from ..models import Communication, db
from .export_manager import ExportManager
from .doi_export import DOIExporter

export_bp = Blueprint('export', __name__)

@export_bp.route('/admin/export/dashboard')
@login_required
def dashboard():
    """Tableau de bord des exports"""
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))

    from ..models import HALDeposit

    exporter = DOIExporter()
    eligible = exporter.get_eligible_communications()

    stats = {
        'total_communications': Communication.query.count(),
        'with_doi': Communication.query.filter(
            Communication.doi.isnot(None)
        ).count(),
        'on_hal': HALDeposit.query.filter_by(status='success').count(),
        'eligible': len(eligible),
        'ready_for_export': len([
            c for c in eligible if c.doi and c.public_url
        ]),
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


# ======================================================================
# Lot DOI à destination de l'Inist
# ======================================================================

@export_bp.route('/admin/export/doi/preview')
@login_required
def doi_preview():
    """
    Simulation : rapporte les DOI et URL qui seraient attribués,
    sans rien écrire en base.
    """
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403

    try:
        exporter = DOIExporter()
        report = exporter.assign_identifiers(dry_run=True)
    except Exception as e:
        current_app.logger.error(f"Erreur prévisualisation DOI: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

    return jsonify({
        'success': True,
        'dry_run': True,
        'total': len(report),
        'a_attribuer': len([r for r in report if r['action'] != 'inchangé']),
        'erreurs': len([r for r in report if r['error']]),
        'communications': report,
    })


@export_bp.route('/admin/export/doi/assign', methods=['POST'])
@login_required
def doi_assign():
    """
    Attribue et enregistre en base les DOI et URL manquants.
    """
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403

    try:
        exporter = DOIExporter()
        report = exporter.assign_identifiers(dry_run=False)
    except Exception as e:
        current_app.logger.error(f"Erreur attribution DOI: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

    modified = [r for r in report if r['action'] != 'inchangé']
    current_app.logger.info(
        f"Attribution DOI par {current_user.email} : "
        f"{len(modified)} communications modifiées"
    )

    return jsonify({
        'success': True,
        'dry_run': False,
        'total': len(report),
        'modifiees': len(modified),
        'erreurs': len([r for r in report if r['error']]),
        'communications': report,
    })


@export_bp.route('/admin/export/doi/package')
@login_required
def doi_package():
    """
    Télécharge l'archive ZIP destinée à l'Inist : un XML DataCite par
    communication, plus le CSV de correspondance DOI vers URL.

    N'attribue aucun identifiant : les communications sans DOI ou sans
    URL sont exclues et signalées dans les logs. Passer par
    /admin/export/doi/assign au préalable.
    """
    if not current_user.is_admin:
        flash("Accès refusé", "danger")
        return redirect(url_for("main.index"))

    try:
        exporter = DOIExporter()
        archive, report = exporter.build_archive(assign=False)
    except Exception as e:
        current_app.logger.error(f"Erreur génération lot DOI: {e}")
        flash(f"Erreur lors de la génération du lot DOI : {e}", "danger")
        return redirect(url_for('export.dashboard'))

    if report['errors']:
        for err in report['errors']:
            current_app.logger.warning(
                f"Lot DOI - communication {err['id']} exclue : {err['error']}"
            )

    if report['exported'] == 0:
        flash(
            "Aucune communication exportable. "
            "Attribuez d'abord les DOI et les URL.",
            "warning"
        )
        return redirect(url_for('export.dashboard'))

    conference = current_app.conference_config.get('conference', {}) or {}
    year = conference.get('year', datetime.now().year)
    filename = f"lot_doi_datacite_{year}.zip"

    return Response(
        archive,
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
