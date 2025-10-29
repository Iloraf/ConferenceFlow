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

# app/conference_routes.py
from flask import Blueprint, render_template_string, render_template, send_file, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime
import csv
import os
from collections import defaultdict
from io import BytesIO
import tempfile
import yaml
from pathlib import Path


try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

conference = Blueprint("conference", __name__)

def load_programme_csv_common():
    """Fonction commune pour charger le programme depuis le CSV avec gestion du temps."""
    csv_path = os.path.join(current_app.root_path, 'static', 'content', 'programme.csv')
    if not os.path.exists(csv_path):
        current_app.logger.warning(f"Fichier programme.csv non trouvé à: {csv_path}")
        return {}
        
    programme_data = defaultdict(lambda: {'date': '', 'sessions': []})
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=';')
            
            for row in reader:
                # Fonction pour nettoyer une valeur de manière sûre
                def clean_value(value):
                    if value is None:
                        return ''
                    if isinstance(value, str):
                        return value.strip()
                    if isinstance(value, (list, tuple)):
                        return str(value[0]).strip() if value else ''
                    return str(value).strip()
                
                def clean_key(key):
                    if key is None:
                        return ''
                    if isinstance(key, str):
                        return key.strip()
                    return str(key).strip()
                
                # Nettoie les espaces et gère tous les types de valeurs
                cleaned_row = {}
                for k, v in row.items():
                    clean_k = clean_key(k)
                    clean_v = clean_value(v)
                    cleaned_row[clean_k] = clean_v
                
                jour = cleaned_row.get('jour', '')
                if not jour:
                    continue
                
                # Définit la date du jour si elle n'est pas encore définie
                date_value = cleaned_row.get('date', '')
                if not programme_data[jour]['date'] and date_value:
                    programme_data[jour]['date'] = date_value
                
                # Construction de la session avec parsing de l'heure
                time_str = cleaned_row.get('heure', '') or ''
                session = {
                    'time': time_str,
                    'title': cleaned_row.get('titre', '') or '',
                    'type': cleaned_row.get('type', '') or 'session',
                    'is_past': is_session_past(date_value, time_str)  # NOUVEAU
                }
                
                # ... rest of your existing code for adding optional fields ...
                orateur = cleaned_row.get('orateur', '')
                if orateur:
                    session['speaker'] = orateur
                
                lieu = cleaned_row.get('lieu', '')
                if lieu:
                    session['location'] = lieu
                
                description = cleaned_row.get('description', '')
                if description:
                    session['description'] = description
                
                # Gestion des sessions parallèles
                sessions_paralleles = []
                for i in range(1, 6):
                    session_key = f'session_{i}'
                    session_value = cleaned_row.get(session_key, '')
                    if session_value:
                        sessions_paralleles.append(session_value)
                
                if sessions_paralleles:
                    session['sessions'] = sessions_paralleles
                    session['type'] = 'parallel'
                
                # Gestion des ateliers parallèles
                ateliers = []
                for i in range(1, 3):
                    atelier_key = f'atelier_{i}'
                    atelier_value = cleaned_row.get(atelier_key, '')
                    if atelier_value:
                        ateliers.append(atelier_value)
                
                if ateliers:
                    session['ateliers'] = ateliers
                    session['type'] = 'workshop'
                
                programme_data[jour]['sessions'].append(session)
                
    except Exception as e:
        current_app.logger.error(f"Erreur lors du chargement du programme: {e}")
        return {}
    
    # Conversion en dictionnaire normal et tri des jours
    result = {}
    for jour in sorted(programme_data.keys()):
        result[f'day{jour}'] = dict(programme_data[jour])
    
    return result

def is_session_past(date_str, time_str):
    """Détermine si une session est passée en tenant compte de la date ET de l'heure."""
    if not date_str or not time_str:
        return False
    
    try:
        from datetime import datetime
        import re
        
        # Extraire l'heure de fin de la session (format: "13h00-14h00")
        time_match = re.search(r'(\d{1,2})h(\d{2})-(\d{1,2})h(\d{2})', time_str)
        if not time_match:
            return False
            
        end_hour = int(time_match.group(3))
        end_min = int(time_match.group(4))
        
        # Parser la date au format "Mardi 1 juillet 2025"
        date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_str)
        if date_match:
            day = int(date_match.group(1))
            month_name = date_match.group(2).lower()
            year = int(date_match.group(3))
            
            # Conversion nom de mois français -> numéro
            mois_fr = {
                'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
                'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8,
                'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
            }
            
            month = mois_fr.get(month_name)
            if not month:
                return False
            
            # Créer l'objet datetime de la session
            session_date = datetime(year, month, day, end_hour, end_min)
            
            # Comparer avec maintenant
            now = datetime.now()
            
            return now > session_date
        
        # Si pas de date parsée, fallback sur test simple
        return False
        
    except Exception as e:
        current_app.logger.error(f"Erreur parsing date {date_str} {time_str}: {e}")
        return False


