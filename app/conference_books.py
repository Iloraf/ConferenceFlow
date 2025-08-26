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

from flask import Blueprint, render_template, send_file, current_app, abort
from flask_login import login_required, current_user
from collections import defaultdict, OrderedDict
from datetime import datetime
import tempfile
import os
from io import BytesIO

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

try:
    from PyPDF2 import PdfWriter, PdfReader
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import gray
    PDF_TOOLS_AVAILABLE = True
except ImportError:
    PDF_TOOLS_AVAILABLE = False

from .models import Communication, CommunicationStatus, ThematiqueHelper, SubmissionFile

books = Blueprint("books", __name__)


@books.route('/')
@login_required
def manage_books():
    """Page d'administration pour la génération des livres."""
    if not current_user.is_admin:
        abort(403)
    
    # Statistiques pour la page
    communications = get_communications_by_type_and_status()
    
    # Calcul de la répartition pour les tomes
    tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
    
    stats = {
        'articles_acceptes': len(communications['articles_acceptes']),
        'tome1_articles': sum(len(comms) for comms in tomes_split['tome1'].values()),
        'tome2_articles': sum(len(comms) for comms in tomes_split['tome2'].values()),
        'resumes': len(communications['resumes']),
        'wips': len(communications['wips']),
        'thematiques_tome1': len(tomes_split['tome1']),
        'thematiques_tome2': len(tomes_split['tome2']),
        'thematiques_resumes': len(group_communications_by_thematique(communications['resumes'])),
        'thematiques_wips': len(group_communications_by_thematique(communications['wips']))
    }
    
    return render_template('admin/manage_books.html', 
                         stats=stats, 
                         weasyprint_available=WEASYPRINT_AVAILABLE,
                         pdf_tools_available=PDF_TOOLS_AVAILABLE)


def get_communications_by_type_and_status():
    """Récupère les communications groupées par type et statut."""
    
    # Articles acceptés pour les tomes 1 et 2
    articles_acceptes = Communication.query.filter(
        Communication.type == 'article',
        Communication.status == CommunicationStatus.ACCEPTE
    ).order_by(Communication.title).all()
    
    # Résumés pour le livre des résumés (articles avec résumé soumis)
    resumes = Communication.query.filter(
        Communication.type == 'article',
        Communication.status.in_([
            CommunicationStatus.RESUME_SOUMIS,
            CommunicationStatus.ARTICLE_SOUMIS,
            CommunicationStatus.EN_REVIEW,
            CommunicationStatus.ACCEPTE
        ])
    ).order_by(Communication.title).all()
    
    # Work in Progress
    wips = Communication.query.filter(
        Communication.type == 'wip',
        Communication.status == CommunicationStatus.WIP_SOUMIS
    ).order_by(Communication.title).all()
    
    return {
        'articles_acceptes': articles_acceptes,
        'resumes': resumes,
        'wips': wips
    }


def group_communications_by_thematique(communications):
    """Groupe les communications par thématique."""
    thematiques_groups = defaultdict(list)
    
    for comm in communications:
        if comm.thematiques_codes:
            # Prendre la première thématique comme thématique principale
            codes = [code.strip() for code in comm.thematiques_codes.split(',') if code.strip()]
            if codes:
                primary_code = codes[0]
                thematique = ThematiqueHelper.get_by_code(primary_code)
                if thematique:
                    thematique_key = thematique['nom']  # Juste le nom, pas le code
                    thematiques_groups[thematique_key].append(comm)
                else:
                    thematiques_groups['Autres'].append(comm)
            else:
                thematiques_groups['Autres'].append(comm)
        else:
            thematiques_groups['Autres'].append(comm)
    
    # Trier les thématiques par ordre alphabétique
    return OrderedDict(sorted(thematiques_groups.items()))


