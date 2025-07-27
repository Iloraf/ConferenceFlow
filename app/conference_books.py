# app/conference_books.py - Générateur des livres de conférence

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
                         weasyprint_available=WEASYPRINT_AVAILABLE)




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
                    thematique_key = f"{thematique['code']} - {thematique['nom']}"
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
    
    # Rééquilibrer si nécessaire
    if abs(tome1_count - tome2_count) > 5:
        # Logique de rééquilibrage si besoin
        pass
    
    return {
        'tome1': group_communications_by_thematique(tome1_articles),
        'tome2': group_communications_by_thematique(tome2_articles)
    }

def generate_author_index(communications, page_mapping):
    """Génère l'index des auteurs avec numéros de pages."""
    
    authors_index = defaultdict(list)
    
    for comm in communications:
        if comm.id in page_mapping:
            page_num = page_mapping[comm.id]
            for author in comm.authors:
                author_name = f"{author.last_name or ''}, {author.first_name or ''}".strip(', ')
                if not author_name:
                    author_name = author.email
                
                authors_index[author_name].append({
                    'title': comm.title[:50] + ('...' if len(comm.title) > 50 else ''),
                    'page': page_num,
                    'comm_id': comm.id
                })
    
    # Trier par ordre alphabétique
    sorted_authors = OrderedDict(sorted(authors_index.items()))
    
    return sorted_authors

def get_communication_file_path(communication, file_type):
    """Récupère le chemin du fichier pour une communication."""
    latest_file = communication.get_latest_file(file_type)
    if latest_file and os.path.exists(latest_file.file_path):
        return latest_file.file_path
    return None

def generate_page_mapping(communications_by_theme, start_page=1):
    """Génère un mapping communication_id -> numéro de page."""
    page_mapping = {}
    current_page = start_page
    
    for thematique, communications in communications_by_theme.items():
        # Page de titre de thématique
        current_page += 1
        
        for comm in communications:
            page_mapping[comm.id] = current_page
            # Estimer le nombre de pages par communication (ajustable)
            current_page += 6  # Par défaut, 6 pages par article
    
    return page_mapping

@books.route('/tome1.pdf')
@login_required
def generate_tome1():
    """Génère le Tome 1 des articles."""
    if not current_user.is_admin:
        abort(403)
    
    if not WEASYPRINT_AVAILABLE:
        return "WeasyPrint non disponible", 500
    
    communications = get_communications_by_type_and_status()
    tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
    
    # Générer le mapping des pages
    page_mapping = generate_page_mapping(tomes_split['tome1'])
    
    # Index des auteurs
    authors_index = generate_author_index(
        [comm for theme_comms in tomes_split['tome1'].values() for comm in theme_comms],
        page_mapping
    )
    
    html_content = render_tome_html(
        title="Articles - Tome 1",
        thematiques_groups=tomes_split['tome1'],
        page_mapping=page_mapping,
        authors_index=authors_index,
        book_type='article'
    )
    
    return generate_pdf_response(html_content, 'SFT2026_Articles_Tome1.pdf')

@books.route('/tome2.pdf')
@login_required
def generate_tome2():
    """Génère le Tome 2 des articles."""
    if not current_user.is_admin:
        abort(403)
    
    if not WEASYPRINT_AVAILABLE:
        return "WeasyPrint non disponible", 500
    
    communications = get_communications_by_type_and_status()
    tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
    
    # Générer le mapping des pages
    page_mapping = generate_page_mapping(tomes_split['tome2'])
    
    # Index des auteurs
    authors_index = generate_author_index(
        [comm for theme_comms in tomes_split['tome2'].values() for comm in theme_comms],
        page_mapping
    )
    
    html_content = render_tome_html(
        title="Articles - Tome 2",
        thematiques_groups=tomes_split['tome2'],
        page_mapping=page_mapping,
        authors_index=authors_index,
        book_type='article'
    )
    
    return generate_pdf_response(html_content, 'SFT2026_Articles_Tome2.pdf')