@conference.route("/programme")
def programme():
    """Affiche le programme de la conférence."""
    programme_data = load_programme_csv_common()
    
    # Fallback si pas de données
    if not programme_data:
        programme_data = {
            'day1': {
                'date': 'Programme à venir',
                'sessions': [
                    {'time': 'À définir', 'title': 'Le programme détaillé sera publié prochainement', 'type': 'info'}
                ]
            }
        }
    
    return render_template("conference/programme.html", programme=programme_data)

@conference.route("/programme/pdf")
def programme_pdf():
    """Génère et retourne le programme en PDF."""
    
    if not WEASYPRINT_AVAILABLE:
        return "WeasyPrint n'est pas installé. Installez-le avec: pip install weasyprint", 500
    
    # Charger la configuration depuis conference.yml
    from app.config_loader import ConfigLoader
    config_loader = ConfigLoader()
    config = config_loader.load_conference_config()
    
    # Debug pour voir la structure réelle
    current_app.logger.info(f"Structure config chargée: {list(config.keys()) if config else 'Config vide'}")
    
    # Utilise la même fonction que la route principale
    programme_data = load_programme_csv_common()  # ou votre fonction existante
    
    current_app.logger.info(f"PDF - Données trouvées: {list(programme_data.keys()) if programme_data else 'AUCUNE'}")
    
    # Fallback si pas de données
    if not programme_data:
        current_app.logger.error("PDF - AUCUNE DONNÉE - Utilisation du fallback")
        programme_data = {
            'day1': {
                'date': 'Programme à venir',
                'sessions': [
                    {'time': 'À définir', 'title': 'Le programme détaillé sera publié prochainement', 'type': 'info'}
                ]
            }
        }
    
    # Template HTML intégré (avec variables dynamiques)
    html_template = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: A4;
            margin: 2cm;
            @bottom-center {
                content: "Page " counter(page) " / " counter(pages);
                font-size: 10pt;
                color: #666;
            }
        }
        
        body {
            font-family: 'Arial', sans-serif;
            font-size: 11pt;
            line-height: 1.4;
            color: #333;
        }
        
        sup {
            vertical-align: super;
            font-size: 0.7em;
            line-height: 0;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #007bff;
            padding-bottom: 20px;
        }
        
        .header h1 {
            color: #007bff;
            font-size: 24pt;
            margin-bottom: 10px;
        }
        
        .header .subtitle {
            font-size: 14pt;
            color: #666;
            margin-bottom: 5px;
        }
        
        .day-section {
            page-break-before: auto;
            margin-bottom: 40px;
        }
        
        .day-header {
            background-color: #007bff;
            color: white;
            padding: 15px;
            margin-bottom: 20px;
            font-size: 16pt;
            font-weight: bold;
        }
        
        .session {
            margin-bottom: 15px;
            border-left: 4px solid #e9ecef;
            padding: 10px 15px;
            background-color: #f8f9fa;
            break-inside: avoid;
        }
        
        .session-plenary {
            border-left-color: #dc3545;
            background-color: rgba(220,53,69,0.1);
        }
        
        .session-parallel {
            border-left-color: #28a745;
            background-color: rgba(40,167,69,0.1);
        }
        
        .session-workshop {
            border-left-color: #ffc107;
            background-color: rgba(255,193,7,0.1);
        }
        
        .session-social {
            border-left-color: #17a2b8;
            background-color: rgba(23,162,184,0.1);
        }
        
        .session-ceremony {
            border-left-color: #6f42c1;
            background-color: rgba(111,66,193,0.1);
        }
        
        .session-break {
            border-left-color: #6c757d;
            background-color: #f8f9fa;
        }
        
        .session-time {
            font-weight: bold;
            color: #007bff;
            font-size: 12pt;
        }
        
        .session-title {
            font-size: 13pt;
            font-weight: bold;
            margin: 5px 0;
        }
        
        .session-speaker {
            color: #dc3545;
            font-style: italic;
            margin: 3px 0;
        }
        
        .session-location {
            color: #666;
            font-size: 10pt;
            margin: 3px 0;
        }
        
        .session-description {
            color: #666;
            font-size: 10pt;
            margin: 3px 0;
        }
        
        .parallel-sessions {
            margin-top: 10px;
            padding: 8px;
            background-color: rgba(255,255,255,0.7);
            border-radius: 4px;
            border: 1px solid rgba(40,167,69,0.3);
        }
        
        .workshop-sessions {
            margin-top: 10px;
            padding: 8px;
            background-color: rgba(255,255,255,0.7);
            border-radius: 4px;
            border: 1px solid rgba(255,193,7,0.3);
        }
        
        .parallel-title {
            font-weight: bold;
            font-size: 10pt;
            margin-bottom: 5px;
            color: #28a745;
        }
        
        .workshop-title {
            font-weight: bold;
            font-size: 10pt;
            margin-bottom: 5px;
            color: #ffc107;
        }
        
        .parallel-list, .workshop-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        
        .parallel-list li, .workshop-list li {
            padding: 2px 0;
            font-size: 10pt;
        }
        
        .parallel-list li:before {
            content: "▪ ";
            color: #28a745;
            font-weight: bold;
        }
        
        .workshop-list li:before {
            content: "🔧 ";
        }
        
        .legend {
            margin-top: 30px;
            padding: 15px;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            break-inside: avoid;
        }
        
        .legend h3 {
            font-size: 12pt;
            margin-bottom: 10px;
            color: #007bff;
        }
        
        .legend-item {
            display: inline-block;
            margin: 3px 15px 3px 0;
            font-size: 9pt;
        }
        
        .legend-color {
            display: inline-block;
            width: 12px;
            height: 12px;
            margin-right: 5px;
            vertical-align: middle;
        }
        
        .footer-info {
            margin-top: 30px;
            padding: 15px;
            background-color: #e9ecef;
            font-size: 10pt;
            text-align: center;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Programme du Congrès</h1>
        <div class="subtitle">{{ config.conference.name|safe }}</div>
        <div class="subtitle">{{ config.location.city }}, {{ config.dates.dates }}</div>
        <div class="subtitle">« {{ config.conference.theme }} »</div>
    </div>
    
    {% for day_key, day_data in programme.items() %}
    <div class="day-section">
        <div class="day-header">
            {{ day_data.date }}
        </div>
        
        {% for session in day_data.sessions %}
        <div class="session session-{{ session.type }}">
            <div class="session-time">{{ session.time }}</div>
            <div class="session-title">{{ session.title }}</div>
            
            {% if session.speaker %}
            <div class="session-speaker">{{ session.speaker }}</div>
            {% endif %}
            
            {% if session.location %}
            <div class="session-location">📍 {{ session.location }}</div>
            {% endif %}
            
            {% if session.description %}
            <div class="session-description">{{ session.description }}</div>
            {% endif %}
            
            {% if session.sessions %}
            <div class="parallel-sessions">
                <div class="parallel-title">Sessions parallèles :</div>
                <ul class="parallel-list">
                    {% for parallel_session in session.sessions %}
                    <li>{{ parallel_session }}</li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
            
            {% if session.ateliers %}
            <div class="workshop-sessions">
                <div class="workshop-title">Ateliers en parallèle :</div>
                <ul class="workshop-list">
                    {% for atelier in session.ateliers %}
                    <li>{{ atelier }}</li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    {% endfor %}
    
    <div class="legend">
        <h3>Légende des types de sessions</h3>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #dc3545;"></span>
            Conférence plénière
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #28a745;"></span>
            Sessions parallèles
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #ffc107;"></span>
            Ateliers / Posters
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #17a2b8;"></span>
            Événements sociaux
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #6c757d;"></span>
            Pauses et repas
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #6f42c1;"></span>
            Cérémonies
        </div>
    </div>
    
    <div class="footer-info">
        {{ config.conference.name|safe }} - {{ config.conference.short_name }}<br>
        {{ config.location.venue }} - {{ config.location.city }}
    </div>
</body>
</html>
    """
    
    try:
        # Rendu du template HTML avec les deux variables
        rendered_html = render_template_string(html_template, programme=programme_data, config=config)
        
        # Génération du PDF
        html_doc = HTML(string=rendered_html)
        pdf_buffer = BytesIO()
        html_doc.write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        
        # Création d'un fichier temporaire pour servir le PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_buffer.getvalue())
            tmp_file_path = tmp_file.name
        
        # Retour du fichier PDF avec nom dynamique
        return send_file(
            tmp_file_path,
            as_attachment=True,
            download_name=f'Programme_{config["conference"]["short_name"].replace(" ", "_")}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la génération du PDF: {e}")
        return f"Erreur lors de la génération du PDF: {str(e)}", 500
    
    finally:
        # Nettoyage du fichier temporaire
        try:
            if 'tmp_file_path' in locals():
                os.unlink(tmp_file_path)
        except:
            pass

@conference.route("/programme/preview")
def programme_preview():
    """Prévisualise le programme dans le format PDF (en HTML)."""
    
    # Réutilise la même fonction de chargement
    programme_data = load_programme_csv_common()  # Fonction définie dans votre route principale
    
    if not programme_data:
        programme_data = {
            'day1': {
                'date': 'Programme à venir',
                'sessions': [
                    {'time': 'À définir', 'title': 'Le programme détaillé sera publié prochainement', 'type': 'info'}
                ]
            }
        }
    
    return render_template("conference/programme_pdf_preview.html", programme=programme_data)

@conference.route("/localisation")
def localisation():
    """Affiche les informations de localisation."""
    from flask import current_app
    
    # Récupérer les données depuis conference.yml
    conference_config = current_app.conference_config
    location_info = conference_config.get('location', {})
    transport_info = conference_config.get('transport', {})
    accommodation_info = conference_config.get('accommodation', {})
    city_info = conference_config.get('city_info', {})
    
    # DEBUG - Afficher ce qui est lu depuis le YAML
    print("=== DEBUG ACCOMMODATION ===")
    print("accommodation_info:", accommodation_info)
    print("Type:", type(accommodation_info))
    if accommodation_info:
        print("Keys:", list(accommodation_info.keys()))
        platform = accommodation_info.get('platform', {})
        print("Platform:", platform)
        if platform:
            print("Platform keys:", list(platform.keys()) if isinstance(platform, dict) else "Not a dict")
            print("URL value:", platform.get('url', 'NOT FOUND'))
    print("=========================")
    
    # Structurer les données pour le template
    venues = {
        'main': {
            'name': location_info.get('venue', 'Centre de congrès'),
            'address': location_info.get('address', 'Adresse à définir'),
            'description': location_info.get('description', 'Description à compléter'),
            'image': location_info.get('image', 'images/venue_default.jpg'),
            'lat': location_info.get('coordinates', {}).get('latitude', 48.674),
            'lng': location_info.get('coordinates', {}).get('longitude', 6.143)
        },
        'transport': _format_transport_data(transport_info),
        'accommodation': accommodation_info  # Passer directement les données
    }
    
    # Variables supplémentaires pour le template
    conference_location = {
        'city': location_info.get('city', 'Nancy'),
        'region': location_info.get('region', 'Grand Est')
    }
    
    conference_dates = {
        'dates': '2-5 juin 2026'
    }
    
    # DEBUG - Vérifier ce qui est passé au template
    print("=== DEBUG VENUES ===")
    print("venues['accommodation']:", venues['accommodation'])
    print("==================")
    
    return render_template("conference/localisation.html", 
                         venues=venues, 
                         city_info=city_info,
                         conference_location=conference_location,
                         conference_dates=conference_dates)

def _format_transport_data(transport_info):
    """Formate les données de transport pour le template."""
    transport_mapping = {
        'train': {
            'title': 'Train',
            'info': transport_info.get('train', {}).get('description', 'Informations à venir')
        },
        'car': {
            'title': 'Voiture',
            'info': transport_info.get('car', {}).get('description', 'Informations à venir')
        },
        'plane': {
            'title': 'Avion',
            'info': transport_info.get('plane', {}).get('description', 'Informations à venir')
        },
        'local': {
            'title': 'Transports locaux',
            'info': transport_info.get('local', {}).get('description', 'Informations à venir')
        }
    }
    
    return transport_mapping

@conference.route("/organisation")
def organisation():
    """Affiche les informations sur l'organisation."""
    
    def load_csv_data(filename):
        """Charge les données depuis un fichier CSV."""
        csv_path = os.path.join(current_app.root_path, 'static', 'content', filename)
        if not os.path.exists(csv_path):
            current_app.logger.warning(f"Fichier CSV non trouvé : {csv_path}")
            return []
            
        data = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file, delimiter=';')
                for row in reader:
                    # Nettoie les espaces en début/fin
                    cleaned_row = {k.strip(): v.strip() for k, v in row.items()}
                    data.append(cleaned_row)
        except Exception as e:
            current_app.logger.error(f"Erreur lors du chargement de {filename}: {e}")
            return []
            
        return data
    
    # Chargement des données CSV
    organizing_members = load_csv_data('comite_local.csv')
    scientific_members = load_csv_data('comite_sft.csv')
    sponsors_data = load_csv_data('sponsors.csv')
    
    # Construction de la structure de données
    committees = {
        'organizing': {
            'title': 'Comité local d\'organisation',
            'presidents': [],  # Liste pour plusieurs présidents
            'members': []
        },
        'scientific': {
            'title': 'Comité scientifique de la SFT',
            'members': []  # Simplifié : juste des membres
        },
        'sponsors': []
    }
    
    # Traitement du comité d'organisation
    for member in organizing_members:
        member_data = {
            'name': member.get('nom', ''),
            'role': member.get('role', ''),
            'institution': member.get('institution', '')
        }
        
        # Les présidents sont identifiés par le rôle "Président"
        if member.get('role', '').lower() in ['président', 'president', 'présidente']:
            committees['organizing']['presidents'].append(member_data)
        else:
            committees['organizing']['members'].append(member_data)
    
    # Traitement du comité scientifique
    for member in scientific_members:
        member_data = {
            'name': member.get('nom', ''),
            'institution': member.get('institution', ''),
            'role': member.get('role', '')  # Au cas où il y aurait des rôles spéciaux
        }
        committees['scientific']['members'].append(member_data)
    
    # Tri alphabétique par nom de famille pour le comité scientifique
    committees['scientific']['members'].sort(key=lambda x: x['name'].split()[-1])
    
    # Traitement des sponsors
    for sponsor in sponsors_data:
        sponsor_data = {
            'name': sponsor.get('nom', ''),
            'level': sponsor.get('niveau', 'bronze').lower(),
            'logo': sponsor.get('logo', 'default.png'),
            'url': sponsor.get('url', ''),  # Site web du sponsor
            'description': sponsor.get('description', '')
        }
        committees['sponsors'].append(sponsor_data)
    
    # Tri des sponsors par niveau (or > argent > bronze)
    level_order = {'or': 1, 'gold': 1, 'argent': 2, 'silver': 2, 'bronze': 3}
    committees['sponsors'].sort(key=lambda x: level_order.get(x['level'], 4))
    
    # Valeurs par défaut si aucun président n'est trouvé
    if not committees['organizing']['presidents']:
        committees['organizing']['presidents'] = [{
            'name': 'À définir', 
            'role': 'Président', 
            'institution': 'Organisation en cours'
        }]
    
    # Valeurs par défaut si aucun membre scientifique
    if not committees['scientific']['members']:
        committees['scientific']['members'] = [{
            'name': 'Société Française de Thermique',
            'institution': 'Comité scientifique en cours de constitution',
            'role': ''
        }]
    
    # Informations de contact (peuvent être déplacées dans un fichier config plus tard)
    contact_info = {
        'general': {
            'email': 'contact@sft2026.fr',
            'phone': '+33 3 XX XX XX XX',
            'address': 'Université de Lorraine, Nancy'
        },
        'organization': {
            'email': 'organisation@sft2026.fr',
            'description': 'Questions sur l\'organisation du congrès'
        },
        'scientific': {
            'email': 'scientifique@sft2026.fr',
            'description': 'Questions scientifiques et communications'
        },
        'registration': {
            'email': 'inscription@sft2026.fr',
            'description': 'Inscriptions et paiements'
        }
    }
    
    # Statistiques pour affichage (optionnel)
    stats = {
        'organizing_members': len(committees['organizing']['members']) + len(committees['organizing']['presidents']),
        'scientific_members': len(committees['scientific']['members']),
        'sponsors_count': len(committees['sponsors'])
    }
    
    return render_template("conference/organisation.html", 
                         committees=committees,
                         contact_info=contact_info,
                         stats=stats)