def split_articles_for_tomes(articles_acceptes, max_per_tome=30):
    """Divise les articles en 2 tomes de manière équilibrée."""
    
    # Grouper par thématique d'abord
    thematiques_groups = group_communications_by_thematique(articles_acceptes)
    
    tome1_articles = []
    tome2_articles = []
    tome1_count = 0
    tome2_count = 0
    
    # Alterner les thématiques entre les deux tomes
    for i, (thematique, articles) in enumerate(thematiques_groups.items()):
        if i % 2 == 0:  # Thématiques paires au tome 1
            tome1_articles.extend(articles)
            tome1_count += len(articles)
        else:  # Thématiques impaires au tome 2
            tome2_articles.extend(articles)
            tome2_count += len(articles)
    
    return {
        'tome1': group_communications_by_thematique(tome1_articles),
        'tome2': group_communications_by_thematique(tome2_articles)
    }


def generate_author_index(communications, page_mapping):
    """Génère l'index des auteurs avec numéros de pages."""
    
    authors_index = defaultdict(set)
    
    for comm in communications:
        if comm.id in page_mapping:
            page_num = page_mapping[comm.id]
            for author in comm.authors:
                first_name = (author.first_name or '').strip()
                last_name = (author.last_name or '').strip()
                
                if last_name and first_name:
                    author_name = f"{last_name} {first_name}"
                elif last_name:
                    author_name = last_name
                elif first_name:
                    author_name = first_name
                else:
                    author_name = author.email or "Auteur inconnu"
                
                authors_index[author_name].add(page_num)
    
    # Convertir les sets en listes triées et trier par nom
    sorted_authors = OrderedDict()
    for name in sorted(authors_index.keys()):
        sorted_authors[name] = sorted(list(authors_index[name]))
    
    return sorted_authors


def get_conference_config():
    """Charge la configuration de la conférence."""
    try:
        from .config_loader import ConfigLoader
        config_loader = ConfigLoader()
        return config_loader.load_conference_config()
    except Exception as e:
        current_app.logger.error(f"Erreur chargement config: {e}")
        # Configuration par défaut basée sur le style SFT
        return {
            'conference': {
                'name': 'Congrès Conference Flow',
                'short_name': 'CF',
                'theme': 'Gestion d\'une conférence',
                'organizing_lab': {
                    'short_name': 'CF',
                    'description': 'Conference Flow'
                }
            },
            'dates': {'dates': '20 juillet 2026'},
            'location': {'city': 'Nancy'}
        }