@books.route('/resumes-wip.pdf')
@login_required
def generate_resumes_wip():
    """Génère le livre des résumés et work in progress."""
    if not current_user.is_admin:
        abort(403)
    
    if not WEASYPRINT_AVAILABLE:
        return "WeasyPrint non disponible", 500
    
    communications = get_communications_by_type_and_status()
    
    # Grouper résumés et WIP par thématique
    resumes_by_theme = group_communications_by_thematique(communications['resumes'])
    wips_by_theme = group_communications_by_thematique(communications['wips'])
    
    # Combiner pour le mapping des pages
    all_communications = communications['resumes'] + communications['wips']
    all_by_theme = group_communications_by_thematique(all_communications)
    page_mapping = generate_page_mapping(all_by_theme)
    
    # Index des auteurs (uniquement pour les résumés)
    authors_index = generate_author_index(communications['resumes'], page_mapping)
    
    html_content = render_resumes_wip_html(
        resumes_by_theme=resumes_by_theme,
        wips_by_theme=wips_by_theme,
        page_mapping=page_mapping,
        authors_index=authors_index
    )
    
    return generate_pdf_response(html_content, 'SFT2026_Resumes_WorkInProgress.pdf')

def render_tome_html(title, thematiques_groups, page_mapping, authors_index, book_type):
    """Génère le HTML pour un tome d'articles."""
    
    # Template HTML pour les tomes
    html_template = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{title} - SFT 2026</title>
    <style>
        {get_book_css()}
    </style>
</head>
<body>
    <!-- Page de couverture -->
    <div class="cover-page">
        <h1>34ème Congrès Français de Thermique</h1>
        <h2>SFT 2026</h2>
        <h3>{title}</h3>
        <div class="cover-subtitle">
            Villers-lès-Nancy, 2-5 juin 2026<br>
            « Thermique & Décarbonation de l'industrie »
        </div>
    </div>
    
    <!-- Table des matières -->
    <div class="toc-page">
        <h2>Table des matières</h2>
        <div class="toc-content">
            <div class="toc-section">
                <a href="#authors-index">Index des auteurs</a>
                <span class="page-ref">3</span>
            </div>
            {generate_toc_html(thematiques_groups, page_mapping)}
        </div>
    </div>
    
    <!-- Index des auteurs -->
    <div id="authors-index" class="authors-index">
        <h2>Index des auteurs</h2>
        {generate_authors_index_html(authors_index)}
    </div>
    
    <!-- Contenu par thématiques -->
    {generate_content_html(thematiques_groups, book_type)}
    
</body>
</html>
"""
    return html_template

def render_resumes_wip_html(resumes_by_theme, wips_by_theme, page_mapping, authors_index):
    """Génère le HTML pour le livre résumés + WIP."""
    
    html_template = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Résumés et Work in Progress - SFT 2026</title>
    <style>
        {get_book_css()}
        {get_wip_watermark_css()}
    </style>
</head>
<body>
    <!-- Page de couverture -->
    <div class="cover-page">
        <h1>34ème Congrès Français de Thermique</h1>
        <h2>SFT 2026</h2>
        <h3>Résumés et Work in Progress</h3>
        <div class="cover-subtitle">
            Villers-lès-Nancy, 2-5 juin 2026<br>
            « Thermique & Décarbonation de l'industrie »
        </div>
    </div>
    
    <!-- Table des matières -->
    <div class="toc-page">
        <h2>Table des matières</h2>
        <div class="toc-content">
            <div class="toc-section">
                <a href="#authors-index">Index des auteurs</a>
                <span class="page-ref">3</span>
            </div>
            
            <h3>Résumés</h3>
            {generate_toc_html(resumes_by_theme, page_mapping)}
            
            <h3>Work in Progress</h3>
            {generate_toc_html(wips_by_theme, page_mapping)}
        </div>
    </div>
    
    <!-- Index des auteurs -->
    <div id="authors-index" class="authors-index">
        <h2>Index des auteurs</h2>
        {generate_authors_index_html(authors_index)}
    </div>
    
    <!-- Résumés -->
    <div class="section-divider">
        <h1>Résumés</h1>
    </div>
    {generate_content_html(resumes_by_theme, 'resume')}
    
    <!-- Work in Progress -->
    <div class="section-divider">
        <h1>Work in Progress</h1>
    </div>
    {generate_content_html(wips_by_theme, 'wip')}
    
</body>
</html>
"""
    return html_template

def generate_toc_html(thematiques_groups, page_mapping):
    """Génère le HTML de la table des matières."""
    toc_html = ""
    
    for thematique, communications in thematiques_groups.items():
        toc_html += f"""
        <div class="toc-thematique">
            <h3>{thematique}</h3>
            {generate_toc_communications_html(communications, page_mapping)}
        </div>
        """
    
    return toc_html