@conference.route("/inscription-conference")
def inscription_conference():
    """Affiche les informations d'inscription à la conférence."""
    
    # Récupérer la configuration des prix depuis le fichier YAML
    fees_config = current_app.conference_config.get('fees', {})
    registration_urls = current_app.conference_config.get('registration_urls', {})
    
    # Si la configuration n'est pas disponible, utiliser des valeurs par défaut
    if not fees_config:
        fees = {
            'early': {
                'date': '15 avril 2026',
                'student': 300,
                'member_indiv': 400,
                'member_collec': 460,
                'not_member': 510,
            },
            'regular': {
                'date': 'Après le 15 avril 2026',
                'student': 460,
                'member_indiv': 550,
                'member_collec': 610,
                'not_member': 660,
            },
            'included': [
                'Accès à toutes les sessions',
                'Documents de la conférence',
                'Pauses café et déjeuners',
                'Cocktail de bienvenue',
            ],
            'optional': [
                {'item': 'Accompagnant', 'price': 150}
            ]
        }
    else:
        # Convertir les dates du format YAML vers français
        from datetime import datetime
        
        # Date early bird
        early_deadline = fees_config.get('early_bird', {}).get('deadline', '2026-04-15')
        try:
            date_obj = datetime.strptime(early_deadline, '%Y-%m-%d')
            formatted_early_date = date_obj.strftime('%d %B %Y').replace('April', 'avril').replace('March', 'mars').replace('May', 'mai').replace('June', 'juin')
        except:
            formatted_early_date = '15 avril 2026'
        
        # Date regular (même date de référence)
        try:
            date_obj = datetime.strptime(early_deadline, '%Y-%m-%d')
            formatted_regular_date = date_obj.strftime('%d %B %Y').replace('April', 'avril').replace('March', 'mars').replace('May', 'mai').replace('June', 'juin')
        except:
            formatted_regular_date = '15 avril 2026'
        
        # Utiliser la configuration du fichier YAML
        fees = {
            'early': {
                'date': f"{formatted_early_date}",
                'student': fees_config.get('early_bird', {}).get('student', 310),
                'member_indiv': fees_config.get('early_bird', {}).get('member_individual', 400),
                'member_collec': fees_config.get('early_bird', {}).get('member_collective', 460),
                'not_member': fees_config.get('early_bird', {}).get('non_member', 510),
            },
            'regular': {
                'date': f"{formatted_regular_date}",
                'student': fees_config.get('regular', {}).get('student', 460),
                'member_indiv': fees_config.get('regular', {}).get('member_individual', 550),
                'member_collec': fees_config.get('regular', {}).get('member_collective', 610),
                'not_member': fees_config.get('regular', {}).get('non_member', 660),
            },
            'included': [
                fees_config.get('included', {}).get('included1'),
                fees_config.get('included', {}).get('included2'),
                fees_config.get('included', {}).get('included3'),
                fees_config.get('included', {}).get('included4'),
            ],
            'categories': {
                'student': fees_config.get('categories', {}).get('student'),
                'member_individual': fees_config.get('categories', {}).get('member_individual'),
                'member_collective': fees_config.get('categories', {}).get('member_collective'),
                'non_member': fees_config.get('categories', {}).get('non_member'),
            }, 
            
            'optional': [
                {
                    'item': fees_config.get('optional', {}).get('item'),
                    'price': fees_config.get('optional', {}).get('price')
                }
            ]
        }

        zones_status = {'inscription_is_open': False, 'inscription_message': 'Les inscriptions seront bientôt ouvertes.'}
    try:
        zones_file = Path(current_app.root_path) / 'static' / 'content' / 'zones.yml'
        if zones_file.exists():
            with open(zones_file, 'r', encoding='utf-8') as f:
                zones = yaml.safe_load(f)['zones']
                inscription_zone = zones.get('inscription', {})
                zones_status = {
                    'inscription_is_open': inscription_zone.get('is_open', False),
                    'inscription_message': inscription_zone.get('message', 'Les inscriptions seront bientôt ouvertes.')
                }
    except Exception as e:
        current_app.logger.error(f"Erreur lecture zones.yml dans inscription_conference: {e}")

    # Modifier le return render_template pour ajouter zones=zones_status :
    return render_template("conference/inscription_conference.html", 
                         fees=fees,
                         registration_urls=registration_urls,
                         zones=zones_status)

