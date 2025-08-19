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
                # Format: "Nom Prénom" (comme dans le PDF SFT)
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


def generate_page_mapping(communications_by_theme, start_page=5):
    """Génère un mapping communication_id -> numéro de page."""
    page_mapping = {}
    current_page = start_page
    
    theme_number = 1
    for thematique, communications in communications_by_theme.items():
        # Page de titre de thématique
        current_page += 1
        
        for comm in communications:
            page_mapping[comm.id] = current_page
            # Estimer le nombre de pages par communication (ajustable)
            current_page += 8  # Articles complets : ~8 pages
        
        theme_number += 1
    
    return page_mapping


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
                'name': '34ème Congrès Français de Thermique',
                'short_name': 'SFT 2026',
                'theme': 'Thermique & Décarbonation de l\'industrie',
                'organizing_lab': {
                    'short_name': 'LEMTA',
                    'description': 'Laboratoire Énergies & Mécanique Théorique et Appliquée'
                }
            },
            'dates': {'dates': '2-5 juin 2026'},
            'location': {'city': 'Villers-lès-Nancy'}
        }


def get_book_css():
    """CSS reproduisant exactement le style SFT des actes."""
    return """
    /* === CONFIGURATION DE PAGE === */
    @page {
        size: A4;
        margin: 2.5cm 2cm 2cm 2cm;
        
        @top-center {
            content: string(page-header);
            font-size: 10pt;
            border-bottom: 1px solid #000;
            padding-bottom: 3pt;
            margin-bottom: 10pt;
        }
        
        @bottom-center {
            content: counter(page);
            font-size: 10pt;
        }
    }
    
    @page cover {
        margin: 0;
        @top-center { content: none; }
        @bottom-center { content: none; }
    }
    
    @page toc {
        @bottom-center { content: counter(page, lower-roman); }
    }
    
    /* === TYPOGRAPHIE === */
    body {
        font-family: Arial, sans-serif;
        font-size: 11pt;
        line-height: 1.2;
        color: #000;
        margin: 0;
        padding: 0;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: Arial, sans-serif;
        color: #000;
        margin: 0;
        padding: 0;
        font-weight: bold;
    }
    
    /* === PAGE DE COUVERTURE (style SFT exact) === */
    .cover-page {
        page: cover;
        height: 100vh;
        background: white;
        color: black;
        text-align: center;
        padding-top: 15%;
        page-break-after: always;
    }
    
    .cover-theme-line {
        font-size: 14pt;
        font-weight: bold;
        margin-bottom: 1em;
        letter-spacing: 1pt;
    }
    
    .cover-authors {
        font-size: 12pt;
        font-weight: bold;
        margin-bottom: 3em;
    }
    
    .cover-actes {
        font-size: 16pt;
        font-weight: bold;
        margin-bottom: 0.5em;
    }
    
    .cover-du {
        font-size: 12pt;
        margin-bottom: 0.5em;
    }
    
    .cover-congres-title {
        font-size: 14pt;
        font-weight: bold;
        margin-bottom: 2em;
        line-height: 1.3;
    }
    
    .cover-event-code {
        font-size: 16pt;
        font-weight: bold;
        margin-bottom: 3em;
    }
    
    .cover-dates {
        font-size: 12pt;
        font-weight: bold;
        margin-bottom: 0.5em;
    }
    
    .cover-location {
        font-size: 12pt;
        font-weight: bold;
        margin-bottom: 3em;
    }
    
    .cover-organise {
        font-size: 10pt;
        font-weight: bold;
        margin-bottom: 0.5em;
    }
    
    .cover-organizer {
        font-size: 10pt;
        margin-bottom: 0.5em;
    }
    
    /* === PAGE BLANCHE === */
    .blank-page {
        page-break-before: always;
        page-break-after: always;
        height: 100vh;
        background: white;
    }
    
    .blank-footer {
        position: absolute;
        bottom: 2cm;
        left: 0;
        right: 0;
        text-align: center;
        font-size: 10pt;
        border-top: 1px solid #000;
        padding-top: 3pt;
    }
    
    /* === TABLE DES MATIÈRES === */
    .toc-page {
        page: toc;
        page-break-before: always;
        page-break-after: always;
    }
    
    .toc-title {
        text-align: center;
        font-size: 16pt;
        font-weight: bold;
        margin-bottom: 2em;
        border-bottom: 1px solid #000;
        padding-bottom: 0.5em;
    }
    
    .toc-entry {
        margin-bottom: 0.3em;
        display: flex;
        justify-content: space-between;
        align-items: baseline;
    }
    
    .toc-entry a {
        color: #000;
        text-decoration: none;
        flex-grow: 1;
    }
    
    .toc-dots {
        flex-grow: 1;
        border-bottom: 1px dotted #000;
        margin: 0 0.5em;
        height: 0;
    }
    
    .toc-page-num {
        font-weight: bold;
    }
    
    /* === INDEX DES AUTEURS === */
    .authors-index {
        page-break-before: always;
        page-break-after: always;
    }
    
    .authors-title {
        text-align: center;
        font-size: 16pt;
        font-weight: bold;
        margin-bottom: 2em;
        border-bottom: 1px solid #000;
        padding-bottom: 0.5em;
    }
    
    .authors-intro {
        margin-bottom: 1.5em;
        text-align: justify;
        font-size: 11pt;
        line-height: 1.4;
    }
    
    .authors-grid {
        columns: 3;
        column-gap: 20pt;
        column-fill: balance;
        text-align: left;
    }
    
    .author-entry {
        break-inside: avoid;
        margin-bottom: 0.2em;
        font-size: 10pt;
        line-height: 1.1;
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
    }
    
    .part-subtitle {
        font-size: 14pt;
        font-weight: bold;
    }
    
    /* === CONTENU PRINCIPAL === */
    .main-content {
        page-break-before: always;
    }
    
    .section-title {
        font-size: 14pt;
        font-weight: bold;
        margin-bottom: 2em;
        text-align: left;
    }
    
    .theme-title {
        font-size: 12pt;
        font-weight: bold;
        margin: 2em 0 1em 0;
        page-break-after: avoid;
    }
    
    .communication {
        margin-bottom: 1.5em;
        page-break-inside: avoid;
    }
    
    .comm-title {
        font-size: 11pt;
        font-weight: bold;
        margin-bottom: 0.5em;
        line-height: 1.3;
    }
    
    .comm-authors {
        font-size: 11pt;
        margin-bottom: 0.3em;
    }
    
    .comm-affiliations {
        font-size: 10pt;
        font-style: italic;
        margin-bottom: 1em;
    }
    
    .comm-content {
        font-size: 11pt;
        line-height: 1.4;
        text-align: justify;
    }
    
    /* === HEADER DYNAMIQUE === */
    .set-header {
        string-set: page-header content();
    }
    
    /* === UTILITAIRES === */
    .page-break { page-break-before: always; }
    .no-break { page-break-inside: avoid; }
    .text-center { text-align: center; }
    
    /* === APERÇU WEB === */
    @media screen {
        body { 
            background: #f5f5f5; 
            padding: 20px; 
        }
        
        .cover-page, .toc-page, .authors-index, .main-content {
            background: white;
            padding: 40px;
            margin-bottom: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            min-height: 80vh;
        }
    }
    """


