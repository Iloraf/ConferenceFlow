# app/conference_routes.py
from flask import Blueprint, render_template_string, render_template, send_file, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime
import csv
import os
from collections import defaultdict
from io import BytesIO
import tempfile

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

conference = Blueprint("conference", __name__)

#####   test email ####

@conference.route("/test-email")
@login_required
def test_email():
    print("📩 Route /test-email atteinte")
    try:
        from app.utils.email_utils import send_email

        #recipients = ["olivier@olivier-farges.xyz"]
        recipients = ["farges.olivier@gmail.com"]
        print(f"👤 Envoi vers: {recipients}")

        send_email(
            subject="Test SFT",
            recipients=recipients,
            body="Test d'email via le SMTP universitaire",
            html="<p><strong>Test</strong> depuis Flask</p>"
        )
        flash("✅ Email envoyé", "success")
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"❌ Échec de l'envoi: {e}", "danger")

    return redirect(url_for("conference.contact"))

###########################

def load_programme_csv_common():
    """Fonction commune pour charger le programme depuis le CSV avec gestion du temps."""
    csv_path = os.path.join(current_app.root_path, '..', 'config', 'programme.csv')
    
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
    
    # Template HTML intégré
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
        <div class="subtitle">34ème Congrès Français de Thermique</div>
        <div class="subtitle">Villers-lès-Nancy, 2-5 juin 2026</div>
        <div class="subtitle">« Thermique & Décarbonation de l'industrie »</div>
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
        34ème Congrès Français de Thermique - SFT 2026<br>
        Domaine de l'Asnée - Villers-lès-Nancy<br>
        Contact : programme@congres-sft2026.fr
    </div>
</body>
</html>
    """
    
    try:
        # Rendu du template HTML
        rendered_html = render_template_string(html_template, programme=programme_data)
        
        # Génération du PDF
        html_doc = HTML(string=rendered_html)
        pdf_buffer = BytesIO()
        html_doc.write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        
        # Création d'un fichier temporaire pour servir le PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_buffer.getvalue())
            tmp_file_path = tmp_file.name
        
        # Retour du fichier PDF
        return send_file(
            tmp_file_path,
            as_attachment=True,
            download_name='Programme_SFT_2026.pdf',
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
    venues = {
        'main': {
            'name': 'Domaine de l\'Asnée',
            'address': '11 Rue de Laxou, 54600 Villers-lès-Nancy',
            'description': 'Lieu principal de la conférence',
            'lat': 48.674,
            'lng': 6.1430,
            'image': 'images/domaine_asnee.png'
        },
        'hotels': [
            {
                'name': 'Grand Hôtel de la Reine',
                'stars': 4,
                'address': '2 Place Stanislas, 54000 Nancy',
                'distance': '500m du centre de congrès',
                'price': 'À partir de 120€/nuit'
            },
            {
                'name': 'Mercure Nancy Centre',
                'stars': 4,
                'address': '5 Rue des Carmes, 54000 Nancy',
                'distance': '800m du centre de congrès',
                'price': 'À partir de 95€/nuit'
            },
            {
                'name': 'Ibis Nancy Centre',
                'stars': 3,
                'address': '3 Rue Crampel, 54000 Nancy',
                'distance': '1km du centre de congrès',
                'price': 'À partir de 75€/nuit'
            }
        ],
        'transport': {
            'train': {
                'title': 'En train',
                'info': 'Gare de Nancy à 15 min en bus du centre de congrès. TGV direct depuis Paris (1h30).'
            },
            'car': {
                'title': 'En voiture',
                'info': 'A31 sortie« Nancy-Centre/Laxou » '
            },
            'plane': {
                'title': 'En avion',
                'info': 'Aéroport Metz-Nancy-Lorraine (45 min). Navette toutes les heures.'
            },
            'local': {
                'title': 'Transports locaux',
                'info': 'Bus ligne 15 - Arrêt "Laxou Les Provines" \n Bus ligne 13 - Arrêt "Domaine de l\'Asnée"'
            }
        }
    }
    return render_template("conference/localisation.html", venues=venues)


# Fonction organisation() complète pour conference_routes.py
# À remplacer dans le fichier app/conference_routes.py

@conference.route("/organisation")
def organisation():
    """Affiche les informations sur l'organisation."""
    
    def load_csv_data(filename):
        """Charge les données depuis un fichier CSV."""
        csv_path = os.path.join(current_app.root_path, '..', 'config', filename)

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