@conference.route("/communication-info")
def communication_info():
    """Affiche les informations générales sur les communications."""

    from flask import current_app as app
    try:
        zones_file = Path(app.root_path) / 'static' / 'content' / 'zones.yml'
        if zones_file.exists():
            with open(zones_file, 'r', encoding='utf-8') as f:
                zones = yaml.safe_load(f)['zones']
                submission_zone = zones.get('submission', {})
                if not submission_zone.get('is_open', False):
                    # Flash avec le message configuré dans zones.yml
                    message = submission_zone.get('message', 'Le dépôt de communications sera bientôt ouvert.')
                    flash(message, 'info')
    except Exception as e:
        current_app.logger.error(f"Erreur lecture zones.yml dans communication_info: {e}")
        # En cas d'erreur, pas de flash (on laisse la page normale)
        pass




    from flask import current_app
    import os
    
    # Récupérer les données depuis les configurations déjà chargées dans l'app
    conference_config = current_app.conference_config
    themes_config = current_app.themes_config
    
    # Extraire les informations pertinentes
    submissions_info = conference_config.get('submissions', {})
    dates_info = conference_config.get('dates', {})
    deadlines = dates_info.get('deadlines', {})
    
    # Convertir les types de soumission du YAML vers le format attendu par le template
    submission_types = submissions_info.get('types', [])
    formatted_types = []
    
    for sub_type in submission_types:
        formatted_type = {
            'name': sub_type.get('name', ''),
            'description': sub_type.get('description', ''),
            'deadline': None,
            'pages': None,
            'format': None
        }
        
        # Définir le format selon le type
        if sub_type.get('max_pages'):
            formatted_type['pages'] = f"{sub_type['max_pages']} pages max"
        elif sub_type.get('format'):
            formatted_type['format'] = sub_type['format']
            
        # Assigner les deadlines selon le type
        type_code = sub_type.get('code', '').lower()
        if type_code == 'article':
            if deadlines.get('article_submission'):
                formatted_type['deadline'] = _format_date(deadlines['article_submission'])
        elif type_code == 'wip':
            if deadlines.get('wip_submission'):
                formatted_type['deadline'] = _format_date(deadlines['wip_submission'])
        elif type_code == 'poster':
            if deadlines.get('wip_submission'):
                formatted_type['deadline'] = _format_date(deadlines['wip_submission'])
                
        # Deadline par défaut si pas trouvée
        if not formatted_type['deadline']:
            formatted_type['deadline'] = "À définir"
            
        formatted_types.append(formatted_type)
    
    # Trier les thématiques par ordre si disponible, sinon par nom
    sorted_themes = sorted(themes_config, key=lambda x: x.get('ordre', 999))
    # Filtrer seulement les thématiques actives
    active_themes = [theme for theme in sorted_themes if theme.get('actif', True)]
    
    # Nouveau : Lister les templates disponibles
    templates_dir = os.path.join(current_app.root_path, 'static', 'templates')
    available_templates = []
    
    if os.path.exists(templates_dir):
        for filename in os.listdir(templates_dir):
            if os.path.isfile(os.path.join(templates_dir, filename)):
                template_info = _get_template_info(filename)
                if template_info:
                    available_templates.append(template_info)
    
    # Trier les templates par type et langue
    available_templates.sort(key=lambda x: (x['type'], x['language']))
    
    # Préparer les données pour le template
    guidelines = {
        'types': formatted_types,
        'themes': active_themes,  # Utiliser les vraies thématiques avec toutes leurs propriétés
        'calendar': [],
        'abstract_info': {
            'deadline': _format_date(deadlines.get('abstract_submission', '2025-11-15')),
            'notification': _format_date(deadlines.get('abstract_notification', '2025-12-01')),
            'required_for_articles': True,
            'format': {
                'max_pages': 1,
                'file_format': 'Texte brut',
                'required_elements': [
                    'Titre et auteurs',
                    'Affiliations complètes', 
                    'Résumé structuré (objectifs, méthodes, résultats)',
                    'Mots-clés (3-5)'
                ]
            }
        }
    }
    
    # Construire le calendrier complet depuis les dates importantes
    deadline_mapping = [
        ('abstract_submission', 'Date limite soumission résumés'),
        ('abstract_notification', 'Notifications d\'acceptation des résumés'),
        ('article_submission', 'Date limite articles complets'),
        ('article_notification', 'Retour des expertises'),
        ('final_version', 'Dépôt des versions définitives'),
        ('wip_submission', 'Date limite posters/WIP')
    ]
    
    for deadline_key, event_name in deadline_mapping:
        if deadlines.get(deadline_key):
            guidelines['calendar'].append({
                'date': _format_date(deadlines[deadline_key]),
                'event': event_name
            })
    
    # Ajouter les dates de la conférence
    if dates_info.get('dates'):
        guidelines['calendar'].append({
            'date': dates_info['dates'], 
            'event': 'Conférence'
        })
    
    # Si le calendrier est vide, ajouter des données par défaut
    if not guidelines['calendar']:
        guidelines['calendar'] = [
            {'date': '15/11/2025', 'event': 'Date limite soumission résumés'},
            {'date': '01/12/2025', 'event': 'Notifications d\'acceptation des résumés'},
            {'date': '22/01/2026', 'event': 'Date limite articles complets'},
            {'date': '25/03/2026', 'event': 'Retour des expertises'},
            {'date': '10/04/2026', 'event': 'Dépôt des versions définitives'},
            {'date': '20/04/2026', 'event': 'Date limite posters/WIP'},
            {'date': '2-5 juin 2026', 'event': 'Conférence'}
        ]
    
    # Si pas de types définis, utiliser les types par défaut
    if not guidelines['types']:
        guidelines['types'] = [
            {
                'name': 'Article complet',
                'pages': '8 pages max',
                'deadline': _format_date(deadlines.get('article_submission', '2026-01-22')),
                'description': 'Travaux aboutis avec résultats complets (nécessite un résumé accepté)'
            },
            {
                'name': 'Work in Progress',
                'pages': '4 pages max', 
                'deadline': _format_date(deadlines.get('wip_submission', '2026-04-20')),
                'description': 'Travaux en cours avec résultats préliminaires'
            },
            {
                'name': 'Poster',
                'format': 'A0 portrait',
                'deadline': _format_date(deadlines.get('wip_submission', '2026-04-20')),
                'description': 'Présentation visuelle avec QR code'
            }
        ]
    
    return render_template("conference/communication_info.html", 
                         guidelines=guidelines,
                         available_templates=available_templates)

