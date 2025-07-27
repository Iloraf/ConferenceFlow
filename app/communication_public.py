from flask import Blueprint, render_template, abort, send_file, url_for
import os
import qrcode
from io import BytesIO
from .models import Communication

public_comm = Blueprint("public_comm", __name__)

# @public_comm.route('/communication/<int:comm_id>')
# def view_communication(comm_id):
#     """Page publique d'une communication accessible via QR code."""
#     communication = Communication.query.get_or_404(comm_id)
    
    # return f"<h1>Communication #{comm_id}</h1><p>{communication.title}</p>" # 


@public_comm.route('/communication/<int:comm_id>')
def view_communication(comm_id):
    """Page publique d'une communication accessible via QR code."""
    communication = Communication.query.get_or_404(comm_id)
    
    # Récupérer tous les fichiers disponibles
    available_files = {
        'resume': communication.get_latest_file('résumé'),
        'article': communication.get_latest_file('article'), 
        'poster': communication.get_latest_file('poster'),
        'wip': communication.get_latest_file('wip')
    }
    
    # Nettoyer les fichiers None
    available_files = {k: v for k, v in available_files.items() if v is not None}
    
    # Affichage simple pour tester
    html = f"""
    <h1>Communication #{comm_id}</h1>
    <h2>{communication.title}</h2>
    <p><strong>Type:</strong> {communication.type}</p>
    <p><strong>Statut:</strong> {communication.status.value}</p>
    
    <h3>Fichiers disponibles :</h3>
    <ul>
    """
    for file_type, file_obj in available_files.items():
        download_url = f"/public/communication/{comm_id}/file/{file_type}"
        html += f'<li>{file_type.title()} : <a href="{download_url}">{file_obj.original_filename}</a></li>'
    
    # for file_type, file_obj in available_files.items():
    #     html += f"<li>{file_type.title()} : {file_obj.original_filename}</li>"

    available_files = {k: v for k, v in available_files.items() if v is not None}
    
    return render_template('public/communication_view.html',
                         communication=communication,
                         available_files=available_files)

    


@public_comm.route('/communication/<int:comm_id>/file/<file_type>')
def download_communication_file(comm_id, file_type):
    """Téléchargement public d'un fichier de communication."""
    communication = Communication.query.get_or_404(comm_id)
    
    # Types de fichiers autorisés
    allowed_types = ['résumé', 'resume', 'article', 'poster', 'wip']
    
    # Normaliser le type (résumé/resume sont équivalents)
    if file_type == 'resume':
        file_type = 'résumé'
    
    if file_type not in allowed_types:
        abort(404)
    
    # Récupérer le fichier
    file_obj = communication.get_latest_file(file_type)
    if not file_obj:
        abort(404, description=f"Aucun fichier {file_type} disponible")
    
    # Vérifier que le fichier existe physiquement
    if not os.path.exists(file_obj.file_path):
        abort(404, description="Fichier introuvable")
    
    return send_file(file_obj.file_path, 
                    as_attachment=True, 
                    download_name=file_obj.original_filename)

@public_comm.route('/communication/<int:comm_id>/qr.png')
def generate_qr_code(comm_id):
    """Génère et retourne le QR code PNG pour une communication."""
    communication = Communication.query.get_or_404(comm_id)
    
    # URL de la communication
    comm_url = url_for('public_comm.view_communication', comm_id=comm_id, _external=True)
    
    # Générer le QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(comm_url)
    qr.make(fit=True)
    
    # Créer l'image
    qr_image = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir en bytes pour l'envoi
    img_buffer = BytesIO()
    qr_image.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    return send_file(img_buffer, 
                    mimetype='image/png',
                    as_attachment=True,
                    download_name=f'QR_comm_{comm_id}.png')