def get_book_css():
    """CSS reproduisant exactement le style LaTeX SFT de référence."""
    return """
    /* === CONFIGURATION DE PAGE === */
    @page {
        size: A4;
        margin: 1.5cm 1.8cm 1.5cm 1.8cm;  /* Marges exactes du LaTeX */
        
        @top-center {
            content: string(page-header);
            font-family: "Helvetica", Arial, sans-serif;
            font-size: 9pt;
            border-bottom: 0.5pt solid #000;
            padding-bottom: 3pt;
            margin-bottom: 10pt;
        }
        
        @bottom-center {
            content: counter(page);
            font-family: "Helvetica", Arial, sans-serif;
            font-size: 10pt;
        }
    }
    
    @page cover {
        margin: 0;
        @top-center { content: none; }
        @bottom-center { content: none; }
    }
    
    @page toc {
        @bottom-center { 
            content: counter(page, lower-roman);
            font-family: "Helvetica", Arial, sans-serif;
            font-size: 10pt;
        }
    }
    
    /* === TYPOGRAPHIE EXACTE DU LATEX === */
    body {
        font-family: "Helvetica", Arial, sans-serif;  /* Sans-serif comme dans LaTeX */
        font-size: 11pt;
        line-height: 1.2;
        color: #000;
        margin: 0;
        padding: 0;
    }
    
    /* Paragraphes avec indentation et espacement du LaTeX */
    p {
        margin: 0;
        padding: 0;
        text-indent: 10mm;  /* \parindent{10mm} */
        margin-bottom: 2mm; /* \parskip{2mm} */
        text-align: justify;
    }
    
    /* Pas d'indentation pour le premier paragraphe */
    p:first-child, .no-indent {
        text-indent: 0;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: "Helvetica", Arial, sans-serif;
        color: #000;
        margin: 0;
        padding: 0;
        font-weight: bold;
        text-indent: 0;  /* Pas d'indentation pour les titres */
    }
    
    /* === PAGE DE COUVERTURE STYLE SFT === */
    .cover-page {
        page: cover;
        height: 100vh;
        background: white;
        color: black;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        font-family: "Helvetica", Arial, sans-serif;
        page-break-after: always;
    }
    
    .cover-theme-line {
        font-size: 18pt;  /* \LARGE */
        font-weight: normal;
        margin-bottom: 1em;
        text-transform: uppercase;
        letter-spacing: 0.5pt;
    }
    
    .cover-authors {
        font-size: 12pt;  /* \normalsize */
        font-weight: normal;
        margin-bottom: 3em;
        line-height: 1.3;
    }
    
    .cover-actes {
        font-size: 24pt;  /* \Huge */
        font-weight: bold;
        margin-bottom: 1em;
        text-transform: uppercase;
    }
    
    .cover-du {
        font-size: 12pt;
        margin-bottom: 1em;
    }
    
    .cover-congres-title {
        font-size: 24pt;  /* \Huge */
        font-weight: normal;
        margin-bottom: 2em;
        line-height: 1.2;
    }
    
    .cover-event-code {
        font-size: 24pt;  /* \Huge */
        font-weight: bold;
        margin-bottom: 2em;
    }
    
    .cover-dates {
        font-size: 14pt;  /* \Large */
        font-weight: normal;
        margin-bottom: 0.5em;
    }
    
    .cover-location {
        font-size: 14pt;  /* \Large */
        font-weight: normal;
        margin-bottom: 2em;
    }
    
    .cover-organise {
        font-size: 14pt;  /* \Large */
        font-weight: normal;
        margin-bottom: 1em;
    }
    
    .cover-organizer {
        font-size: 12pt;  /* \normalsize */
        font-weight: normal;
        margin-bottom: 0.5em;
        line-height: 1.3;
    }
    
    /* === SECTIONS PRINCIPALES === */
    .part-page {
        page-break-before: always;
        page-break-after: always;
        text-align: center;
        padding-top: 40%;
    }
    
    .part-title {
        font-size: 18pt;
        font-weight: bold;
        margin-bottom: 1em;
        text-indent: 0;
    }
    
    /* === APERÇU WEB === */
    @media screen {
        body { 
            background: #f5f5f5; 
            padding: 20px; 
        }
        
        .cover-page, .part-page {
            background: white;
            padding: 40px;
            margin-bottom: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            min-height: 80vh;
        }
        
        /* En mode web, on désactive l'indentation pour la lisibilité */
        p {
            text-indent: 0;
            margin-bottom: 1em;
        }
    }
    """


def generate_dynamic_header(config):
    """Génère l'en-tête dynamiquement à partir de conference.yml."""
    
    # Extraire les informations de la configuration
    conference_info = config.get('conference', {})
    location_info = config.get('location', {})
    dates_info = config.get('dates', {})
    
    # Construction intelligente du nom de série/congrès
    series_name = "Congrès Français de Thermique"  # Nom de base
    
    # Si on a des infos sur la série dans la config
    if 'series' in conference_info:
        series_name = conference_info['series']
    elif 'full_name' in conference_info:
        # Utiliser le nom complet s'il contient "Congrès"
        if "Congrès" in conference_info['full_name']:
            series_name = conference_info['full_name']
    
    # Nom court de la conférence (ex: SFT 2026)
    short_name = conference_info.get('short_name', 'Conference Flow')
    
    # Ville
    city = location_info.get('city', 'Nancy')
    
    # Dates - essayer plusieurs formats possibles dans conference.yml
    dates = None
    
    # Priorité 1: dates.conference.dates (format texte)
    if dates_info.get('conference', {}).get('dates'):
        dates = dates_info['conference']['dates']
    
    # Priorité 2: dates.dates (format global)
    elif dates_info.get('dates'):
        dates = dates_info['dates']
    
    # Priorité 3: construire depuis start/end si disponible
    elif dates_info.get('conference', {}).get('start') and dates_info.get('conference', {}).get('end'):
        start_date = dates_info['conference']['start']
        end_date = dates_info['conference']['end']
        
        # Parser les dates si elles sont en format YYYY-MM-DD
        try:
            from datetime import datetime
            start_obj = datetime.strptime(start_date, '%Y-%m-%d')
            end_obj = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Formatter en français
            months_fr = {
                1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril', 5: 'mai', 6: 'juin',
                7: 'juillet', 8: 'août', 9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
            }
            
            if start_obj.month == end_obj.month:
                # Même mois : "2 -- 5 juin 2026"
                dates = f"{start_obj.day} -- {end_obj.day} {months_fr[start_obj.month]} {start_obj.year}"
            else:
                # Mois différents : "30 juin -- 3 juillet 2026"
                dates = f"{start_obj.day} {months_fr[start_obj.month]} -- {end_obj.day} {months_fr[end_obj.month]} {start_obj.year}"
                
        except (ValueError, KeyError):
            # Si le parsing échoue, utiliser les valeurs brutes
            dates = f"{start_date} -- {end_date}"
    
    # Valeur par défaut
    if not dates:
        dates = "20 juillet 2026"
    
    # Gestion spéciale pour "1er" si les dates commencent par "1 "
    if dates.startswith('1 '):
        dates = '1er' + dates[1:]
    
    # Construction finale de l'en-tête
    header = f"{series_name} {short_name}, {city}, {dates}"
    
    return header