def _format_date(date_str):
    """Convertit une date YYYY-MM-DD en format français."""
    if not date_str:
        return "À définir"
    
    try:
        from datetime import datetime
        if isinstance(date_str, str) and len(date_str) == 10:  # Format YYYY-MM-DD
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d/%m/%Y')
        else:
            return str(date_str)
    except:
        return str(date_str)

def _get_template_info(filename):
    """Analyse un nom de fichier pour extraire les informations du template."""
    import os
    
    # Extensions supportées et leurs informations
    extension_info = {
        '.docx': {'icon': 'fas fa-file-word', 'color': 'primary', 'type_name': 'Word'},
        '.doc': {'icon': 'fas fa-file-word', 'color': 'primary', 'type_name': 'Word'},
        '.zip': {'icon': 'fas fa-file-archive', 'color': 'secondary', 'type_name': 'LaTeX'},
        '.tex': {'icon': 'fas fa-file-alt', 'color': 'secondary', 'type_name': 'LaTeX'},
        '.pptx': {'icon': 'fas fa-file-powerpoint', 'color': 'warning', 'type_name': 'PowerPoint'},
        '.ppt': {'icon': 'fas fa-file-powerpoint', 'color': 'warning', 'type_name': 'PowerPoint'}
    }
    
    # Obtenir l'extension
    name, ext = os.path.splitext(filename)
    ext_lower = ext.lower()
    
    if ext_lower not in extension_info:
        return None
    
    # Analyser le nom pour détecter la langue et le type
    name_lower = name.lower()
    
    # Détecter la langue
    if 'fr' in name_lower or 'french' in name_lower or 'francais' in name_lower:
        language = 'Français'
        lang_code = 'fr'
    elif 'en' in name_lower or 'english' in name_lower or 'us' in name_lower or 'anglais' in name_lower:
        language = 'English'
        lang_code = 'en'
    else:
        language = 'Multilingue'
        lang_code = 'multi'
    
    # Détecter le type de document
    if 'poster' in name_lower:
        doc_type = 'poster'
        type_display = 'Poster'
    elif 'article' in name_lower:
        doc_type = 'article'
        type_display = 'Article'
    elif 'resume' in name_lower or 'abstract' in name_lower:
        doc_type = 'resume'
        type_display = 'Résumé'
    elif 'latex' in name_lower or ext_lower == '.zip':
        doc_type = 'article'
        type_display = 'Article'
    else:
        doc_type = 'article'
        type_display = 'Article'
    
    return {
        'filename': filename,
        'display_name': f"{type_display} - {extension_info[ext_lower]['type_name']} ({language})",
        'icon': extension_info[ext_lower]['icon'],
        'color': extension_info[ext_lower]['color'],
        'type': doc_type,
        'language': language,
        'lang_code': lang_code,
        'download_url': f"/static/templates/{filename}",
        'file_size': _get_file_size(os.path.join('app/static/templates', filename))
    }