def render_tome_html(title, thematiques_groups, page_mapping, authors_index, book_type):
    """Génère le HTML d'un tome au style SFT exact."""
    
    config = get_conference_config()
    
    # En-tête des pages comme dans le PDF SFT
    header_text = f"Congrès Français de Thermique {config['conference']['short_name']}, {config['location']['city']}, {config['dates']['dates']}"
    
    # Générer les noms des présidents depuis la config si disponible
    presidents_names = ""
    if 'presidents' in config['conference'] and config['conference']['presidents']:
        presidents_names = "<br>".join([p['name'] for p in config['conference']['presidents']])
    else:
        presidents_names = "MICHEL GRADECK<br>VINCENT SCHICK"  # Noms par défaut
    
    html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{title} - {config['conference']['short_name']}</title>
    <style>{get_book_css()}</style>
</head>
<body>
    <!-- En-tête pour toutes les pages -->
    <div class="set-header" style="display: none;">{header_text}</div>
    
    <!-- Page de couverture exacte style SFT -->
    <div class="cover-page">
        <div class="cover-theme-line">{config['conference']['theme'].upper()}</div>
        <div class="cover-authors">{presidents_names}</div>
        
        <div class="cover-actes">ACTES</div>
        <div class="cover-du">DU</div>
        
        <div class="cover-congres-title">
            CONGRÈS ANNUEL DE LA<br>
            SOCIÉTÉ FRANÇAISE DE THERMIQUE
        </div>
        
        <div class="cover-event-code">{config['conference']['short_name']}</div>
        
        <div class="cover-dates">{config['dates']['dates']}</div>
        <div class="cover-location">{config['location']['city']}</div>
        
        <div class="cover-organise">ORGANISÉ PAR</div>
        <div class="cover-organizer">
            {config['conference']['organizing_lab']['short_name']} - {config['conference']['organizing_lab']['description']}
        </div>
    </div>
    
    <!-- Page blanche avec footer -->
    <div class="blank-page">
        <div class="blank-footer">
            {header_text}<br>
            ii
        </div>
    </div>
    
    <!-- Table des matières -->
    <div class="toc-page">
        <h2 class="toc-title">Table des matières</h2>
        
        <div class="toc-entry">
            <a href="#authors-index">Index des auteurs</a>
            <div class="toc-dots"></div>
            <span class="toc-page-num">3</span>
        </div>
        
        {generate_toc_entries(thematiques_groups, page_mapping)}
    </div>
    
    <!-- Index des auteurs -->
    <div id="authors-index" class="authors-index">
        <h2 class="authors-title">Index des auteurs</h2>
        
        <div class="authors-intro">
            Le comité d'organisation adresse de très vifs remerciements aux relecteurs qui ont pris le 
            temps de lire et d'expertiser les articles soumis au congrès.
        </div>
        
        {generate_authors_html(authors_index)}
    </div>
    
    <!-- Première partie -->
    <div class="part-page">
        <div class="part-title">Deuxième partie</div>
        <div class="part-subtitle">Textes complets</div>
    </div>
    
    <!-- Contenu principal -->
    <div class="main-content">
        {generate_themes_content(thematiques_groups, book_type)}
    </div>
    