# Route Inscription conférence (différent de l'inscription utilisateur)
@conference.route("/inscription-conference")
def inscription_conference():
    """Affiche les informations d'inscription à la conférence."""
    fees = {
        'early': {
            'date': 'Avant le 15 avril 2026',
            'student': 310,
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
    return render_template("conference/inscription_conference.html", fees=fees)

# Route Communication (présentation générale, différent de "mes communications")
@conference.route("/communication-info")
def communication_info():
    """Affiche les informations générales sur les communications."""
    guidelines = {
        'types': [
            {
                'name': 'Article complet',
                'pages': '6-8 pages',
                'deadline': '15 mai 2026',
                'description': 'Travaux aboutis avec résultats complets'
            },
            {
                'name': 'Work in Progress',
                'pages': '2-4 pages',
                'deadline': '15 mai 2026',
                'description': 'Travaux en cours avec résultats préliminaires'
            },
            {
                'name': 'Poster',
                'format': 'A0 portrait',
                'deadline': '20 mai 2026',
                'description': 'Présentation visuelle avec QR code'
            }
        ],
        'themes': [
            'Conduction, convection, rayonnement',
            'Changement de phase et transferts multiphasiques',
            'Transferts en milieux poreux',
            'Micro et nanothermique',
            'Thermique du vivant',
            'Énergétique des systèmes',
            'Combustion et flammes',
            'Machines thermiques et frigorifiques',
            'Échangeurs de chaleur',
            'Stockage thermique',
            'Énergies renouvelables',
            'Thermique du bâtiment',
            'Thermique industrielle',
            'Métrologie et techniques inverses',
            'Modélisation et simulation numérique'
        ],
        'calendar': [
            {'date': '1er novembre 2025', 'event': 'Ouverture des soumissions'},
            {'date': '21 novembre 2025', 'event': 'Date limite soumission résumés'},
            {'date': '1er décembre 2025', 'event': 'Notifications d\'acceptation'},
            {'date': '31 janvier 2026', 'event': 'Date limite articles complets'},
            {'date': '25 mars 2026', 'event': 'Retour des expertises'},
            {'date': '10 avril 2026', 'event': 'Dépot des versions définitives'},
            {'date': '30 mai 2026', 'event': 'Date limite posters pour dépot sur HAL automatisé'},
            {'date': '2-5 juin 2026', 'event': 'Conférence'}
        ]
    }
    return render_template("conference/communication_info.html", guidelines=guidelines)

# Route Contact
@conference.route("/contact", methods=["GET", "POST"])
def contact():
    """Page de contact."""
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")
        
        # Ici vous pourriez envoyer un email
        flash("Votre message a été envoyé avec succès.", "success")
        return redirect(url_for("conference.contact"))
    
    contacts = {
        'general': {
            'title': 'Contact général',
            'email': 'congres-sft2026@univ-lorraine.fr',
            'phone': '+33 3 83 00 00 00'
        },
        'scientific': {
            'title': 'Questions scientifiques',
            'email': 'michel.gradeck@univ-lorraine.fr',
            'person': 'Michel Gradeck'
        },
        'registration': {
            'title': 'Inscriptions',
            'email': 'vincent.schick@univ-lorraine.fr',
            'person': 'Vincent Schick'
        },
        'communication': {
            'title': 'Communication',
            'email': 'olivier.farges@univ-lorraine.fr',
            'person': 'Olivier Farges'
        }
    }
    return render_template("conference/contact.html", contacts=contacts)