def get_communication_pdf(communication, book_type):
    """Récupère le chemin du fichier PDF d'une communication selon le type de livre."""
    try:
        # Définir le type de fichier selon le type de livre
        if book_type == 'article':
            # Pour les tomes d'articles complets
            target_file = communication.files.filter_by(file_type='article').first()
        elif book_type == 'resume':
            # Pour les résumés et WIP
            if communication.type == 'wip':
                target_file = communication.files.filter_by(file_type='wip').first()
            else:
                target_file = communication.files.filter_by(file_type='résumé').first()
        else:
            target_file = None
        
        if target_file and target_file.file_path:
            # Construire le chemin complet vers le fichier
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], target_file.file_path)
            
            # Vérifier que le fichier existe
            if os.path.exists(full_path):
                return full_path
            else:
                current_app.logger.warning(f"Fichier PDF introuvable: {full_path}")
                return None
        
        return None
        
    except Exception as e:
        current_app.logger.error(f"Erreur récupération PDF pour communication {communication.id}: {e}")
        return None


def calculate_page_numbers(communications_by_theme):
    """Calcule le mapping des numéros de pages pour chaque communication."""
    page_mapping = {}
    
    # Pages de garde et TOC (estimé)
    current_page = 5  # Après couverture, page blanche, TOC
    
    for theme_name, communications in communications_by_theme.items():
        # Page de titre thématique
        current_page += 1
        
        for comm in communications:
            page_mapping[comm.id] = current_page
            
            # Estimer le nombre de pages du PDF
            pdf_path = get_communication_pdf(comm, 'article' if comm.type == 'article' else 'resume')
            if pdf_path and os.path.exists(pdf_path):
                try:
                    reader = PdfReader(pdf_path)
                    nb_pages = len(reader.pages)
                except:
                    nb_pages = 8  # Estimation par défaut
            else:
                nb_pages = 1  # Page placeholder
            
            current_page += nb_pages
    
    return page_mapping