</body>
</html>
"""
    return html


def generate_toc_entries(thematiques_groups, page_mapping):
    """Génère les entrées de la table des matières."""
    toc_html = ""
    theme_num = 1
    
    for theme_name, communications in thematiques_groups.items():
        if communications:
            first_page = page_mapping.get(communications[0].id, '???')
            
            toc_html += f"""
            <div class="toc-entry">
                <a href="#theme-{theme_num}">{theme_num} {theme_name}</a>
                <div class="toc-dots"></div>
                <span class="toc-page-num">{first_page}</span>
            </div>
            """
            
            # Limiter les communications affichées dans la TOC
            for comm in communications[:3]:
                page_num = page_mapping.get(comm.id, '???')
                title_short = comm.title[:60] + ('...' if len(comm.title) > 60 else '')
                
                toc_html += f"""
                <div class="toc-entry" style="margin-left: 1em; font-size: 10pt;">
                    <a href="#comm-{comm.id}">{title_short}</a>
                    <div class="toc-dots"></div>
                    <span class="toc-page-num">{page_num}</span>
                </div>
                """
            
            if len(communications) > 3:
                toc_html += f"""
                <div class="toc-entry" style="margin-left: 1em; font-size: 10pt; font-style: italic;">
                    <span>... et {len(communications) - 3} autres communications</span>
                    <div class="toc-dots"></div>
                    <span class="toc-page-num"></span>
                </div>
                """
        
        theme_num += 1
    
    return toc_html


def generate_authors_html(authors_index):
    """Génère l'HTML de l'index des auteurs en 3 colonnes."""
    authors_html = '<div class="authors-grid">'
    
    for author_name, pages in authors_index.items():
        pages_str = ', '.join(map(str, pages))
        authors_html += f'<div class="author-entry">{author_name} {pages_str}</div>'
    
    authors_html += '</div>'
    return authors_html


def generate_themes_content(thematiques_groups, book_type):
    """Génère le contenu des thématiques."""
    content_html = ""
    theme_num = 1
    
    for theme_name, communications in thematiques_groups.items():
        content_html += f"""
        <div id="theme-{theme_num}" class="theme-section">
            <h2 class="section-title">Thème {theme_num}</h2>
            <h3 class="theme-title">{theme_name}</h3>
            
            {generate_communications_html(communications, book_type)}
        </div>
        """
        theme_num += 1
    
    return content_html


def generate_communications_html(communications, book_type):
    """Génère le HTML des communications."""
    comm_html = ""
    
    for comm in communications:
        # Auteurs
        authors_list = []
        for author in comm.authors:
            name_parts = []
            if author.first_name:
                name_parts.append(author.first_name.strip())
            if author.last_name:
                name_parts.append(author.last_name.strip())
            
            if name_parts:
                authors_list.append(' '.join(name_parts))
            elif author.email:
                authors_list.append(author.email)
        
        authors_str = ', '.join(authors_list) if authors_list else "Auteur non spécifié"
        
        # Affiliations
        affiliations = set()
        for author in comm.authors:
            for aff in author.affiliations:
                if aff.sigle:
                    affiliations.add(aff.sigle)
        
        affiliations_str = ', '.join(sorted(affiliations)) if affiliations else ""
        
        comm_html += f"""
        <div id="comm-{comm.id}" class="communication">
            <h4 class="comm-title">{comm.title}</h4>
            <div class="comm-authors">{authors_str}</div>
            {f'<div class="comm-affiliations">{affiliations_str}</div>' if affiliations_str else ''}
            
            <div class="comm-content">
                <p>[Contenu de la communication - sera intégré depuis le fichier PDF]</p>
            </div>
        </div>
        """
    
    return comm_html


# Reprendre les routes existantes
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
    
    page_mapping = generate_page_mapping(tomes_split['tome1'])
    authors_index = generate_author_index(
        [comm for theme_comms in tomes_split['tome1'].values() for comm in theme_comms],
        page_mapping
    )
    
    html_content = render_tome_html(
        "Articles - Tome 1",
        tomes_split['tome1'],
        page_mapping,
        authors_index,
        'article'
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
    
    page_mapping = generate_page_mapping(tomes_split['tome2'])
    authors_index = generate_author_index(
        [comm for theme_comms in tomes_split['tome2'].values() for comm in theme_comms],
        page_mapping
    )
    
    html_content = render_tome_html(
        "Articles - Tome 2",
        tomes_split['tome2'],
        page_mapping,
        authors_index,
        'article'
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
    page_mapping = generate_page_mapping(all_by_theme, start_page=5)
    
    # Index des auteurs (tous)
    authors_index = generate_author_index(all_communications, page_mapping)
    
    html_content = render_tome_html(
        "Résumés et Work in Progress",
        all_by_theme,
        page_mapping,
        authors_index,
        'resume'
    )
    
    return generate_pdf_response(html_content, 'SFT2026_Resumes_WorkInProgress.pdf')


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
            "Articles - Tome 1", 
            tomes_split['tome1'], 
            page_mapping, 
            authors_index, 
            'article'
        )
    elif book_type == 'tome2':
        tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
        page_mapping = generate_page_mapping(tomes_split['tome2'])
        authors_index = generate_author_index(
            [comm for theme_comms in tomes_split['tome2'].values() for comm in theme_comms],
            page_mapping
        )
        html_content = render_tome_html(
            "Articles - Tome 2", 
            tomes_split['tome2'], 
            page_mapping, 
            authors_index, 
            'article'
        )
    else:  # resumes-wip
        resumes_by_theme = group_communications_by_thematique(communications['resumes'])
        wips_by_theme = group_communications_by_thematique(communications['wips'])
        all_communications = communications['resumes'] + communications['wips']
        all_by_theme = group_communications_by_thematique(all_communications)
        page_mapping = generate_page_mapping(all_by_theme, start_page=5)
        authors_index = generate_author_index(all_communications, page_mapping)
        html_content = render_tome_html(
            "Résumés et Work in Progress",
            all_by_theme,
            page_mapping,
            authors_index,
            'resume'
        )
    
    return html_content