def _get_file_size(filepath):
    """Retourne la taille du fichier en format lisible."""
    try:
        size = os.path.getsize(filepath)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except:
        return "N/A"


@conference.route("/contact", methods=["GET", "POST"])
def contact():
    """Page de contact."""
    from flask import current_app
    
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")
        contact_type = request.form.get("contact_type")  # ← AJOUT
        
        # Valider les champs
        if not all([name, email, subject, message]):
            flash("Tous les champs sont obligatoires.", "danger")
            return redirect(url_for("conference.contact"))
        
        try:
            # Récupérer la configuration des contacts
            conference_config = current_app.conference_config
            contacts_config = conference_config.get('contacts', {})
            conference_info = conference_config.get('conference', {})
            
            # Déterminer l'email de destination selon le type de contact
            default_contact = contacts_config.get('general', {})
            recipient_email = default_contact.get('email', 'congres-sft2026@univ-lorraine.fr')
            recipient_name = f"Équipe {conference_info.get('short_name', 'SFT 2026')}"

            
            if contact_type and contact_type in contacts_config:
                contact_data = contacts_config[contact_type]
                
                # Pour le programme (présidents), chercher l'email dans les présidents
                if contact_type == 'program':
                    presidents = conference_info.get('presidents', [])
                    if presidents and presidents[0].get('email'):
                        recipient_email = presidents[0]['email']
                        recipient_name = presidents[0].get('name', 'Président du programme')
                    elif contact_data.get('email'):
                        recipient_email = contact_data['email']
                        recipient_name = contact_data.get('person', 'Programme scientifique')
                else:
                    # Pour les autres contacts, utiliser directement l'email du contact
                    if contact_data.get('email'):
                        recipient_email = contact_data['email']
                        recipient_name = contact_data.get('person', contact_data.get('title', 'Contact'))
            
            
            # Utiliser la fonction send_email existante
            congress_name = conference_info.get('name', 'SFT 2026')
            congress_short_name = conference_info.get('short_name', 'SFT 2026')
            email_subject = f"[Contact {congress_short_name}] {subject}"
            email_body = f"""
Nouveau message reçu depuis le formulaire de contact :

Destinataire : {recipient_name}
Type de contact : {contact_type or 'Général'}
Nom : {name}
Email : {email}
Sujet : {subject}

Message :
{message}

---
Envoyé depuis le site {congress_name} ({congress_short_name})
Répondre à : {email}
"""

            
            # Envoyer avec la fonction existante
            current_app.send_email(email_subject, [recipient_email], email_body)
            flash(f"Votre message a été envoyé avec succès à {recipient_name} ({recipient_email}).", "success")
            
        except Exception as e:
            current_app.logger.error(f"Erreur envoi email contact: {str(e)}")
            flash("Erreur lors de l'envoi du message. Veuillez réessayer.", "danger")
        
        return redirect(url_for("conference.contact"))
    
    # Récupérer les contacts depuis conference.yml
    conference_config = current_app.conference_config
    contacts_config = conference_config.get('contacts', {})
    conference_info = conference_config.get('conference', {})
    
    # Restructurer les contacts pour le template
    contacts = {}
    
    # Mapping des clés entre conference.yml et le format attendu par le template
    contact_mapping = {
        'general': 'general',
        'program': 'program',
        'submissions': 'submissions',
        'communication': 'communication'
    }
    
    for template_key, config_key in contact_mapping.items():
        if config_key in contacts_config:
            contact_data = contacts_config[config_key]
            
            # Traitement spécial pour le programme scientifique (présidents)
            if template_key == 'program':
                presidents = conference_info.get('presidents', [])
                
                # Si on a des présidents, on les utilise directement
                if presidents:
                    # Vérifier si on a des emails dans les présidents
                    presidents_with_emails = []
                    for president in presidents:
                        president_copy = president.copy()
                        # Si pas d'email dans president, essayer de le récupérer depuis contact_data
                        if not president_copy.get('email') and contact_data.get('email'):
                            current_app.logger.info(f"DEBUG - Ajout email de fallback pour {president.get('name')}: {contact_data.get('email')}")
                            president_copy['email'] = contact_data.get('email')
                        presidents_with_emails.append(president_copy)
                    
                    contacts[template_key] = {
                        'title': contact_data.get('title', ''),
                        'description': contact_data.get('description', ''),
                        'presidents': presidents_with_emails,
                        'has_presidents': True
                    }
                else:
                    # Fallback sur les données contact classiques
                    contacts[template_key] = {
                        'title': contact_data.get('title', ''),
                        'email': contact_data.get('email', ''),
                        'phone': contact_data.get('phone', ''),
                        'person': contact_data.get('person', ''),
                        'description': contact_data.get('description', ''),
                        'has_presidents': False
                    }
            else:
                contacts[template_key] = {
                    'title': contact_data.get('title', ''),
                    'email': contact_data.get('email', ''),
                    'phone': contact_data.get('phone', ''),
                    'person': contact_data.get('person', ''),
                    'description': contact_data.get('description', '')
                }
    
    return render_template("conference/contact.html", contacts=contacts)