def generate_complete_book_pdf(title, communications_by_theme, authors_index, book_type):
    """Génère un livre PDF complet avec TOC, agrégation PDF, index et numérotation."""
    if not PDF_TOOLS_AVAILABLE:
        raise Exception("PyPDF2 et reportlab requis pour l'agrégation PDF: pip install PyPDF2 reportlab")
    
    try:
        # 1. CALCUL DU MAPPING DES PAGES
        page_mapping = calculate_page_numbers(communications_by_theme)
        
        # 2. GÉNÉRATION DES PARTIES HTML (couverture, TOC, index)
        html_parts = generate_book_html_parts(title, communications_by_theme, authors_index, page_mapping, book_type)
        
        # 3. ASSEMBLAGE FINAL
        pdf_writer = PdfWriter()
        current_page = 1
        
        # A. Page de garde (pas de numérotation)
        cover_pdf = html_to_pdf(html_parts['cover'])
        cover_reader = PdfReader(BytesIO(cover_pdf))
        for page in cover_reader.pages:
            pdf_writer.add_page(page)
        current_page += len(cover_reader.pages)
        
        # B. TOC (numérotation romaine)
        toc_pdf = html_to_pdf(html_parts['toc'])
        toc_reader = PdfReader(BytesIO(toc_pdf))
        for i, page in enumerate(toc_reader.pages):
            numbered_page = add_page_number(page, current_page + i, format='roman')
            pdf_writer.add_page(numbered_page)
        current_page += len(toc_reader.pages)
        
        # C. COMMUNICATIONS PAR THÉMATIQUE (numérotation arabe)
        for theme_name, communications in communications_by_theme.items():
            # Page de séparateur thématique
            theme_page_pdf = generate_theme_separator_pdf(theme_name)
            theme_reader = PdfReader(BytesIO(theme_page_pdf))
            for page in theme_reader.pages:
                numbered_page = add_page_number(page, current_page, format='arabic')
                pdf_writer.add_page(numbered_page)
                current_page += 1
            
            # PDF des communications
            for comm in communications:
                comm_pdf_path = get_communication_pdf(comm, book_type)
                
                if comm_pdf_path and os.path.exists(comm_pdf_path):
                    comm_reader = PdfReader(comm_pdf_path)
                    
                    for page_num, page in enumerate(comm_reader.pages):
                        # Appliquer le filigrane WIP si nécessaire
                        if book_type == 'resume' and comm.type == 'wip':
                            page = add_wip_watermark(page)
                        
                        # Ajouter numérotation
                        numbered_page = add_page_number(page, current_page, format='arabic')
                        pdf_writer.add_page(numbered_page)
                        current_page += 1
                else:
                    # Page placeholder si PDF manquant
                    placeholder_pdf = generate_placeholder_pdf(comm)
                    placeholder_reader = PdfReader(BytesIO(placeholder_pdf))
                    for page in placeholder_reader.pages:
                        numbered_page = add_page_number(page, current_page, format='arabic')
                        pdf_writer.add_page(numbered_page)
                        current_page += 1
        
        # D. INDEX DES AUTEURS (continuation numérotation arabe)
        index_pdf = html_to_pdf(html_parts['index'])
        index_reader = PdfReader(BytesIO(index_pdf))
        for page in index_reader.pages:
            numbered_page = add_page_number(page, current_page, format='arabic')
            pdf_writer.add_page(numbered_page)
            current_page += 1
        
        # 4. FINALISATION
        final_buffer = BytesIO()
        pdf_writer.write(final_buffer)
        final_buffer.seek(0)
        
        return final_buffer.getvalue()
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération livre PDF: {e}")
        raise


def add_page_number(page, number, format='arabic'):
    """Ajoute un numéro de page à une page PDF."""
    # Créer une page avec le numéro
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    
    # Position du numéro de page (centré en bas)
    width, height = A4
    
    if format == 'roman':
        page_text = int_to_roman(number)
    else:
        page_text = str(number)
    
    can.drawCentredString(width/2, 30, page_text)
    can.save()
    
    # Fusionner avec la page originale
    packet.seek(0)
    number_pdf = PdfReader(packet)
    page.merge_page(number_pdf.pages[0])
    
    return page


def add_wip_watermark(page):
    """Ajoute un filigrane 'Work in Progress' à une page."""
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    
    # Configurer le filigrane
    can.setFillColor(gray, alpha=0.3)
    can.setFont("Helvetica-Bold", 48)
    
    # Position et rotation
    width, height = A4
    can.saveState()
    can.translate(width/2, height/2)
    can.rotate(45)
    can.drawCentredString(0, 0, "Work in Progress")
    can.restoreState()
    can.save()
    
    # Appliquer le filigrane
    packet.seek(0)
    watermark_pdf = PdfReader(packet)
    page.merge_page(watermark_pdf.pages[0])
    
    return page


def int_to_roman(num):
    """Convertit un entier en chiffres romains."""
    values = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    literals = ['M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL', 'X', 'IX', 'V', 'IV', 'I']
    
    result = ''
    for i in range(len(values)):
        count = num // values[i]
        result += literals[i] * count
        num -= values[i] * count
    
    return result.lower()