def generate_toc_communications_html(communications, page_mapping):
    """Génère le HTML des communications dans la TOC."""
    comm_html = ""
    
    for comm in communications:
        page_num = page_mapping.get(comm.id, '?')
        authors_str = ', '.join([f"{a.last_name or ''} {a.first_name or ''}".strip() for a in comm.authors[:3]])
        if len(comm.authors) > 3:
            authors_str += " et al."
        
        comm_html += f"""
        <div class="toc-communication">
            <a href="#comm-{comm.id}">{comm.title}</a>
            <div class="toc-authors">{authors_str}</div>
            <span class="page-ref">{page_num}</span>
        </div>
        """
    
    return comm_html

def generate_authors_index_html(authors_index):
    """Génère le HTML de l'index des auteurs en 2 colonnes."""
    
    authors_list = list(authors_index.items())
    mid_point = len(authors_list) // 2
    
    col1_authors = authors_list[:mid_point]
    col2_authors = authors_list[mid_point:]
    
    def generate_author_column(authors):
        html = ""
        for author_name, communications in authors:
            pages = ', '.join(str(comm['page']) for comm in communications)
            html += f"""
            <div class="author-entry">
                <span class="author-name">{author_name}</span>
                <span class="author-pages">{pages}</span>
            </div>
            """
        return html
    
    return f"""
    <div class="authors-columns">
        <div class="authors-column">
            {generate_author_column(col1_authors)}
        </div>
        <div class="authors-column">
            {generate_author_column(col2_authors)}
        </div>
    </div>
    """

def generate_content_html(thematiques_groups, content_type):
    """Génère le HTML du contenu principal."""
    content_html = ""
    
    for thematique, communications in thematiques_groups.items():
        content_html += f"""
        <div class="thematique-section">
            <h2 class="thematique-title">{thematique}</h2>
            {generate_communications_content_html(communications, content_type)}
        </div>
        """
    
    return content_html

def generate_communications_content_html(communications, content_type):
    """Génère le HTML pour les communications d'une thématique."""
    comm_html = ""
    
    for comm in communications:
        watermark_class = "wip-watermark" if content_type == 'wip' else ""
        
        # Informations de base
        authors_str = ', '.join([f"{a.first_name or ''} {a.last_name or ''}".strip() for a in comm.authors])
        affiliations_str = ', '.join(list(set([aff.sigle for author in comm.authors for aff in author.affiliations])))
        
        comm_html += f"""
        <div id="comm-{comm.id}" class="communication {watermark_class}">
            <h3 class="comm-title">{comm.title}</h3>
            <div class="comm-authors">{authors_str}</div>
            <div class="comm-affiliations">{affiliations_str}</div>
            
            <!-- Ici on inclurait le contenu du fichier PDF -->
            <div class="comm-content">
                <p class="placeholder">
                    [Contenu de la communication #{comm.id} - Type: {content_type}]
                </p>
                <!-- TODO: Intégrer le contenu réel du PDF -->
            </div>
        </div>
        """
    
    return comm_html