def html_to_pdf(html_content):
    """Convertit du HTML en PDF."""
    html_doc = HTML(string=html_content)
    buffer = BytesIO()
    html_doc.write_pdf(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def generate_book_html_parts(title, communications_by_theme, authors_index, page_mapping, book_type):
    """Génère les parties HTML du livre (couverture, TOC, index)."""
    config = get_conference_config()
    
    parts = {}
    
    # COUVERTURE
    parts['cover'] = generate_cover_only_html(title, config)
    
    # TABLE DES MATIÈRES
    parts['toc'] = generate_toc_html(communications_by_theme, page_mapping)
    
    # INDEX DES AUTEURS
    parts['index'] = generate_index_html(authors_index)
    
    return parts


def generate_cover_only_html(title, config):
    """Page de garde uniquement."""
    header_text = generate_dynamic_header(config)
    presidents_names = get_presidents_names(config)
    livre_titre, livre_type = get_book_title_type(title)
    
    return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>{get_book_css()}</style>
</head>
<body>
    <div class="cover-page">
        <div class="cover-theme-line">{config['conference']['theme'].upper()}</div>
        <div style="flex: 1;"></div>
        <div class="cover-authors">{presidents_names}</div>
        <div style="flex: 1;"></div>
        <div class="cover-actes">{livre_titre}</div>
        <div class="cover-du">{livre_type}</div>
        <div class="cover-congres-title">
            CONGRÈS ANNUEL DE LA<br>
            SOCIÉTÉ FRANÇAISE DE THERMIQUE
        </div>
        <div style="flex: 1;"></div>
        <div class="cover-event-code">{config['conference']['short_name']}</div>
        <div style="flex: 1;"></div>
        <div class="cover-dates">{config.get('dates', {}).get('dates', '20 juillet 2026')}</div>
        <div class="cover-location">{config['location']['city']}</div>
        <div style="flex: 1;"></div>
        <div class="cover-organise">ORGANISÉ PAR</div>
        <div class="cover-organizer">
            {config['conference']['organizing_lab']['description']}<br>
            {config['conference']['organizing_lab']['short_name']}<br>
            {config['location']['city'].upper()}
        </div>
    </div>
</body>
</html>
"""


def generate_toc_html(communications_by_theme, page_mapping):
    """Table des matières."""
    toc_entries = ""
    theme_num = 1
    
    for theme_name, communications in communications_by_theme.items():
        if communications:
            first_page = page_mapping.get(communications[0].id, '???')
            
            toc_entries += f"""
            <div class="toc-entry">
                <span>Thème {theme_num} - {theme_name}</span>
                <div class="toc-dots"></div>
                <span class="toc-page-num">{first_page}</span>
            </div>
            """
            
            # Ajouter quelques communications principales
            for comm in communications[:3]:
                page_num = page_mapping.get(comm.id, '???')
                title_short = comm.title[:60] + ('...' if len(comm.title) > 60 else '')
                
                toc_entries += f"""
                <div class="toc-entry" style="margin-left: 1em; font-size: 10pt;">
                    <span>{title_short}</span>
                    <div class="toc-dots"></div>
                    <span class="toc-page-num">{page_num}</span>
                </div>
                """
        
        theme_num += 1

    return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Table des matières</title>
    <style>
    @page {{
        margin: 1.5cm 1.8cm 1.5cm 1.8cm;
        @bottom-center {{ content: none; }}
    }}
    body {{
        font-family: "Helvetica", Arial, sans-serif;
        font-size: 11pt;
        color: #000;
        margin: 0;
        padding: 0;
    }}
    .toc-title {{
        text-align: center;
        font-size: 16pt;
        font-weight: bold;
        margin-bottom: 2em;
        border-bottom: 0.5pt solid #000;
        padding-bottom: 0.5em;
    }}
    .toc-entry {{
        margin-bottom: 0.3em;
        display: flex;
        justify-content: space-between;
        align-items: baseline;
    }}
    .toc-dots {{
        flex-grow: 1;
        border-bottom: 1px dotted #000;
        margin: 0 0.5em;
        height: 0;
    }}
    .toc-page-num {{
        font-weight: bold;
    }}
    </style>
</head>
<body>
    <div class="toc-page">
        <h2 class="toc-title">Table des matières</h2>
        {toc_entries}
    </div>
</body>
</html>
"""


def generate_index_html(authors_index):
    """Index des auteurs."""
    authors_entries = ""
    for author_name, pages in authors_index.items():
        pages_str = ', '.join(map(str, pages))
        authors_entries += f'<div class="author-entry">{author_name} {pages_str}</div>'

    return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Index des auteurs</title>
    <style>
    @page {{
        margin: 1.5cm 1.8cm 1.5cm 1.8cm;
        @bottom-center {{ content: none; }}
    }}
    body {{
        font-family: "Helvetica", Arial, sans-serif;
        font-size: 11pt;
        color: #000;
        margin: 0;
        padding: 0;
    }}
    .authors-title {{
        text-align: center;
        font-size: 16pt;
        font-weight: bold;
        margin-bottom: 2em;
        border-bottom: 0.5pt solid #000;
        padding-bottom: 0.5em;
    }}
    .authors-intro {{
        margin-bottom: 1.5em;
        text-align: justify;
        font-size: 11pt;
        line-height: 1.4;
    }}
    .authors-grid {{
        columns: 3;
        column-gap: 20pt;
        column-fill: balance;
        text-align: left;
    }}
    .author-entry {{
        break-inside: avoid;
        margin-bottom: 0.2em;
        font-size: 10pt;
        line-height: 1.1;
    }}
    </style>
</head>       
<body>
    <div class="authors-index">
        <h2 class="authors-title">Index des auteurs</h2>
 <div class="authors-intro">
 Le comité d'organisation adresse de très vifs remerciements aux relecteurs qui ont pris le 
            temps de lire et d'expertiser les articles soumis au congrès.
        </div>
        <div class="authors-grid">
            {authors_entries}
        </div>
    </div>
</body>
</html>
"""


def generate_theme_separator_pdf(theme_name):
    """Génère une page de séparation pour une thématique."""
    html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Thématique</title>
    <style>{get_book_css()}</style>
</head>
<body>
    <div class="part-page">
        <div class="part-title">{theme_name}</div>
    </div>
</body>
</html>
"""
    return html_to_pdf(html)


def generate_placeholder_pdf(communication):
    """Génère une page placeholder pour une communication sans PDF."""
    html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Communication manquante</title>
    <style>{get_book_css()}</style>
</head>
<body>
    <div class="communication">
        <h4 class="comm-title">{communication.title}</h4>
        <div class="comm-authors">
            {', '.join([f"{a.first_name} {a.last_name}" for a in communication.authors]) if communication.authors else "Auteur non spécifié"}
        </div>
        <div style="margin-top: 2em; text-align: center; color: #666;">
            <p><em>PDF de la communication en attente</em></p>
        </div>
    </div>
</body>
</html>
"""
    return html_to_pdf(html)


def get_presidents_names(config):
    """Récupère les noms des présidents."""
    if 'presidents' in config.get('conference', {}) and config['conference']['presidents']:
        return "<br>".join([p['name'] for p in config['conference']['presidents']])
    else:
        return "Jean-Baptiste Biot, Joseph Fourier"


def get_book_title_type(title):
    """Détermine le titre et type de livre."""
    if 'article' in title.lower():
        return "ACTES", "du"
    else:
        return "RECUEIL DES RÉSUMÉS", "du"


# === ROUTES PRINCIPALES ===

@books.route('/tome1.pdf')
@login_required
def generate_tome1():
    """Génère le Tome 1 des articles par agrégation PDF."""
    if not current_user.is_admin:
        abort(403)
    
    if not PDF_TOOLS_AVAILABLE:
        return "PyPDF2 et reportlab requis pour l'agrégation PDF", 500
    
    try:
        communications = get_communications_by_type_and_status()
        tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
        
        # Générer l'index des auteurs
        authors_index = generate_author_index(
            [comm for theme_comms in tomes_split['tome1'].values() for comm in theme_comms],
            {}  # Le page_mapping sera calculé dans generate_complete_book_pdf
        )
        
        # Générer le PDF complet
        pdf_content = generate_complete_book_pdf(
            "Articles - Tome 1",
            tomes_split['tome1'],
            authors_index,
            'article'
        )
        
        # Créer la réponse
        config = get_conference_config()
        filename = f"{config.get('conference', {}).get('short_name', 'Conference')}_Articles_Tome1.pdf"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_content)
            tmp_file_path = tmp_file.name
        
        return send_file(
            tmp_file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération Tome 1: {e}")
        return f"Erreur lors de la génération du PDF: {str(e)}", 500
    
    finally:
        try:
            if 'tmp_file_path' in locals():
                os.unlink(tmp_file_path)
        except:
            pass


@books.route('/tome2.pdf')
@login_required
def generate_tome2():
    """Génère le Tome 2 des articles par agrégation PDF."""
    if not current_user.is_admin:
        abort(403)
    
    if not PDF_TOOLS_AVAILABLE:
        return "PyPDF2 et reportlab requis pour l'agrégation PDF", 500
    
    try:
        communications = get_communications_by_type_and_status()
        tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
        
        # Générer l'index des auteurs
        authors_index = generate_author_index(
            [comm for theme_comms in tomes_split['tome2'].values() for comm in theme_comms],
            {}
        )
        
        # Générer le PDF complet
        pdf_content = generate_complete_book_pdf(
            "Articles - Tome 2",
            tomes_split['tome2'],
            authors_index,
            'article'
        )
        
        # Créer la réponse
        config = get_conference_config()
        filename = f"{config.get('conference', {}).get('short_name', 'Conference')}_Articles_Tome2.pdf"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_content)
            tmp_file_path = tmp_file.name
        
        return send_file(
            tmp_file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération Tome 2: {e}")
        return f"Erreur lors de la génération du PDF: {str(e)}", 500
    
    finally:
        try:
            if 'tmp_file_path' in locals():
                os.unlink(tmp_file_path)
        except:
            pass


@books.route('/resumes-wip.pdf')
@login_required
def generate_resumes_wip():
    """Génère le livre des résumés et WIP par agrégation PDF avec filigrane."""
    if not current_user.is_admin:
        abort(403)
    
    if not PDF_TOOLS_AVAILABLE:
        return "PyPDF2 et reportlab requis pour l'agrégation PDF", 500
    
    try:
        communications = get_communications_by_type_and_status()
        
        # Combiner résumés et WIP
        all_communications = communications['resumes'] + communications['wips']
        all_by_theme = group_communications_by_thematique(all_communications)
        
        # Générer l'index des auteurs
        authors_index = generate_author_index(all_communications, {})
        
        # Générer le PDF complet (avec filigrane WIP automatique)
        pdf_content = generate_complete_book_pdf(
            "Résumés et Work in Progress",
            all_by_theme,
            authors_index,
            'resume'  # Ce type déclenchera le filigrane pour les WIP
        )
        
        # Créer la réponse
        config = get_conference_config()
        filename = f"{config.get('conference', {}).get('short_name', 'Conference')}_Resumes_WorkInProgress.pdf"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_content)
            tmp_file_path = tmp_file.name
        
        return send_file(
            tmp_file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération Résumés/WIP: {e}")
        return f"Erreur lors de la génération du PDF: {str(e)}", 500
    
    finally:
        try:
            if 'tmp_file_path' in locals():
                os.unlink(tmp_file_path)
        except:
            pass


@books.route('/preview/<book_type>')
@login_required
def preview_book(book_type):
    """Prévisualise un livre en HTML (version simplifiée)."""
    if not current_user.is_admin:
        abort(403)
    
    if book_type not in ['tome1', 'tome2', 'resumes-wip']:
        abort(404)
    
    try:
        communications = get_communications_by_type_and_status()
        config = get_conference_config()
        
        if book_type == 'tome1':
            tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
            title = "Articles - Tome 1"
            communications_data = tomes_split['tome1']
        elif book_type == 'tome2':
            tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
            title = "Articles - Tome 2"
            communications_data = tomes_split['tome2']
        else:  # resumes-wip
            all_communications = communications['resumes'] + communications['wips']
            title = "Résumés et Work in Progress"
            communications_data = group_communications_by_thematique(all_communications)
        
        # Générer une prévisualisation simple
        html_content = generate_cover_only_html(title, config)
        
        return html_content
        
    except Exception as e:
        current_app.logger.error(f"Erreur prévisualisation {book_type}: {e}")
        return f"Erreur lors de la prévisualisation: {str(e)}", 500