def get_book_css():
    """Retourne le CSS pour les livres."""
    return """
        @page {
            size: A4;
            margin: 2.5cm 2cm;
            @bottom-center {
                content: "Page " counter(page);
                font-size: 10pt;
                color: #666;
            }
            @bottom-right {
                content: "SFT 2026 - Nancy";
                font-size: 9pt;
                color: #999;
            }
        }
        
        body {
            font-family: 'Times New Roman', serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #333;
        }
        
        /* Page de couverture */
        .cover-page {
            page-break-after: always;
            text-align: center;
            padding-top: 5cm;
        }
        
        .cover-page h1 {
            font-size: 28pt;
            color: #007bff;
            margin-bottom: 1cm;
        }
        
        .cover-page h2 {
            font-size: 24pt;
            color: #333;
            margin-bottom: 2cm;
        }
        
        .cover-page h3 {
            font-size: 20pt;
            color: #007bff;
            margin-bottom: 3cm;
        }
        
        .cover-subtitle {
            font-size: 14pt;
            color: #666;
            line-height: 1.8;
        }
        
        /* Table des matières */
        .toc-page {
            page-break-before: always;
            page-break-after: always;
        }
        
        .toc-page h2 {
            color: #007bff;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        
        .toc-thematique {
            margin-bottom: 25px;
        }
        
        .toc-thematique h3 {
            color: #333;
            font-size: 14pt;
            margin-bottom: 10px;
            border-left: 4px solid #007bff;
            padding-left: 10px;
        }
        
        .toc-communication {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
            padding-left: 20px;
        }
        
        .toc-communication a {
            flex-grow: 1;
            text-decoration: none;
            color: #333;
            font-weight: 500;
        }
        
        .toc-communication a:hover {
            color: #007bff;
        }
        
        .toc-authors {
            font-style: italic;
            color: #666;
            font-size: 10pt;
            margin-top: 2px;
        }
        
        .page-ref {
            font-weight: bold;
            color: #007bff;
            min-width: 30px;
            text-align: right;
        }
        
        /* Index des auteurs */
        .authors-index {
            page-break-before: always;
            page-break-after: always;
        }
        
        .authors-index h2 {
            color: #007bff;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        
        .authors-columns {
            display: flex;
            gap: 30px;
        }
        
        .authors-column {
            flex: 1;
        }
        
        .author-entry {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            border-bottom: 1px dotted #ccc;
            padding-bottom: 2px;
        }
        
        .author-name {
            font-weight: 500;
        }
        
        .author-pages {
            color: #007bff;
            font-weight: bold;
        }
        
        /* Sections thématiques */
        .thematique-section {
            page-break-before: always;
        }
        
        .thematique-title {
            color: #007bff;
            font-size: 18pt;
            border-bottom: 3px solid #007bff;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }
        
        /* Communications */
        .communication {
            margin-bottom: 40px;
            page-break-inside: avoid;
        }
        
        .comm-title {
            color: #333;
            font-size: 14pt;
            font-weight: bold;
            margin-bottom: 10px;
        }
        
        .comm-authors {
            font-weight: 500;
            color: #007bff;
            margin-bottom: 5px;
        }
        
        .comm-affiliations {
            font-style: italic;
            color: #666;
            font-size: 10pt;
            margin-bottom: 15px;
        }
        
        .comm-content {
            margin-top: 20px;
        }
        
        .placeholder {
            background-color: #f8f9fa;
            padding: 20px;
            border: 1px dashed #ddd;
            text-align: center;
            color: #666;
            font-style: italic;
        }
        
        .section-divider {
            page-break-before: always;
            text-align: center;
            padding: 50px 0;
        }
        
        .section-divider h1 {
            font-size: 24pt;
            color: #007bff;
            border-top: 3px solid #007bff;
            border-bottom: 3px solid #007bff;
            padding: 20px 0;
            margin: 0;
        }
    """

def get_wip_watermark_css():
    """Retourne le CSS pour le filigrane Work in Progress."""
    return """
        .wip-watermark {
            position: relative;
        }
        
        .wip-watermark::before {
            content: "WORK IN PROGRESS";
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) rotate(-45deg);
            font-size: 48pt;
            color: rgba(220, 53, 69, 0.1);
            font-weight: bold;
            z-index: -1;
            white-space: nowrap;
            pointer-events: none;
        }
    """

def generate_pdf_response(html_content, filename):
    """Génère et retourne la réponse PDF."""
    try:
        html_doc = HTML(string=html_content)
        pdf_buffer = BytesIO()
        html_doc.write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_buffer.getvalue())
            tmp_file_path = tmp_file.name
        
        return send_file(
            tmp_file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération PDF {filename}: {e}")
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
    """Prévisualise un livre en HTML."""
    if not current_user.is_admin:
        abort(403)
    
    if book_type not in ['tome1', 'tome2', 'resumes-wip']:
        abort(404)
    
    communications = get_communications_by_type_and_status()
    
    if book_type == 'tome1':
        tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
        page_mapping = generate_page_mapping(tomes_split['tome1'])
        authors_index = generate_author_index(
            [comm for theme_comms in tomes_split['tome1'].values() for comm in theme_comms],
            page_mapping
        )
        html_content = render_tome_html(
            "Articles - Tome 1", tomes_split['tome1'], page_mapping, authors_index, 'article'
        )
    elif book_type == 'tome2':
        tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
        page_mapping = generate_page_mapping(tomes_split['tome2'])
        authors_index = generate_author_index(
            [comm for theme_comms in tomes_split['tome2'].values() for comm in theme_comms],
            page_mapping
        )
        html_content = render_tome_html(
            "Articles - Tome 2", tomes_split['tome2'], page_mapping, authors_index, 'article'
        )
    else:  # resumes-wip
        resumes_by_theme = group_communications_by_thematique(communications['resumes'])
        wips_by_theme = group_communications_by_thematique(communications['wips'])
        all_communications = communications['resumes'] + communications['wips']
        all_by_theme = group_communications_by_thematique(all_communications)
        page_mapping = generate_page_mapping(all_by_theme)
        authors_index = generate_author_index(communications['resumes'], page_mapping)
        html_content = render_resumes_wip_html(resumes_by_theme, wips_by_theme, page_mapping, authors_index)
    
    return html_content
