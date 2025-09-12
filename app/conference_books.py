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
import time

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
        @page {
            size: A4;
            margin: 0;
        }
        
        body {
            font-family: 'Computer Modern', 'Times New Roman', serif;
            margin: 0;
            padding: 0;
            line-height: 1.2;
        }
        
        .cover-page {
            width: 210mm;
            height: 297mm;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            padding: 40mm 20mm;
            box-sizing: border-box;
            position: relative;
        }
        
        /* THÈME EN HAUT */
        .cover-theme-line {
            font-size: 18pt;
            font-weight: normal;
            text-transform: uppercase;
            letter-spacing: 0.5pt;
            margin-bottom: 0;
        }
        
        /* ESPACES FLEXIBLES (reproduit \vspace{\stretch{1}}) */
        .cover-spacer-1 { flex: 1; }
        .cover-spacer-2 { flex: 0.5; }
        .cover-spacer-3 { flex: 1; }
        .cover-spacer-4 { flex: 1; }
        .cover-spacer-5 { flex: 1; }
        .cover-spacer-large { flex: 2; }
        
        /* PRÉSIDENTS */
        .cover-presidents {
            font-size: 12pt;
            font-weight: normal;
            line-height: 1.4;
        }
        
        /* TITRE PRINCIPAL */
        .cover-title-main {
            font-size: 32pt;
            font-weight: bold;
            margin-bottom: 0.3em;
        }
        
        .cover-du {
            font-size: 18pt;
            font-weight: normal;
            margin-bottom: 0.5em;
        }
        
        /* CONGRÈS */
        .cover-congress-title {
            font-size: 32pt;
            font-weight: normal;
            line-height: 1.1;
            margin-bottom: 0;
        }
        
        /* CODE ÉVÉNEMENT */
        .cover-event-code {
            font-size: 32pt;
            font-weight: bold;
        }
        
        /* DATES ET LIEU */
        .cover-dates-location {
            font-size: 16pt;
            font-weight: normal;
            line-height: 1.3;
        }
        
        /* ORGANISÉ PAR */
        .cover-organized-by {
            font-size: 14pt;
            font-weight: normal;
            margin-bottom: 0.5em;
        }
        
        .cover-organizer {
            font-size: 12pt;
            font-weight: normal;
            line-height: 1.4;
        }
/* STYLES POUR LES CHAPITRES (nouveaux) */
.chapter-page {
    width: 210mm;
    height: 297mm;
    padding: 25mm 20mm;
    box-sizing: border-box;
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.4;
}

.chapter-title {
    font-size: 18pt;
    font-weight: bold;
    margin-bottom: 1.5em;
    text-align: left;
    border-bottom: 1px solid #000;
    padding-bottom: 0.5em;
}

.chapter-content {
    text-align: justify;
    line-height: 1.5;
}

.chapter-content h2 {
    font-size: 14pt;
    font-weight: bold;
    margin: 1.5em 0 1em 0;
    text-decoration: underline;
}

.chapter-content h3 {
    font-size: 12pt;
    font-weight: bold;
    margin: 1.2em 0 0.8em 0;
}

.chapter-content p {
    margin-bottom: 1em;
    text-align: justify;
}

.chapter-content ul {
    margin: 1em 0;
    padding-left: 0;
    list-style: none;
}

.chapter-content ul li {
    margin-bottom: 0.5em;
    padding-left: 1em;
    position: relative;
}

.chapter-content ul li:before {
    content: "•";
    position: absolute;
    left: 0;
    font-weight: bold;
}

.signature {
    margin-top: 3em;
    text-align: right;
    font-style: italic;
}

.remerciements-text, .introduction-text {
    line-height: 1.6;
}

/* Styles spécifiques comité organisation */
.chapter-content strong {
    font-weight: bold;
}

.chapter-content small {
    font-size: 10pt;
    color: #666;
}

        
        /* Responsive pour l'aperçu web */
        @media screen and (max-width: 800px) {
            .cover-page {
                width: 100vw;
                height: 140vw;
                padding: 8vw 4vw;
            }
            
            .cover-theme-line { font-size: 4vw; }
            .cover-title-main { font-size: 7vw; }
            .cover-congress-title { font-size: 7vw; }
            .cover-event-code { font-size: 7vw; }
            .cover-dates-location { font-size: 3.5vw; }
            .cover-organized-by { font-size: 3vw; }
            .cover-organizer { font-size: 2.5vw; }
            .cover-presidents { font-size: 2.5vw; }
        }
    """

# def get_book_css():
#     """CSS reproduisant exactement le style LaTeX SFT de référence."""
#     return """
#     /* === CONFIGURATION DE PAGE === */
#     @page {
#         size: A4;
#         margin: 1.5cm 1.8cm 1.5cm 1.8cm;  /* Marges exactes du LaTeX */
        
#         @top-center {
#             content: string(page-header);
#             font-family: "Helvetica", Arial, sans-serif;
#             font-size: 9pt;
#             border-bottom: 0.5pt solid #000;
#             padding-bottom: 3pt;
#             margin-bottom: 10pt;
#         }
        
#         @bottom-center {
#             content: counter(page);
#             font-family: "Helvetica", Arial, sans-serif;
#             font-size: 10pt;
#         }
#     }
    
#     @page cover {
#         margin: 0;
#         @top-center { content: none; }
#         @bottom-center { content: none; }
#     }
    
#     @page toc {
#         @bottom-center { 
#             content: counter(page, lower-roman);
#             font-family: "Helvetica", Arial, sans-serif;
#             font-size: 10pt;
#         }
#     }
    
#     /* === TYPOGRAPHIE EXACTE DU LATEX === */
#     body {
#         font-family: "Helvetica", Arial, sans-serif;  /* Sans-serif comme dans LaTeX */
#         font-size: 11pt;
#         line-height: 1.2;
#         color: #000;
#         margin: 0;
#         padding: 0;
#     }
    
#     /* Paragraphes avec indentation et espacement du LaTeX */
#     p {
#         margin: 0;
#         padding: 0;
#         text-indent: 10mm;  
#         margin-bottom: 2mm; 
#         text-align: justify;
#     }
    
#     /* Pas d'indentation pour le premier paragraphe */
#     p:first-child, .no-indent {
#         text-indent: 0;
#     }
    
#     h1, h2, h3, h4, h5, h6 {
#         font-family: "Helvetica", Arial, sans-serif;
#         color: #000;
#         margin: 0;
#         padding: 0;
#         font-weight: bold;
#         text-indent: 0;  /* Pas d'indentation pour les titres */
#     }
    
#     /* === PAGE DE COUVERTURE STYLE SFT === */
#     .cover-page {
#         page: cover;
#         height: 100vh;
#         background: white;
#         color: black;
#         text-align: center;
#         display: flex;
#         flex-direction: column;
#         justify-content: center;
#         align-items: center;
#         font-family: "Helvetica", Arial, sans-serif;
#         page-break-after: always;
#     }
    
#     .cover-theme-line {
#         font-size: 18pt;  
#         font-weight: normal;
#         margin-bottom: 1em;
#         text-transform: uppercase;
#         letter-spacing: 0.5pt;
#     }
    
#     .cover-authors {
#         font-size: 12pt;  
#         font-weight: normal;
#         margin-bottom: 3em;
#         line-height: 1.3;
#     }
    
#     .cover-actes {
#         font-size: 24pt;  
#         font-weight: bold;
#         margin-bottom: 1em;
#         text-transform: uppercase;
#     }
    
#     .cover-du {
#         font-size: 12pt;
#         margin-bottom: 1em;
#     }
    
#     .cover-congres-title {
#         font-size: 24pt;  
#         font-weight: normal;
#         margin-bottom: 2em;
#         line-height: 1.2;
#     }
    
#     .cover-event-code {
#         font-size: 24pt;  
#         font-weight: bold;
#         margin-bottom: 2em;
#     }
    
#     .cover-dates {
#         font-size: 14pt;  
#         font-weight: normal;
#         margin-bottom: 0.5em;
#     }
    
#     .cover-location {
#         font-size: 14pt;  
#         font-weight: normal;
#         margin-bottom: 2em;
#     }
    
#     .cover-organise {
#         font-size: 14pt;  
#         font-weight: normal;
#         margin-bottom: 1em;
#     }
    
#     .cover-organizer {
#         font-size: 12pt;  
#         font-weight: normal;
#         margin-bottom: 0.5em;
#         line-height: 1.3;
#     }
    
#     /* === SECTIONS PRINCIPALES === */
#     .part-page {
#         page-break-before: always;
#         page-break-after: always;
#         text-align: center;
#         padding-top: 40%;
#     }
    
#     .part-title {
#         font-size: 18pt;
#         font-weight: bold;
#         margin-bottom: 1em;
#         text-indent: 0;
#     }
    
#     /* === APERÇU WEB === */
#     @media screen {
#         body { 
#             background: #f5f5f5; 
#             padding: 20px; 
#         }
        
#         .cover-page, .part-page {
#             background: white;
#             padding: 40px;
#             margin-bottom: 20px;
#             box-shadow: 0 0 10px rgba(0,0,0,0.1);
#             min-height: 80vh;
#         }
        
#         /* En mode web, on désactive l'indentation pour la lisibilité */
#         p {
#             text-indent: 0;
#             margin-bottom: 1em;
#         }
#     }
#     """


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
    """Récupère le chemin vers le PDF d'une communication selon le type de livre."""
    try:
        current_app.logger.info(f"Recherche PDF pour comm {communication.id}, book_type: {book_type}, comm.type: {communication.type}")
        
        # Définir le type de fichier selon le type de livre
        if book_type in ['tome1', 'tome2']:
            # Pour les tomes d'articles complets - toujours des articles
            target_file = communication.get_file('article')
            current_app.logger.info(f"Recherche fichier 'article' pour tome (comm {communication.id})")
            
        elif book_type == 'resumes-wip':
            # Pour le livre résumés-wip - toujours chercher les résumés en priorité
            if communication.type == 'wip':
                # Pour les WIP, chercher d'abord le fichier WIP, sinon résumé
                target_file = communication.get_file('wip') or communication.get_file('résumé')
                current_app.logger.info(f"Recherche fichier 'wip' puis 'résumé' pour WIP (comm {communication.id})")
            else:
                # Pour tous les autres types, chercher résumé en priorité
                target_file = communication.get_file('résumé')
                current_app.logger.info(f"Recherche fichier 'résumé' pour résumé (comm {communication.id})")
                
                # Si pas de résumé, essayer 'resume' (sans accent)
                if not target_file:
                    target_file = communication.get_file('resume')
                    current_app.logger.info(f"Tentative fichier 'resume' (sans accent) pour comm {communication.id}")
        else:
            target_file = None
            current_app.logger.info(f"Type de livre non reconnu: {book_type}")
        
        if target_file and hasattr(target_file, 'file_path') and target_file.file_path:
            # Construire le chemin complet vers le fichier
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], target_file.file_path)
            current_app.logger.info(f"Chemin construit: {full_path}")
            
            # Vérifier que le fichier existe
            if os.path.exists(full_path):
                current_app.logger.info(f"✅ Fichier PDF trouvé: {full_path}")
                return full_path
            else:
                current_app.logger.warning(f"⚠️ Fichier PDF introuvable sur le disque: {full_path}")
                return None
        else:
            current_app.logger.info(f"ℹ️ Aucun fichier PDF de ce type pour comm {communication.id}")
            
            # Debug : lister tous les fichiers disponibles
            try:
                available_files = communication.submission_files
                if available_files:
                    current_app.logger.info(f"Fichiers disponibles pour comm {communication.id}:")
                    for file in available_files:
                        current_app.logger.info(f"  - {file.file_type}: {file.original_filename}")
                else:
                    current_app.logger.info(f"Aucun fichier trouvé pour comm {communication.id}")
            except Exception as e:
                current_app.logger.error(f"Erreur listing fichiers: {e}")
        
        return None
        
    except Exception as e:
        current_app.logger.error(f"❌ Erreur récupération PDF pour communication {communication.id}: {e}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return None




# def get_communication_pdf(communication, book_type):
#     try:
#         bt = (book_type or "").lower()
#         # Unifier : tout ce qui n’est pas "article" est traité comme recueil résumés/WIP
#         is_articles = bt in {"article", "tome1", "tome2"}

#         if is_articles:
#             target_file = communication.files.filter_by(file_type='article').first()
#         else:
#             if communication.type == 'wip':
#                 target_file = (communication.files
#                                .filter(SubmissionFile.file_type.in_(['wip','WIP']))
#                                .first())
#             else:
#                 # tolérer 'résumé' (accent), 'resume', 'abstract'
#                 target_file = (communication.files
#                                .filter(SubmissionFile.file_type.in_(['résumé','resume','abstract']))
#                                .first())

#         if target_file and target_file.file_path:
#             full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], target_file.file_path)
#             return full_path if os.path.exists(full_path) else None
#         return None
#     except Exception as e:
#         current_app.logger.error(f"Erreur récupération PDF pour communication {communication.id}: {e}")
#         return None


# def get_communication_pdf(communication, book_type):
#     """Récupère le chemin du fichier PDF d'une communication selon le type de livre."""
#     try:
#         # Définir le type de fichier selon le type de livre
#         if book_type == 'article':
#             # Pour les tomes d'articles complets
#             target_file = communication.files.filter_by(file_type='article').first()
#         elif book_type == 'resume':
#             # Pour les résumés et WIP
#             if communication.type == 'wip':
#                 target_file = communication.files.filter_by(file_type='wip').first()
#             else:
#                 target_file = communication.files.filter_by(file_type='résumé').first()
#         else:
#             target_file = None
        
#         if target_file and target_file.file_path:
#             # Construire le chemin complet vers le fichier
#             full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], target_file.file_path)
            
#             # Vérifier que le fichier existe
#             if os.path.exists(full_path):
#                 return full_path
#             else:
#                 current_app.logger.warning(f"Fichier PDF introuvable: {full_path}")
#                 return None
        
#         return None
        
#     except Exception as e:
#         current_app.logger.error(f"Erreur récupération PDF pour communication {communication.id}: {e}")
#         return None


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
            pdf_path = get_communication_pdf(comm, 'article' if comm.type == 'article' else 'resumes-wip')
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
        
        # B. SECTIONS PRÉLIMINAIRES (numérotation romaine)
        prelim_sections = ['remerciements', 'comite_organisation', 'reviewers', 'introduction', 'prix_biot_fourier']
        roman_page = 1
        
        for section_name in prelim_sections:
            if section_name in html_parts:
                section_pdf = html_to_pdf(html_parts[section_name])
                section_reader = PdfReader(BytesIO(section_pdf))
                for page in section_reader.pages:
                    numbered_page = add_page_number(page, roman_page, format='roman')
                    pdf_writer.add_page(numbered_page)
                    roman_page += 1
        
        # C. TOC (continuation numérotation romaine)
        toc_pdf = html_to_pdf(html_parts['toc'])
        toc_reader = PdfReader(BytesIO(toc_pdf))
        for page in toc_reader.pages:
            numbered_page = add_page_number(page, roman_page, format='roman')
            pdf_writer.add_page(numbered_page)
            roman_page += 1
        
        # D. COMMUNICATIONS PAR THÉMATIQUE (numérotation arabe recommence à 1)
        arabic_page = 1
        
        for theme_name, communications in communications_by_theme.items():
            # Page de séparateur thématique
            theme_page_pdf = generate_theme_separator_pdf(theme_name)
            theme_reader = PdfReader(BytesIO(theme_page_pdf))
            for page in theme_reader.pages:
                numbered_page = add_page_number(page, arabic_page, format='arabic')
                pdf_writer.add_page(numbered_page)
                arabic_page += 1
            
            # PDF des communications
            for comm in communications:
                comm_pdf_path = get_communication_pdf(comm, book_type)
                
                if comm_pdf_path and os.path.exists(comm_pdf_path):
                    comm_reader = PdfReader(comm_pdf_path)
                    
                    for page_num, page in enumerate(comm_reader.pages):
                        # Appliquer le filigrane WIP si nécessaire
                        if book_type.lower() in {'resume', 'resumes-wip'} and comm.type == 'wip':
                            page = add_wip_watermark(page)
                        
                        # Ajouter numérotation
                        numbered_page = add_page_number(page, arabic_page, format='arabic')
                        pdf_writer.add_page(numbered_page)
                        arabic_page += 1
                else:
                    # Page placeholder si PDF manquant
                    placeholder_pdf = generate_placeholder_pdf(comm)
                    placeholder_reader = PdfReader(BytesIO(placeholder_pdf))
                    for page in placeholder_reader.pages:
                        numbered_page = add_page_number(page, arabic_page, format='arabic')
                        pdf_writer.add_page(numbered_page)
                        arabic_page += 1
        
        # E. INDEX DES AUTEURS (continuation numérotation arabe)
        index_pdf = html_to_pdf(html_parts['index'])
        index_reader = PdfReader(BytesIO(index_pdf))
        for page in index_reader.pages:
            numbered_page = add_page_number(page, arabic_page, format='arabic')
            pdf_writer.add_page(numbered_page)
            arabic_page += 1


        
        
        # # A. Page de garde (pas de numérotation)
        # cover_pdf = html_to_pdf(html_parts['cover'])
        # cover_reader = PdfReader(BytesIO(cover_pdf))
        # for page in cover_reader.pages:
        #     pdf_writer.add_page(page)
        # current_page += len(cover_reader.pages)
        
        # # B. TOC (numérotation romaine)
        # toc_pdf = html_to_pdf(html_parts['toc'])
        # toc_reader = PdfReader(BytesIO(toc_pdf))
        # for i, page in enumerate(toc_reader.pages):
        #     numbered_page = add_page_number(page, current_page + i, format='roman')
        #     pdf_writer.add_page(numbered_page)
        # current_page += len(toc_reader.pages)
        
        # # C. COMMUNICATIONS PAR THÉMATIQUE (numérotation arabe)
        # for theme_name, communications in communications_by_theme.items():
        #     # Page de séparateur thématique
        #     theme_page_pdf = generate_theme_separator_pdf(theme_name)
        #     theme_reader = PdfReader(BytesIO(theme_page_pdf))
        #     for page in theme_reader.pages:
        #         numbered_page = add_page_number(page, current_page, format='arabic')
        #         pdf_writer.add_page(numbered_page)
        #         current_page += 1
            
        #     # PDF des communications
        #     for comm in communications:
        #         comm_pdf_path = get_communication_pdf(comm, book_type)
                
        #         if comm_pdf_path and os.path.exists(comm_pdf_path):
        #             comm_reader = PdfReader(comm_pdf_path)
                    
        #             for page_num, page in enumerate(comm_reader.pages):
        #                 # Appliquer le filigrane WIP si nécessaire
        #                 if book_type == 'resume' and comm.type == 'wip':
        #                     page = add_wip_watermark(page)
                        
        #                 # Ajouter numérotation
        #                 numbered_page = add_page_number(page, current_page, format='arabic')
        #                 pdf_writer.add_page(numbered_page)
        #                 current_page += 1
        #         else:
        #             # Page placeholder si PDF manquant
        #             placeholder_pdf = generate_placeholder_pdf(comm)
        #             placeholder_reader = PdfReader(BytesIO(placeholder_pdf))
        #             for page in placeholder_reader.pages:
        #                 numbered_page = add_page_number(page, current_page, format='arabic')
        #                 pdf_writer.add_page(numbered_page)
        #                 current_page += 1
        
        # # D. INDEX DES AUTEURS (continuation numérotation arabe)
        # index_pdf = html_to_pdf(html_parts['index'])
        # index_reader = PdfReader(BytesIO(index_pdf))
        # for page in index_reader.pages:
        #     numbered_page = add_page_number(page, current_page, format='arabic')
        #     pdf_writer.add_page(numbered_page)
        #     current_page += 1
        
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
    
    # NOUVELLES SECTIONS (dans l'ordre LaTeX)
    parts['remerciements'] = generate_remerciements_html(config)
    parts['comite_organisation'] = generate_comite_organisation_html(config)
    parts['reviewers'] = generate_reviewers_html(config)
    parts['introduction'] = generate_introduction_html(config)
    parts['prix_biot_fourier'] = generate_prix_biot_fourier_html(config)
    
    # TABLE DES MATIÈRES
    parts['toc'] = generate_toc_html(communications_by_theme, page_mapping)
    
    # INDEX DES AUTEURS
    parts['index'] = generate_index_html(authors_index)
    
    return parts

# def generate_book_html_parts(title, communications_by_theme, authors_index, page_mapping, book_type):
#     """Génère les parties HTML du livre (couverture, TOC, index)."""
#     config = get_conference_config()
    
#     parts = {}
    
#     # COUVERTURE
#     parts['cover'] = generate_cover_only_html(title, config)
    
#     # TABLE DES MATIÈRES
#     parts['toc'] = generate_toc_html(communications_by_theme, page_mapping)
    
#     # INDEX DES AUTEURS
#     parts['index'] = generate_index_html(authors_index)
    
#     return parts

def generate_cover_only_html(title, config):
    """Page de garde conforme au template SFT."""
    
    # Garder la logique existante
    presidents_names = get_presidents_names(config)
    livre_titre, livre_type = get_book_title_type(title)
    
    # Nouvelles données pour template SFT
    theme = config.get('conference', {}).get('theme', 'Thermique')
    congress_name = config.get('conference', {}).get('series', 'Congrès')
    organizing_lab = config.get('conference', {}).get('organizing_lab', {})
    
    # Format organisateur SFT
    lab_name = organizing_lab.get('short_name', 'LEMTA')
    lab_umr = organizing_lab.get('umr', '7563')
    lab_university = organizing_lab.get('university', 'Université de Lorraine')
    organizer_text = f"{lab_name} (UMR {lab_umr} - {lab_university})"
    
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
        <div class="cover-theme-line">{theme}</div>
        <div style="flex: 0.3;"></div>
        {f'<div class="cover-authors">{presidents_names}</div>' if presidents_names else ''}
        <div style="flex: 1;"></div>
        <div class="cover-actes">{livre_titre}</div>
        <div class="cover-du">{livre_type}</div>
<div class="cover-congres-title">
    Congrès Annuel de la<br>
    Société Française de Thermique
</div>
        <div style="flex: 1;"></div>
        <div class="cover-event-code">{config['conference']['short_name']}</div>
        <div style="flex: 1;"></div>
        <div class="cover-dates">{config.get('dates', {}).get('dates', '20 juillet 2026')}</div>
        <div class="cover-location">{config['location']['city']}</div>
        <div style="flex: 1;"></div>
        <div class="cover-organise">Organisé par</div>
        <div class="cover-organizer">{organizer_text}</div>
    </div>
</body>
</html>
"""


def get_presidents_names(config):
    """Extrait les présidents depuis conference.yml."""
    # Chercher dans conference.presidents (structure actuelle)
    presidents_list = config.get('conference', {}).get('presidents', [])
    
    # Alternative : chercher dans organizing.presidents  
    if not presidents_list:
        organizing = config.get('organizing', {})
        presidents_list = organizing.get('presidents', [])
    
    # Alternative : chercher dans contacts.program.presidents
    if not presidents_list:
        contacts = config.get('contacts', {})
        program = contacts.get('program', {})
        presidents_list = program.get('presidents', [])
    
    names = []
    for president in presidents_list:
        if isinstance(president, dict):
            name = president.get('name', '')
            if not name:
                # Essayer first_name + last_name
                first = president.get('first_name', '')
                last = president.get('last_name', '')
                name = (first + " " + last).strip()
            if name:
                # Mettre le nom de famille en majuscules
                parts = name.split()
                if len(parts) >= 2:
                    # Dernier mot = nom de famille en majuscules
                    parts[-1] = parts[-1].upper()
                    name = ' '.join(parts)
                names.append(name)
        elif isinstance(president, str):
            names.append(president)
    
    if not names:
        return ""
    
    # Format académique : une ligne par nom
    return "<br>".join(names)

def get_book_css():
    """CSS reproduisant le style LaTeX SFT."""
    return """
        @page {
            size: A4;
            margin: 0;
        }
        
        body {
            font-family: "Helvetica Neue Light","Helvetica Neue", Helvetica, Arial, sans-serif;
            font-weight: 300;
            margin: 0;
            padding: 0;
        }
        
        .cover-page {
            width: 210mm;
            height: 297mm;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            padding: 15mm 25mm 30mm 25mm;
            box-sizing: border-box;
            font-variant: small-caps;
        }
        
        .cover-theme-line {
            font-size: 20.74pt;
            font-weight: 400;
            margin-bottom: 0;
        }
        
        .cover-authors {
            font-size: 12pt;
            font-weight: normal;
            line-height: 1.4;
            font-variant: normal;
        }
        
        .cover-actes {
            font-size: 24.88pt;
            font-weight: bold;
            margin-bottom: 0.3em;
        }
        
        .cover-du {
            font-size: 12pt;
            margin: 1em 0;
        }
        
        .cover-congres-title {
            font-size: 24.88pt;
            font-weight: normal;
            line-height: 1.1;
        }
        
        .cover-event-code {
            font-size: 24.88pt;
            font-weight: bold;
        }
        
        .cover-dates, .cover-location {
            font-size: 17.28pt;
            font-variant: normal;
        }
        
        .cover-organise {
            font-size: 17.28pt;
            margin-bottom: 1em;
        }
        
        .cover-organizer {
            font-size: 12pt;
            font-variant: normal;
            line-height: 1.4;
        }
    """
def generate_remerciements_html(config):
    """Génère la page de remerciements."""
    try:
        # Charger depuis remerciements.yml
        from .config_loader import ConfigLoader
        config_loader = ConfigLoader()
        content_dir = config_loader.config_dir
        
        import yaml
        remerciements_file = content_dir / "remerciements.yml"
        
        if remerciements_file.exists():
            with open(remerciements_file, 'r', encoding='utf-8') as f:
                remerciements_data = yaml.safe_load(f)
        else:
            # Contenu par défaut
            remerciements_data = {
                'title': 'Remerciements',
                'content': 'Le Comité d\'organisation remercie tous les participants.',
                'signature': 'Le Comité d\'organisation'
            }
        
        # Remplacer les variables
        content = remerciements_data['content']
        signature = remerciements_data['signature']
        
        # Variables de remplacement
        variables = {
            'CONFERENCE_NAME': config.get('conference', {}).get('name', ''),
            'CONFERENCE_SHORT_NAME': config.get('conference', {}).get('short_name', ''),
            'ORGANIZATION_NAME': config.get('conference', {}).get('organizer', {}).get('name', '')
        }
        
        for var, value in variables.items():
            content = content.replace('{' + var + '}', value)
            signature = signature.replace('{' + var + '}', value)
        
        return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{remerciements_data['title']}</title>
    <style>{get_book_css()}</style>
</head>
<body>
    <div class="chapter-page">
        <h1 class="chapter-title">{remerciements_data['title']}</h1>
        <div class="chapter-content">
            <div class="remerciements-text">
                {content.replace(chr(10), '<br>').replace('•', '&bull;')}
            </div>
            <div class="signature">
                {signature.replace(chr(10), '<br>')}
            </div>
        </div>
    </div>
</body>
</html>
"""
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération remerciements: {e}")
        return "<html><body><p>Erreur chargement remerciements</p></body></html>"

def generate_comite_organisation_html(config):
    """Génère la page du comité d'organisation."""
    try:
        # Utiliser la même logique que la page /organisation
        def load_csv_data(filename):
            """Charge les données depuis un fichier CSV."""
            import csv
            import os
            csv_path = os.path.join(current_app.root_path, 'static', 'content', filename)
            if not os.path.exists(csv_path):
                return []
                
            data = []
            try:
                with open(csv_path, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file, delimiter=';')
                    for row in reader:
                        cleaned_row = {k.strip(): v.strip() for k, v in row.items()}
                        data.append(cleaned_row)
            except Exception as e:
                current_app.logger.error(f"Erreur chargement {filename}: {e}")
                return []
            return data
        
        # Charger les données
        organizing_members = load_csv_data('comite_local.csv')
        scientific_members = load_csv_data('comite_sft.csv')
        
        # Séparer présidents et membres
        presidents = []
        members = []
        
        for member in organizing_members:
            member_data = {
                'name': member.get('nom', ''),
                'role': member.get('role', ''),
                'institution': member.get('institution', '')
            }
            
            if member.get('role', '').lower() in ['président', 'president', 'présidente']:
                presidents.append(member_data)
            else:
                members.append(member_data)
        
        # Construire le HTML
        presidents_html = ""
        if presidents:
            presidents_html = "<h3>Président :</h3><ul>"
            for president in presidents:
                presidents_html += f"<li><strong>{president['name']}</strong>"
                if president['institution']:
                    presidents_html += f" - {president['institution']}"
                presidents_html += "</li>"
            presidents_html += "</ul>"
        
        members_html = ""
        if members:
            members_html = "<h3>Membres :</h3><ul>"
            for member in members:
                members_html += f"<li><strong>{member['name']}</strong>"
                if member['role']:
                    members_html += f" - {member['role']}"
                if member['institution']:
                    members_html += f" ({member['institution']})"
                members_html += "</li>"
            members_html += "</ul>"
        
        return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Comité d'organisation</title>
    <style>{get_book_css()}</style>
</head>
<body>
    <div class="chapter-page">
        <h1 class="chapter-title">Comité d'organisation</h1>
        <div class="chapter-content">
            <h2>Équipe locale</h2>
            <p>Le congrès {config.get('conference', {}).get('name', '')} s'est organisé par l'équipe locale du {config.get('conference', {}).get('organizing_lab', {}).get('name', '')}.</p>
            
            {presidents_html}
            {members_html}
        </div>
    </div>
</body>
</html>
"""
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération comité organisation: {e}")
        return "<html><body><p>Erreur chargement comité d'organisation</p></body></html>"

def generate_reviewers_html(config):
    """Génère le tableau des reviewers."""
    try:
        from .models import User, CommunicationReview
        
        # Récupérer tous les reviewers (utilisateurs ayant fait des reviews)
        reviewers = db.session.query(User).join(CommunicationReview).distinct().all()
        
        # Trier par nom de famille
        reviewers_sorted = sorted(reviewers, key=lambda x: x.last_name or x.email)
        
        reviewers_html = ""
        if reviewers_sorted:
            # Organiser en colonnes
            reviewers_html = '<div class="reviewers-grid">'
            for reviewer in reviewers_sorted:
                name = f"{reviewer.first_name or ''} {reviewer.last_name or ''}".strip()
                if not name:
                    name = reviewer.email
                
                institution = reviewer.institution or ""
                
                reviewers_html += f'<div class="reviewer-entry">'
                reviewers_html += f'<strong>{name}</strong>'
                if institution:
                    reviewers_html += f'<br><small>{institution}</small>'
                reviewers_html += f'</div>'
            
            reviewers_html += '</div>'
        else:
            reviewers_html = "<p>Liste des reviewers en cours de constitution.</p>"
        
        return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Tableau des reviewers</title>
    <style>
    {get_book_css()}
    .reviewers-grid {{
        columns: 3;
        column-gap: 20pt;
        column-fill: balance;
        margin-top: 1em;
    }}
    .reviewer-entry {{
        break-inside: avoid;
        margin-bottom: 1em;
        font-size: 11pt;
    }}
    </style>
</head>
<body>
    <div class="chapter-page">
        <h1 class="chapter-title">Tableau des reviewers</h1>
        <div class="chapter-content">
            <p>Le comité d'organisation adresse de très vifs remerciements aux relecteurs qui ont pris le temps de lire et d'expertiser les articles soumis au congrès.</p>
            
            {reviewers_html}
        </div>
    </div>
</body>
</html>
"""
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération reviewers: {e}")
        return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Tableau des reviewers</title>
    <style>{get_book_css()}</style>
</head>
<body>
    <div class="chapter-page">
        <h1 class="chapter-title">Tableau des reviewers</h1>
        <div class="chapter-content">
            <p>Le comité d'organisation adresse de très vifs remerciements aux relecteurs qui ont pris le temps de lire et d'expertiser les articles soumis au congrès.</p>
            <p><em>Liste des reviewers en cours de constitution.</em></p>
        </div>
    </div>
</body>
</html>
"""

def generate_introduction_html(config):
    """Génère la page d'introduction."""
    try:
        # Charger depuis introduction.yml
        from .config_loader import ConfigLoader
        config_loader = ConfigLoader()
        content_dir = config_loader.config_dir
        
        import yaml
        introduction_file = content_dir / "introduction.yml"
        
        if introduction_file.exists():
            with open(introduction_file, 'r', encoding='utf-8') as f:
                intro_data = yaml.safe_load(f)
        else:
            # Contenu par défaut
            intro_data = {
                'title': 'Introduction',
                'content': 'Bienvenue au congrès.',
                'signature': 'Le Comité d\'organisation'
            }
        
        # Compter les communications pour les statistiques
        from .models import Communication, CommunicationStatus
        total_communications = Communication.query.filter_by(status=CommunicationStatus.ACCEPTED).count()
        
        # Variables de remplacement
        content = intro_data['content']
        signature = intro_data['signature']
        
        variables = {
            'CONFERENCE_NAME': config.get('conference', {}).get('name', ''),
            'CONFERENCE_SHORT_NAME': config.get('conference', {}).get('short_name', ''),
            'CONFERENCE_EDITION': config.get('conference', {}).get('edition', ''),
            'CONFERENCE_THEME': config.get('conference', {}).get('theme', ''),
            'CONFERENCE_LOCATION': config.get('location', {}).get('city', ''),
            'CONFERENCE_DATES': config.get('dates', {}).get('dates', ''),
            'ORGANIZATION_NAME': config.get('conference', {}).get('organizer', {}).get('name', ''),
            'TOTAL_COMMUNICATIONS': str(total_communications)
        }
        
        for var, value in variables.items():
            content = content.replace('{' + var + '}', value)
            signature = signature.replace('{' + var + '}', value)
        
        return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{intro_data['title']}</title>
    <style>{get_book_css()}</style>
</head>
<body>
    <div class="chapter-page">
        <h1 class="chapter-title">{intro_data['title']}</h1>
        <div class="chapter-content">
            <div class="introduction-text">
                {content.replace(chr(10), '<br>')}
            </div>
            <div class="signature">
                {signature.replace(chr(10), '<br>')}
            </div>
        </div>
    </div>
</body>
</html>
"""
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération introduction: {e}")
        return "<html><body><p>Erreur chargement introduction</p></body></html>"   

def generate_prix_biot_fourier_html(config):
    """Génère la page des prix Biot-Fourier."""
    try:
        from .models import Communication, Review
        
        # Récupérer les communications sélectionnées pour l'audition
        audition_candidates = Communication.query.filter_by(
            biot_fourier_audition_selected=True
        ).all()
        
        candidates_html = ""
        
        if audition_candidates:
            candidates_html = f'<p>{len(audition_candidates)} contributions ont été présélectionnées pour le Prix Biot-Fourier. Les auteurs présenteront leurs travaux à l\'occasion de sessions orales.</p>'
            candidates_html += '<p>Le Prix Biot-Fourier sera attribué en fonction des rapports d\'expertise et de la qualité des présentations orales.</p>'
            candidates_html += '<div class="candidates-list">'
            
            for candidate in audition_candidates:
                authors_str = ", ".join([
                    f"{'<u>' if i == 0 else ''}{a.first_name} {a.last_name}{'</u>' if i == 0 else ''}" 
                    for i, a in enumerate(candidate.authors)
                ])
                
                # Récupérer les affiliations des auteurs
                affiliations = []
                for author in candidate.authors:
                    if author.institution and author.institution not in affiliations:
                        affiliations.append(author.institution)
                
                affiliations_str = "<br>".join([f"$^{{{i+1}}}$ {aff}" for i, aff in enumerate(affiliations)])
                
                candidates_html += f'''
                <div class="candidate-entry">
                    <h4>{candidate.title}</h4>
                    <p class="authors">{authors_str}</p>
                    {f'<p class="affiliations">{affiliations_str}</p>' if affiliations else ''}
                    <p class="reference">(Cf. page référence)</p>
                </div>
                <hr>
                '''
            
            candidates_html += '</div>'
        else:
            candidates_html = '<p>Les communications sélectionnées pour le Prix Biot-Fourier seront annoncées prochainement.</p>'
        
        return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Prix Biot-Fourier</title>
    <style>
    {get_book_css()}
    .candidates-list {{
        margin-top: 2em;
    }}
    .candidate-entry {{
        margin-bottom: 1.5em;
    }}
    .candidate-entry h4 {{
        margin-bottom: 0.5em;
        font-size: 14pt;
        font-weight: bold;
    }}
    .authors {{
        margin-bottom: 0.3em;
        font-size: 12pt;
    }}
    .affiliations {{
        font-size: 10pt;
        margin-bottom: 0.5em;
        color: #666;
    }}
    .reference {{
        font-style: italic;
        color: #666;
        margin-bottom: 0;
        font-size: 11pt;
    }}
    hr {{
        margin: 1.5em 0;
        border: none;
        border-top: 1px solid #ccc;
    }}
    </style>
</head>
<body>
    <div class="chapter-page">
        <h1 class="chapter-title">Prix Biot-Fourier</h1>
        <div class="chapter-content">
            {candidates_html}
        </div>
    </div>
</body>
</html>
"""
        
    except Exception as e:
        current_app.logger.error(f"Erreur génération prix Biot-Fourier: {e}")
        return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Prix Biot-Fourier</title>
    <style>{get_book_css()}</style>
</head>
<body>
    <div class="chapter-page">
        <h1 class="chapter-title">Prix Biot-Fourier</h1>
        <div class="chapter-content">
            <p>Les communications sélectionnées pour le Prix Biot-Fourier seront annoncées prochainement.</p>
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

def get_presidents_names_sft_format(config):
    """Extrait les présidents depuis conference.yml format SFT."""
    # Chercher dans organizing.presidents
    organizing = config.get('organizing', {})
    presidents_list = organizing.get('presidents', [])
    
    # Alternative : chercher dans conference.presidents  
    if not presidents_list:
        presidents_list = config.get('conference', {}).get('presidents', [])
    
    # Alternative : chercher dans contacts.program.presidents
    if not presidents_list:
        contacts = config.get('contacts', {})
        program = contacts.get('program', {})
        presidents_list = program.get('presidents', [])
    
    names = []
    for president in presidents_list:
        if isinstance(president, dict):
            name = president.get('name', '')
            if not name:
                # Essayer first_name + last_name
                first = president.get('first_name', '')
                last = president.get('last_name', '')
                name = f"{first} {last}".strip()
            if name:
                names.append(name)
        elif isinstance(president, str):
            names.append(president)
    
    if not names:
        return ""
    
    # Format SFT : une ligne par nom
    return "<br>".join(names)


# def get_presidents_names(config):
#     """Récupère les noms des présidents."""
#     if 'presidents' in config.get('conference', {}) and config['conference']['presidents']:
#         return "<br>".join([p['name'] for p in config['conference']['presidents']])
#     else:
#         return "Jean-Baptiste Biot, Joseph Fourier"

def get_book_title_type_sft(title):
    """Détermine le titre selon les conventions SFT exactes."""
    title_lower = title.lower()
    
    if 'résumé' in title_lower or 'resume' in title_lower:
        return ("Recueil des résumés", "du")
    elif 'acte' in title_lower:
        return ("ACTES", "du") 
    elif 'tome' in title_lower:
        if 'tome 1' in title_lower or '1' in title_lower:
            return ("ACTES", "du")  # Tome 1
        elif 'tome 2' in title_lower or '2' in title_lower:
            return ("ACTES", "du")  # Tome 2  
        else:
            return ("ACTES", "du")
    else:
        return ("Recueil", "du")


def get_sft_exact_css():
    """CSS reproduisant EXACTEMENT le template LaTeX SFT (Computer Modern + espacements LaTeX)."""
    return """
        /* PAGE A4 EXACTE */
        @page {
            size: A4;
            margin: 0;
        }
        
        body {
            font-family: "Latin Modern Roman", "Computer Modern", "Times", serif;
            margin: 0;
            padding: 0;
            line-height: 1.2;
        }
        
        /* TITLEPAGE - reproduit \\begin{titlepage}\\center\\scshape */
        .titlepage {
            width: 210mm;
            height: 297mm;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            box-sizing: border-box;
            font-variant: small-caps;  /* reproduit \\scshape */
            padding: 30mm 25mm;
        }
        
        /* THÈME - reproduit \\LARGE */
        .theme-top {
            font-size: 17.28pt;  /* LaTeX \\LARGE = 17.28pt à 12pt de base */
            font-weight: normal;
            margin-bottom: 0;
            line-height: 1.2;
        }
        
        /* ESPACES FLEXIBLES - reproduisent \\vspace{\\stretch{1}} */
        .vspace-stretch-1 { flex: 1; }
        .vspace-stretch-2 { flex: 0.3; min-height: 10mm; }
        .vspace-stretch-3 { flex: 1; }
        .vspace-stretch-4 { flex: 1; }
        .vspace-stretch-5 { flex: 1; }
        
        /* PRÉSIDENTS - reproduit les lignes normales */
        .presidents-block {
            font-size: 12pt;
            font-weight: normal;
            line-height: 1.4;
            font-variant: normal;  /* Pas de small-caps pour les noms */
        }
        
        /* TITRE PRINCIPAL - reproduit {\\Huge\\bfseries Recueil des résumés\\\\} */
        .title-main {
            font-size: 24.88pt;  /* LaTeX \\Huge = 24.88pt à 12pt de base */
            font-weight: bold;
            line-height: 1.1;
            margin-bottom: 0.2em;
        }
        
        /* DU - reproduit vspace{1em} + du + vspace{1em} */
        .du-spacing {
            font-size: 12pt;
            font-weight: normal;
            margin: 1em 0;
        }
        
        /* CONGRÈS - reproduit {\\Huge Congrès Annuel de la\\\\ Société Française de Thermique\\\\} */
        .congress-title {
            font-size: 24.88pt;  /* \\Huge */
            font-weight: normal;
            line-height: 1.1;
            margin-bottom: 0;
        }
        
        /* CODE ÉVÉNEMENT - reproduit {\\Huge\\bfseries SFT 2021}\\\\ */
        .event-code {
            font-size: 24.88pt;  /* \\Huge */
            font-weight: bold;
            line-height: 1.1;
        }
        
        /* DATES ET LIEU - reproduit le format exact */
        .dates-location {
            font-size: 12pt;
            font-weight: normal;
            line-height: 1.3;
            font-variant: normal;
        }
        
        /* ORGANISÉ PAR - reproduit \\large Organisé par\\\\ */
        .organized-by {
            font-size: 14.4pt;  /* LaTeX \\large = 14.4pt à 12pt de base */
            font-weight: normal;
            margin-bottom: 1em;
        }
        
        /* ORGANISATEUR - reproduit \\normalsize nom du laboratoire */
        .organizer-name {
            font-size: 12pt;  /* \\normalsize */
            font-weight: normal;
            line-height: 1.4;
            font-variant: normal;
        }
        
        /* RESPONSIVE pour aperçu web */
        @media screen and (max-width: 800px) {
            .titlepage {
                width: 100vw;
                height: 140vw;
                padding: 8vw 4vw;
            }
            
            .theme-top { font-size: 4.5vw; }
            .title-main { font-size: 6.5vw; }
            .congress-title { font-size: 6.5vw; }
            .event-code { font-size: 6.5vw; }
            .dates-location { font-size: 3vw; }
            .organized-by { font-size: 3.5vw; }
            .organizer-name { font-size: 3vw; }
            .presidents-block { font-size: 3vw; }
        }
    """



def get_book_title_type(title):
    """Détermine le titre et type de livre selon la convention SFT."""
    title_lower = title.lower()
    
    if 'résumé' in title_lower or 'resume' in title_lower:
        return ("Recueil des résumés", "du")
    elif 'acte' in title_lower:
        return ("ACTES", "du") 
    elif 'tome' in title_lower:
        if 'tome 1' in title_lower:
            return ("ACTES - TOME 1", "du")
        elif 'tome 2' in title_lower:
            return ("ACTES - TOME 2", "du")
        else:
            return ("ACTES", "du")
    else:
        return ("Recueil", "du")

# def get_book_title_type(title):
#     """Détermine le titre et type de livre."""
#     if 'article' in title.lower():
#         return "ACTES", "du"
#     else:
#         return "RECUEIL DES RÉSUMÉS", "du"


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

# Ajoutez ceci AU DÉBUT de la fonction generate_book_latex
@books.route('/latex/<book_type>.pdf')
@login_required
def generate_book_latex(book_type):
    """Génère un livre PDF via compilation LaTeX."""
    
    # === LOGS FORCÉS ===
    print("=" * 60)
    print(f"DÉBUT GÉNÉRATION LIVRE {book_type}")
    print("=" * 60)
    
    if not current_user.is_admin:
        abort(403)
    
    if book_type not in ['tome1', 'tome2', 'resumes-wip']:
        abort(404)
    
    try:
        print(f"Récupération des communications pour {book_type}...")
        # Récupérer les communications
        communications = get_communications_by_type_and_status()
        
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
            print(f"Nombre de résumés: {len(communications['resumes'])}")
            print(f"Nombre de WIP: {len(communications['wips'])}")
            print(f"Total communications: {len(all_communications)}")
            title = "Résumés et Work in Progress"
            communications_data = group_communications_by_thematique(all_communications)
        
        print(f"Titre du livre: {title}")
        print(f"Nombre de thématiques: {len(communications_data)}")
        for theme, comms in communications_data.items():
            print(f"  - {theme}: {len(comms)} communications")
        
        print("Lancement de compile_latex_book...")
        # Générer et compiler le LaTeX
        pdf_path = compile_latex_book(title, communications_data, book_type)
        
        # Retourner le PDF
        config = get_conference_config()
        filename = f"{config.get('conference', {}).get('short_name', 'Conference')}_{title.replace(' ', '_')}.pdf"
        
        return send_file(pdf_path, as_attachment=True, download_name=filename, mimetype='application/pdf')
        
    except Exception as e:
        print(f"ERREUR DANS generate_book_latex: {e}")
        import traceback
        print(f"TRACEBACK: {traceback.format_exc()}")
        current_app.logger.error(f"Erreur génération LaTeX {book_type}: {e}")
        return f"Erreur lors de la génération du PDF: {str(e)}", 500

# @books.route('/latex/<book_type>.pdf')
# @login_required
# def generate_book_latex(book_type):
#     """Génère un livre PDF via compilation LaTeX."""
#     print("=" * 60)
#     print(f"DÉBUT GÉNÉRATION LIVRE {book_type}")
#     print("=" * 60)


#     if not current_user.is_admin:
#         abort(403)
    
#     if book_type not in ['tome1', 'tome2', 'resumes-wip']:
#         abort(404)
    
#     try:
#         # Récupérer les communications
#         communications = get_communications_by_type_and_status()
        
#         if book_type == 'tome1':
#             tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
#             title = "Articles - Tome 1"
#             communications_data = tomes_split['tome1']
#         elif book_type == 'tome2':
#             tomes_split = split_articles_for_tomes(communications['articles_acceptes'])
#             title = "Articles - Tome 2" 
#             communications_data = tomes_split['tome2']
#         else:  # resumes-wip
#             all_communications = communications['resumes'] + communications['wips']
#             title = "Résumés et Work in Progress"
#             communications_data = group_communications_by_thematique(all_communications)
        
#         # Générer et compiler le LaTeX
#         pdf_path = compile_latex_book(title, communications_data, book_type)
        
#         # Retourner le PDF
#         config = get_conference_config()
#         filename = f"{config.get('conference', {}).get('short_name', 'Conference')}_{title.replace(' ', '_')}.pdf"
        
#         return send_file(pdf_path, as_attachment=True, download_name=filename, mimetype='application/pdf')
        
#     except Exception as e:
#         current_app.logger.error(f"Erreur génération LaTeX {book_type}: {e}")
#         return f"Erreur lors de la génération du PDF: {str(e)}", 500


def compile_latex_book(title, communications_by_theme, book_type):
    """Compile un livre LaTeX et retourne l'URL relative du PDF généré (ex: static/uploads/...)."""
    import tempfile
    import subprocess
    import os
    import shutil
    import time
    from flask import current_app
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copier les fichiers de template LaTeX
        copy_latex_templates(temp_dir, title, book_type)
        
        # Générer le fichier .tex principal
        tex_content = generate_latex_content(title, communications_by_theme, book_type)
        tex_file = os.path.join(temp_dir, "livre.tex")
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(tex_content)

        # === DEBUT AJOUT DEBUG ===
        print("=== EXAMEN DU FICHIER LIVRE.TEX ===")
        print(f"Chemin du fichier: {tex_file}")

        # Lire et afficher les premières lignes du fichier livre.tex
        try:
            with open(tex_file, "r", encoding="utf-8") as f:
                content = f.read()
    
            print("--- DÉBUT DU FICHIER livre.tex ---")
            lines = content.split('\n')
    
            # Afficher les 20 premières lignes
            for i, line in enumerate(lines[:20]):
                print(f"{i+1:2d}: {line}")
    
            print("...")
    
            # Chercher les références aux comm_*.tex
            comm_references = [line for line in lines if 'comm_' in line and '.tex' in line]
            print(f"--- RÉFÉRENCES AUX COMMUNICATIONS ({len(comm_references)} trouvées) ---")
            for ref in comm_references[:10]:  # Premières 10
                print(f"    {ref.strip()}")
    
            # Chercher la partie problématique
            mainmatter_start = None
            for i, line in enumerate(lines):
                if '\\mainmatter' in line:
                    mainmatter_start = i
                    break
    
            if mainmatter_start:
                print(f"--- PARTIE MAINMATTER (lignes {mainmatter_start}-{mainmatter_start+15}) ---")
                for i in range(mainmatter_start, min(mainmatter_start + 15, len(lines))):
                    print(f"{i+1:2d}: {lines[i]}")
    
            print("=== FIN EXAMEN ===")
    
        except Exception as e:
            print(f"Erreur lors de la lecture du fichier: {e}")
        
        # Copier les fichiers debug
        debug_dir = os.path.join(current_app.root_path, "static", "uploads", "debug_latex")
        os.makedirs(debug_dir, exist_ok=True)

        debug_files = ['livre.tex', 'config.tex', 'page-garde.tex', 'Tableau_Reviewer.tex', 
                       'remerciements.tex', 'comite-organisation.tex', 'index_style.ist']
        for file in debug_files:
            src = os.path.join(temp_dir, file)
            if os.path.exists(src):
                shutil.copy2(src, debug_dir)
                current_app.logger.info(f"Fichier {file} copié vers debug_latex")
                    
        current_app.logger.info(f"Fichiers debug copiés vers: {debug_dir}")
        # === FIN AJOUT DEBUG ===
            
        # Copier les PDFs des communications
        copy_communication_pdfs(communications_by_theme, temp_dir, book_type)

        try:
            print("=== COMPILATION LATEX AVEC INDEX ===")
            
            # 1. Première compilation LaTeX
            print("1. Première compilation LaTeX...")
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "livre.tex"],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            
            # 2. Génération de l'index avec makeindex
            print("2. Génération de l'index avec makeindex...")
            idx_file = os.path.join(temp_dir, "livre.idx")
            if os.path.exists(idx_file):
                subprocess.run(
                    ["makeindex", "-s", "index_style.ist", "livre.idx"],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                print("✅ Index généré avec succès")
            else:
                print("⚠️ Fichier .idx non trouvé, index ignoré")
            
            # 3. Deuxième compilation LaTeX pour intégrer l'index
            print("3. Deuxième compilation LaTeX...")
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "livre.tex"],
                cwd=temp_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            
            print("✅ Compilation terminée avec succès")
        

            # Vérifier que le PDF a bien été généré
            pdf_source = os.path.join(temp_dir, "livre.pdf")
            if not os.path.exists(pdf_source):
                raise FileNotFoundError(f"PDF non généré : {pdf_source}")

            # Dossier uploads
            uploads_dir = os.path.join(current_app.root_path, "static", "uploads")
            os.makedirs(uploads_dir, exist_ok=True)

            # Nom final (ajout timestamp pour éviter les collisions)
            filename = f"latex_book_{book_type}_{int(time.time())}.pdf"
            pdf_dest = os.path.join(uploads_dir, filename)   # absolu
            pdf_web_path = f"static/uploads/{filename}"      # relatif web

            # Copier le PDF
            shutil.copy2(pdf_source, pdf_dest)

            current_app.logger.info(f"PDF généré avec succès: {pdf_web_path}")

            # ✅ Retour uniquement l'URL relative pour le front
            return pdf_web_path

        except subprocess.CalledProcessError as e:
            # Lire le log LaTeX pour aider au debug
            log_file = os.path.join(temp_dir, "livre.log")
            if os.path.exists(log_file):
                with open(log_file, "r") as f:
                    log_content = f.read()
                current_app.logger.error(f"Erreur LaTeX: {log_content[:2000]}...")

            raise Exception("Erreur compilation LaTeX — voir logs.")
    
# def compile_latex_book(title, communications_by_theme, book_type):
#     """Compile un livre LaTeX et retourne l'URL relative du PDF généré (ex: static/uploads/...)."""
#     import tempfile
#     import subprocess
#     import os
#     import shutil
#     import time
#     from flask import current_app
    
#     with tempfile.TemporaryDirectory() as temp_dir:
#         # Copier les fichiers de template LaTeX
#         copy_latex_templates(temp_dir, title, book_type)
#         # Générer le fichier .tex principal
#         tex_content = generate_latex_content(title, communications_by_theme, book_type)
#         tex_file = os.path.join(temp_dir, "livre.tex")
#         with open(tex_file, "w", encoding="utf-8") as f:
#             f.write(tex_content)

#         # === DEBUT AJOUT ===
#         print("=== EXAMEN DU FICHIER LIVRE.TEX ===")
#         print(f"Chemin du fichier: {tex_file}")

#         # Lire et afficher les premières lignes du fichier livre.tex
#         try:
#             with open(tex_file, "r", encoding="utf-8") as f:
#                 content = f.read()
    
#             print("--- DÉBUT DU FICHIER livre.tex ---")
#             lines = content.split('\n')
    
#             # Afficher les 20 premières lignes
#             for i, line in enumerate(lines[:20]):
#                 print(f"{i+1:2d}: {line}")
    
#             print("...")
    
#             # Chercher les références aux comm_*.tex
#             comm_references = [line for line in lines if 'comm_' in line and '.tex' in line]
#             print(f"--- RÉFÉRENCES AUX COMMUNICATIONS ({len(comm_references)} trouvées) ---")
#             for ref in comm_references[:10]:  # Premières 10
#                 print(f"    {ref.strip()}")
    
#             # Chercher la partie problématique
#             mainmatter_start = None
#             for i, line in enumerate(lines):
#                 if '\\mainmatter' in line:
#                     mainmatter_start = i
#                     break
    
#                 if mainmatter_start:
#                     print(f"--- PARTIE MAINMATTER (lignes {mainmatter_start}-{mainmatter_start+15}) ---")
#                 for i in range(mainmatter_start, min(mainmatter_start + 15, len(lines))):
#                     print(f"{i+1:2d}: {lines[i]}")
    
#                 print("=== FIN EXAMEN ===")
    
#         except Exception as e:
#             print(f"Erreur lors de la lecture du fichier: {e}")       
#             debug_dir = os.path.join(current_app.root_path, "static", "uploads", "debug_latex")
#             os.makedirs(debug_dir, exist_ok=True)

#             debug_files = ['livre.tex', 'config.tex', 'page-garde.tex', 'Tableau_Reviewer.tex' 
#                            'remerciements.tex', 'comite-organisation.tex', 'index_style.ist']
#         for file in debug_files:
#             src = os.path.join(temp_dir, file)
#             if os.path.exists(src):
#                 shutil.copy2(src, debug_dir)
#                 current_app.logger.info(f"Fichier {file} copié vers debug_latex")
                    
#         current_app.logger.info(f"Fichiers debug copiés vers: {debug_dir}")

            
#         # Copier les PDFs des communications
#         copy_communication_pdfs(communications_by_theme, temp_dir, book_type)

#         try:
#             # Deux compilations LaTeX pour stabiliser les références
#             for _ in range(2):
#                 subprocess.run(
#                     ["pdflatex", "-interaction=nonstopmode", "livre.tex"],
#                     cwd=temp_dir,
#                     check=True,
#                     capture_output=True,
#                     text=True,
#                 )


                
#             # Vérifier que le PDF a bien été généré
#             pdf_source = os.path.join(temp_dir, "livre.pdf")
#             if not os.path.exists(pdf_source):
#                 raise FileNotFoundError(f"PDF non généré : {pdf_source}")

#             # Dossier uploads
#             uploads_dir = os.path.join(current_app.root_path, "static", "uploads")
#             os.makedirs(uploads_dir, exist_ok=True)

#             # Nom final (ajout timestamp pour éviter les collisions)
#             filename = f"latex_book_{book_type}_{int(time.time())}.pdf"
#             pdf_dest = os.path.join(uploads_dir, filename)   # absolu
#             pdf_web_path = f"static/uploads/{filename}"      # relatif web

#             # Copier le PDF
#             shutil.copy2(pdf_source, pdf_dest)

#             current_app.logger.info(f"PDF généré avec succès: {pdf_web_path}")

#             # ✅ Retour uniquement l'URL relative pour le front
#             return pdf_web_path

#         except subprocess.CalledProcessError as e:
#             # Lire le log LaTeX pour aider au debug
#             log_file = os.path.join(temp_dir, "livre.log")
#             if os.path.exists(log_file):
#                 with open(log_file, "r") as f:
#                     log_content = f.read()
#                 current_app.logger.error(f"Erreur LaTeX: {log_content[:2000]}...")

#             raise Exception("Erreur compilation LaTeX — voir logs.")




def generate_latex_content(title, communications_by_theme, book_type):
    """Génère le contenu LaTeX principal basé sur les templates existants."""
    
    config = get_conference_config()
    title_l = title.lower()
    is_resume = (
        any(k in title_l for k in ("résumé", "resume", "resumé")) or
        (book_type.lower() in {"resume","resumes-wip","abstract","abstracts"})
    )
    part_title = "Résumé des communications" if is_resume else "Actes du congrès"


    # title_l = title.lower()

    
    # is_resume = any(k in title_l for k in ("résumé", "resume", "resumé")) or \
    #     (book_type in {"resume", "abstracts", "abstract"})
    # part_title = "Résumé des communications" if is_resume else "Actes du congrès"
    latex_content = f"""\\documentclass[12pt,a4paper, openright]{{book}}
%=====================================
%   WARNING
%   FICHIER AUTOMATISE - Conference Flow
%   NE PAS MODIFIER
%=====================================

\\input{{config.tex}}
\\begingroup\\shorthandoff{{:;}}
\\hypersetup{{
  pdfinfo={{
    Title={{{config.get('conference', {}).get('short_name', 'CONF')} - {title}}},
    Author={{Communauté {config.get('conference', {}).get('organizer', {}).get('short_name', 'CONF')}}},
    Subjects={{{config.get('conference', {}).get('name', 'Congrès')} - {config.get('location', {}).get('city', 'Ville')}}},
    Producer={{Conference Flow}},
    Creator={{{config.get('conference', {}).get('organizing_lab', {}).get('short_name', 'LAB')}}}
  }}
}}
\\endgroup

\\begin{{document}}
\\SetBgContents{{}}
\\pagestyle{{fancy}}
\\dominitoc
\\frontmatter
%
\\input{{./page-garde.tex}}
%
\\part{{Prolégomènes}}

 \\input{{./remerciements.tex}}
 \\cleardoublepage
 \\input{{./comite-organisation.tex}}
 \\cleardoublepage
 \\input{{./Tableau_Reviewer.tex}}
 \\cleardoublepage
 \\input{{./introduction.tex}}
 \\cleardoublepage
 \\input{{./prix-biot-fourier.tex}}

\\phantomsection
\\addcontentsline{{toc}}{{chapter}}{{Table des matières}}
\\tableofcontents
%
\\mainmatter

\\adjustmtc[+1]

\\part{{{part_title}}}
%
\\makeatletter
\\renewcommand{{\\@chapapp}}{{Thème}}
\\makeatother
"""

    # Ajouter les thématiques et communications
    theme_num = 1
    for theme_name, communications in communications_by_theme.items():
        if communications:
            current_app.logger.info(f"DEBUG: theme_name='{theme_name}' -> escaped='{escape_latex(theme_name)}'")
            latex_content += f"""
%%%%%%% THEME {theme_num} %%%%%
\\cleardoublepage
\\phantomsection
\\addcontentsline{{toc}}{{part}}{{Thème {theme_num}}}

            
\\chapter{{{escape_latex(theme_name)}}}

"""
            
            # Ajouter chaque communication
            for comm in communications:
                comm_filename = f"comm_{comm.id}"
                latex_content += f"\\input{{{comm_filename}.tex}}\n"
                latex_content += f"\\includepdf[pages=-,pagecommand={{\\thispagestyle{{fancy}}}},width=1.05\\paperwidth]{{{comm_filename}.pdf}}\n"
            
            theme_num += 1
    
    # Fin du document
    latex_content += """
% Index des auteurs
\\cleardoublepage
\\phantomsection
\\addcontentsline{toc}{chapter}{Index des auteurs}
\\printindex

\\end{document}
"""
    return latex_content

def copy_communication_pdfs(communications_by_theme, temp_dir, book_type):
    """Copie les PDFs des communications vers le répertoire temporaire."""
    print("=" * 60)
    print("DEBUG: TYPES DE FICHIERS DISPONIBLES")
    print("=" * 60)
    
    for theme_name, communications in communications_by_theme.items():
        print(f"\n--- THÈME: {theme_name} ---")
        for comm in communications:
            print(f"Communication {comm.id}: {comm.title[:50]}...")
            
            # Lister tous les fichiers disponibles
            if hasattr(comm, 'submission_files') and comm.submission_files:
                print(f"  Types de fichiers disponibles:")
                for file in comm.submission_files:
                    print(f"    - {file.file_type}: {file.original_filename}")
            else:
                print("  ⚠️ AUCUN FICHIER TROUVÉ")
    
    print("=" * 60)




    current_app.logger.info(f"=== DEBUT copy_communication_pdfs ===")
    current_app.logger.info(f"temp_dir: {temp_dir}")
    current_app.logger.info(f"book_type: {book_type}")
    current_app.logger.info(f"Nombre de thématiques: {len(communications_by_theme)}")
    
    import os
    import shutil
    
    total_communications = 0
    files_created = 0
    
    for theme_name, communications in communications_by_theme.items():
        current_app.logger.info(f"--- Thématique: {theme_name} ---")
        current_app.logger.info(f"Nombre de communications dans cette thématique: {len(communications)}")
        
        for i, comm in enumerate(communications):
            current_app.logger.info(f"Communication {i+1}/{len(communications)}: ID={comm.id}, Titre='{comm.title[:50]}...'")
            total_communications += 1
            
            # Récupérer le PDF de la communication
            pdf_path = get_communication_pdf(comm, book_type)
            current_app.logger.info(f"Chemin PDF pour comm {comm.id}: {pdf_path}")
            
            if pdf_path and os.path.exists(pdf_path):
                current_app.logger.info(f"✅ PDF existe: {pdf_path}")
                # Copier avec un nom standardisé
                dest_filename = f"comm_{comm.id}.pdf"
                dest_path = os.path.join(temp_dir, dest_filename)
                shutil.copy2(pdf_path, dest_path)
                current_app.logger.info(f"✅ PDF copié vers: {dest_path}")
                
                # Générer aussi un fichier .tex minimal pour cette communication
                current_app.logger.info(f"Génération du fichier .tex pour comm {comm.id}...")
                generate_communication_tex(comm, temp_dir)
                
                # Vérifier que le fichier .tex a été créé
                tex_path = os.path.join(temp_dir, f"comm_{comm.id}.tex")
                if os.path.exists(tex_path):
                    current_app.logger.info(f"✅ Fichier .tex créé: {tex_path}")
                    files_created += 1
                else:
                    current_app.logger.error(f"❌ Fichier .tex NON créé: {tex_path}")
                
            else:
                current_app.logger.warning(f"⚠️ PDF manquant pour communication {comm.id}: {comm.title}")
                # Créer un placeholder
                current_app.logger.info(f"Création d'un placeholder pour comm {comm.id}...")
                create_placeholder_tex(comm, temp_dir)
                
                # Vérifier que le placeholder a été créé
                tex_path = os.path.join(temp_dir, f"comm_{comm.id}.tex")
                if os.path.exists(tex_path):
                    current_app.logger.info(f"✅ Placeholder .tex créé: {tex_path}")
                    files_created += 1
                else:
                    current_app.logger.error(f"❌ Placeholder .tex NON créé: {tex_path}")
    
    current_app.logger.info(f"=== RÉSUMÉ copy_communication_pdfs ===")
    current_app.logger.info(f"Total communications traitées: {total_communications}")
    current_app.logger.info(f"Fichiers .tex créés: {files_created}")
    
    # Lister tous les fichiers comm_*.tex créés
    tex_files = [f for f in os.listdir(temp_dir) if f.startswith('comm_') and f.endswith('.tex')]
    current_app.logger.info(f"Fichiers comm_*.tex trouvés: {tex_files}")
    
    current_app.logger.info(f"=== FIN copy_communication_pdfs ===")

# def copy_communication_pdfs(communications_by_theme, temp_dir, book_type):
#     """Copie les PDFs des communications vers le répertoire temporaire."""
#     import os
#     import shutil
    
#     for theme_name, communications in communications_by_theme.items():
#         for comm in communications:
#             # Récupérer le PDF de la communication
#             pdf_path = get_communication_pdf(comm, book_type)
#             if pdf_path and os.path.exists(pdf_path):
#                 # Copier avec un nom standardisé
#                 dest_filename = f"comm_{comm.id}.pdf"
#                 dest_path = os.path.join(temp_dir, dest_filename)
#                 shutil.copy2(pdf_path, dest_path)
                
#                 # Générer aussi un fichier .tex minimal pour cette communication
#                 generate_communication_tex(comm, temp_dir)
#             else:
#                 current_app.logger.warning(f"PDF manquant pour communication {comm.id}: {comm.title}")
#                 # Créer un placeholder
#                 create_placeholder_tex(comm, temp_dir)

def generate_communication_tex(comm, temp_dir):
    """Génère un fichier .tex minimal pour une communication."""
    current_app.logger.info(f"Génération fichier .tex pour communication {comm.id}")
    
    # Échapper le titre pour les références techniques
    escaped_title = escape_latex(comm.title)
    index_entries = []
    
    # Générer les entrées d'index pour les auteurs
    for author in comm.authors:
        first_name = author.first_name or ""
        last_name = author.last_name or ""
        
        if first_name or last_name:
            # Créer l'entrée d'index : \index{nomprenom@Prenom, Nom}
            clean_last = last_name.replace(' ', '').replace('-', '')
            clean_first = first_name.replace(' ', '').replace('-', '')
            index_key = f"{clean_last}{clean_first}"
            index_display = f"{first_name}, {last_name}" if last_name else first_name
            
            index_entries.append(f"\\index{{{index_key}@{escape_latex(index_display)}}}")
    
    # Contenu technique uniquement (pas d'affichage visuel)
    tex_content = f"""
% Communication {comm.id} - Références techniques uniquement
% Index des auteurs
"""
    
    # Ajouter toutes les entrées d'index
    for entry in index_entries:
        tex_content += f"{entry}\n"
    
    # Références pour la table des matières et les liens croisés
    tex_content += f"""
% Références pour TOC et liens croisés (pas d'affichage visuel)
\\phantomsection\\addtocounter{{section}}{{1}}
\\addcontentsline{{toc}}{{section}}{{{escaped_title}}}
\\label{{ref:{comm.id}}}

% Le titre et les auteurs sont déjà dans le PDF intégré

"""
    
    tex_filename = f"comm_{comm.id}.tex"
    tex_path = os.path.join(temp_dir, tex_filename)
    
    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(tex_content)
    
    current_app.logger.info(f"✅ Fichier {tex_filename} créé avec {len(index_entries)} entrées d'index (mode technique)")


def create_placeholder_tex(comm, temp_dir):
    """Crée un fichier .tex placeholder pour une communication sans PDF."""
    current_app.logger.info(f"Création placeholder pour communication {comm.id}")
    
    # Échapper le titre et les noms d'auteurs
    escaped_title = escape_latex(comm.title)
    escaped_authors = []
    index_entries = []
    
    # Générer les entrées d'index pour les auteurs
    for author in comm.authors:
        first_name = author.first_name or ""
        last_name = author.last_name or ""
        
        escaped_first = escape_latex(first_name)
        escaped_last = escape_latex(last_name)
        
        name = f"{escaped_first} {escaped_last}".strip()
        if name:
            escaped_authors.append(name)
            
            # Créer l'entrée d'index
            clean_last = last_name.replace(' ', '').replace('-', '')
            clean_first = first_name.replace(' ', '').replace('-', '')
            index_key = f"{clean_last}{clean_first}"
            index_display = f"{first_name}, {last_name}" if last_name else first_name
            
            index_entries.append(f"\\index{{{index_key}@{escape_latex(index_display)}}}")
    
    authors_str = ", ".join(escaped_authors) if escaped_authors else "Auteur non spécifié"
    
    # Pour les placeholders, on affiche quand même le titre/auteurs car il n'y a pas de PDF
    tex_content = f"""
% Communication {comm.id} - PLACEHOLDER (PDF manquant)
% Index des auteurs
"""
    
    # Ajouter toutes les entrées d'index
    for entry in index_entries:
        tex_content += f"{entry}\n"
    
    tex_content += f"""
\\phantomsection\\addtocounter{{section}}{{1}}
\\addcontentsline{{toc}}{{section}}{{{escaped_title}}}
{{\\Large \\textbf{{{escaped_title}}}}}\\label{{ref:{comm.id}}}

\\vspace{{2mm}}
{authors_str}
\\vspace{{4mm}}

\\textit{{[Document PDF non disponible]}}

\\vspace{{4mm}}

"""
    
    tex_filename = f"comm_{comm.id}.tex"
    tex_path = os.path.join(temp_dir, tex_filename)
    
    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(tex_content)
    
    current_app.logger.info(f"✅ Placeholder {tex_filename} créé avec {len(index_entries)} entrées d'index")

# def generate_communication_tex(comm, temp_dir):
#     """Génère un fichier .tex minimal pour une communication."""
#     current_app.logger.info(f"Génération fichier .tex pour communication {comm.id}")
    
#     # Échapper le titre et les noms d'auteurs
#     escaped_title = escape_latex(comm.title)
#     escaped_authors = []
#     index_entries = []
    
#     for author in comm.authors:
#         first_name = author.first_name or ""
#         last_name = author.last_name or ""
        
#         escaped_first = escape_latex(first_name)
#         escaped_last = escape_latex(last_name)
        
#         name = f"{escaped_first} {escaped_last}".strip()
#         if name:
#             escaped_authors.append(name)
            
#             # Créer l'entrée d'index : \index{nomprenom@Prenom, Nom}
#             # Nettoyer les noms pour l'index (sans caractères LaTeX spéciaux)
#             clean_last = last_name.replace(' ', '').replace('-', '')
#             clean_first = first_name.replace(' ', '').replace('-', '')
#             index_key = f"{clean_last}{clean_first}"
#             index_display = f"{first_name}, {last_name}" if last_name else first_name
            
#             index_entries.append(f"\\index{{{index_key}@{escape_latex(index_display)}}}")
    
#     authors_str = ", ".join(escaped_authors) if escaped_authors else "Auteur non spécifié"
    
#     # Contenu avec entrées d'index
#     tex_content = f"""
# % Communication {comm.id}
# % Index des auteurs
# """
    
#     # Ajouter toutes les entrées d'index
#     for entry in index_entries:
#         tex_content += f"{entry}\n"
    
#     tex_content += f"""
# \\phantomsection\\addtocounter{{section}}{{1}}
# \\addcontentsline{{toc}}{{section}}{{{escaped_title}}}
# {{\\Large \\textbf{{{escaped_title}}}}}\\label{{ref:{comm.id}}}

# \\vspace{{2mm}}
# {authors_str}
# \\vspace{{4mm}}

# """
    
#     tex_filename = f"comm_{comm.id}.tex"
#     tex_path = os.path.join(temp_dir, tex_filename)
    
#     with open(tex_path, 'w', encoding='utf-8') as f:
#         f.write(tex_content)
    
#     current_app.logger.info(f"✅ Fichier {tex_filename} créé avec {len(index_entries)} entrées d'index")


def create_placeholder_tex(comm, temp_dir):
    """Crée un fichier .tex placeholder pour une communication sans PDF."""
    current_app.logger.info(f"Création placeholder pour communication {comm.id}")
    
    # Échapper le titre et les noms d'auteurs
    escaped_title = escape_latex(comm.title)
    escaped_authors = []
    index_entries = []
    
    for author in comm.authors:
        first_name = author.first_name or ""
        last_name = author.last_name or ""
        
        escaped_first = escape_latex(first_name)
        escaped_last = escape_latex(last_name)
        
        name = f"{escaped_first} {escaped_last}".strip()
        if name:
            escaped_authors.append(name)
            
            # Créer l'entrée d'index : \index{nomprenom@Prenom, Nom}
            clean_last = last_name.replace(' ', '').replace('-', '')
            clean_first = first_name.replace(' ', '').replace('-', '')
            index_key = f"{clean_last}{clean_first}"
            index_display = f"{first_name}, {last_name}" if last_name else first_name
            
            index_entries.append(f"\\index{{{index_key}@{escape_latex(index_display)}}}")
    
    authors_str = ", ".join(escaped_authors) if escaped_authors else "Auteur non spécifié"
    
    # Contenu du placeholder avec entrées d'index
    tex_content = f"""
% Communication {comm.id} - PLACEHOLDER (PDF manquant)
% Index des auteurs
"""
    
    # Ajouter toutes les entrées d'index
    for entry in index_entries:
        tex_content += f"{entry}\n"
    
    tex_content += f"""
\\phantomsection\\addtocounter{{section}}{{1}}
\\addcontentsline{{toc}}{{section}}{{{escaped_title}}}
{{\\Large \\textbf{{{escaped_title}}}}}\\label{{ref:{comm.id}}}

\\vspace{{2mm}}
{authors_str}
\\vspace{{4mm}}

\\textit{{[Document PDF non disponible]}}

\\vspace{{4mm}}

"""
    
    tex_filename = f"comm_{comm.id}.tex"
    tex_path = os.path.join(temp_dir, tex_filename)
    
    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(tex_content)
    
    current_app.logger.info(f"✅ Placeholder {tex_filename} créé avec {len(index_entries)} entrées d'index")


# def generate_communication_tex(comm, temp_dir):
#     """Génère un fichier .tex minimal pour une communication."""
#     # Échapper le titre et les noms d'auteurs
#     escaped_title = escape_latex(comm.title)
#     escaped_authors = []
#     for author in comm.authors:
#         escaped_first = escape_latex(author.first_name)
#         escaped_last = escape_latex(author.last_name)
#         escaped_authors.append(f"{escaped_first} {escaped_last}")
    
#     authors_str = ", ".join(escaped_authors)
    
#     tex_content = f"""
# % Communication {comm.id}
# \\phantomsection\\addtocounter{{section}}{{1}}
# \\addcontentsline{{toc}}{{section}}{{{escaped_title}}}
# {{\\Large \\textbf{{{escaped_title}}}}}\\label{{ref:{comm.id}}}

# \\vspace{{2mm}}
# {authors_str}
# \\vspace{{4mm}}

# """
    
#     tex_filename = f"comm_{comm.id}.tex"
#     tex_path = os.path.join(temp_dir, tex_filename)
    
#     with open(tex_path, 'w', encoding='utf-8') as f:
#         f.write(tex_content)


def create_placeholder_tex(comm, temp_dir):
    """Crée un fichier .tex placeholder pour une communication sans PDF."""
    # Échapper le titre et les noms d'auteurs
    escaped_title = escape_latex(comm.title)
    escaped_authors = []
    for author in comm.authors:
        escaped_first = escape_latex(author.first_name)
        escaped_last = escape_latex(author.last_name)
        escaped_authors.append(f"{escaped_first} {escaped_last}")
    
    authors_str = ", ".join(escaped_authors)
    
    # Contenu du placeholder avec message d'information
    tex_content = f"""
% Communication {comm.id} - PLACEHOLDER (PDF manquant)
\\phantomsection\\addtocounter{{section}}{{1}}
\\addcontentsline{{toc}}{{section}}{{{escaped_title}}}
{{\\Large \\textbf{{{escaped_title}}}}}\\label{{ref:{comm.id}}}

\\vspace{{2mm}}
{authors_str}
\\vspace{{4mm}}

\\textit{{[Document PDF non disponible]}}

\\vspace{{4mm}}

"""
    
    tex_filename = f"comm_{comm.id}.tex"
    tex_path = os.path.join(temp_dir, tex_filename)
    
    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(tex_content)

def create_auxiliary_files(temp_dir):
    """Crée les fichiers auxiliaires nécessaires pour LaTeX."""
    
    # Créer index_style.ist pour l'index des auteurs (compatible avec le template existant)
    index_style = """heading_prefix "{\\\\bfseries\\\\hrulefill\\\\hspace*{2mm}"
heading_suffix "\\\\hspace*{2mm}\\\\hrulefill}\\n"
headings_flag 1

delim_0 "\\\\dotfill"
delim_1 "\\\\dotfill"
delim_2 "\\\\dotfill"
"""
    
    with open(os.path.join(temp_dir, "index_style.ist"), 'w', encoding='utf-8') as f:
        f.write(index_style)

def generate_config_tex(temp_dir, config):
    """Génère config.tex dynamiquement avec les bonnes informations."""
    
    # Extraire les infos depuis conference.yml
    congress_name = config.get('conference', {}).get('name', 'Congrès')
    short_name = config.get('conference', {}).get('short_name', 'CONF')
    city = config.get('location', {}).get('city', 'Ville')
    dates = config.get('dates', {}).get('dates', 'Dates à définir')
    
    # Formater les dates pour l'en-tête (ex: "2 -- 5 juin 2026")
    header_dates = dates  # À adapter selon le format souhaité
    
    config_content = f"""\\usepackage[french]{{babel}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{xspace}}

\\usepackage[]{{pdfpages}}
\\usepackage{{marvosym}}
\\usepackage{{sansmathfonts}}
\\usepackage[scaled]{{helvet}}
\\renewcommand{{\\familydefault}}{{\\sfdefault}}
\\hyphenpenalty=0
\\pdfminorversion=7
\\usepackage{{amsfonts}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\usepackage{{multicol}}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
\\usepackage[nohints]{{minitoc}}
\\setcounter{{minitocdepth}}{{2}}
\\setlength{{\\mtcindent}}{{0pt}}
\\renewcommand{{\\mtcfont}}{{\\small}}
\\renewcommand{{\\mtcSfont}}{{\\small}}
\\mtcsettitle{{minitoc}}{{}}
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
\\setcounter{{tocdepth}}{{1}}
\\setcounter{{secnumdepth}}{{1}}
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
\\usepackage{{enumitem}}
\\usepackage[makeindex]{{imakeidx}}
\\makeindex[options= -s index_style.ist, title=Liste des auteurs]

    
\\usepackage[a4paper,top=1.5cm,bottom=1.5cm,left=1.8cm,right=1.8cm]{{geometry}}

\\usepackage{{graphicx}}
\\DeclareGraphicsExtensions{{.jpg,.eps,.pdf,.png}}

\\usepackage{{supertabular}}

\\setlength{{\\parindent}}{{10mm}}
\\setlength{{\\parskip}}{{2mm}}
\\usepackage{{tcolorbox}}
\\tcbuselibrary{{breakable}}

\\usepackage[pages=some,contents={{Work In Progress}},color=gray!50]{{background}}

\\usepackage[compact]{{titlesec}}

%%%%%%%%%% Titre en haut de page
\\usepackage{{fancyhdr}}
\\setlength{{\\headheight}}{{15pt}}
\\renewcommand{{\\headrule}}{{\\hrule height 0.5pt}}
\\renewcommand{{\\footrule}}{{\\hrule height 0.5pt}}

\\fancyhf{{}}
\\fancyfoot[C]{{\\thepage}}
\\fancyhead[C]{{{congress_name} {short_name}, {city}, {header_dates}}}
\\fancyhead[L]{{}}
\\fancyhead[R]{{}}
\\pagestyle{{fancy}}

\\usepackage{{ifthen}}

\\usepackage[final,colorlinks,linkcolor={{blue}},citecolor={{blue}},urlcolor={{red}}]{{hyperref}}

\\hyphenation{{con-flu-ence Ga-ny-me-de}}
\\newcommand{{\\unit}}[1]{{\\,\\mathsf{{#1}}}}
\\newcommand{{\\dC}}{{\\,{{}}^{{\\circ}}\\mathsf{{C}}{{}}}}

%============
% Réglages césure des mots
%===========
\\sloppy
\\widowpenalty=10000
\\clubpenalty=10000
\\raggedbottom"""

    with open(os.path.join(temp_dir, "config.tex"), 'w', encoding='utf-8') as f:
        f.write(config_content)


def copy_latex_templates(temp_dir, title, book_type):
    current_app.logger.info(f"=== DEBUT copy_latex_templates ===")
    current_app.logger.info(f"temp_dir: {temp_dir}")
    current_app.logger.info(f"title: {title}")
    current_app.logger.info(f"book_type: {book_type}")
    
    try:
        config = get_conference_config()
        current_app.logger.info("✅ Config récupérée")
        
        current_app.logger.info("Génération de config.tex...")
        generate_config_tex(temp_dir, config)
        current_app.logger.info("✅ config.tex généré")
        
        current_app.logger.info("Génération de page-garde.tex...")
        generate_page_garde_tex(temp_dir, config, title, book_type)
        current_app.logger.info("✅ page-garde.tex généré")
        
        current_app.logger.info("Génération de remerciements.tex...")
        generate_remerciements_tex(temp_dir, config)
        current_app.logger.info("✅ remerciements.tex généré")
        
        current_app.logger.info("Génération de comite-organisation.tex...")
        generate_comite_organisation_tex(temp_dir, config)
        current_app.logger.info("✅ comite-organisation.tex généré")
        
        current_app.logger.info("Génération de Tableau_Reviewer.tex...")
        generate_tableau_reviewer_tex(temp_dir)
        current_app.logger.info("✅ Tableau_Reviewer.tex généré")
        
        current_app.logger.info("Génération de introduction.tex...")
        generate_introduction_tex(temp_dir, config)
        current_app.logger.info("✅ introduction.tex généré")
        
        current_app.logger.info("Génération de prix-biot-fourier.tex...")
        generate_prix_biot_fourier_tex(temp_dir)
        current_app.logger.info("✅ prix-biot-fourier.tex généré")
        
        # Vérifier que create_auxiliary_files est appelé
        current_app.logger.info("Création des fichiers auxiliaires...")
        create_auxiliary_files(temp_dir)
        current_app.logger.info("✅ Fichiers auxiliaires créés")
        
        current_app.logger.info("Tous les fichiers LaTeX ont été générés")
        
        # Vérifier quels fichiers ont été créés
        current_app.logger.info("=== VERIFICATION DES FICHIERS CRÉÉS ===")
        files_created = os.listdir(temp_dir)
        current_app.logger.info(f"Fichiers dans {temp_dir}: {files_created}")
        
        # Vérifier spécifiquement Tableau_Reviewer.tex
        tableau_path = os.path.join(temp_dir, "Tableau_Reviewer.tex")
        if os.path.exists(tableau_path):
            current_app.logger.info(f"✅ Tableau_Reviewer.tex EXISTS - Taille: {os.path.getsize(tableau_path)} bytes")
        else:
            current_app.logger.error(f"❌ Tableau_Reviewer.tex MISSING!")
            
    except Exception as e:
        current_app.logger.error(f"❌ ERREUR dans copy_latex_templates: {e}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        raise
    
    current_app.logger.info(f"=== FIN copy_latex_templates ===")
        
# def copy_latex_templates(temp_dir, title, book_type):
#     config = get_conference_config()
#     generate_config_tex(temp_dir, config)
#     generate_page_garde_tex(temp_dir, config, title, book_type)
#     generate_remerciements_tex(temp_dir, config)
#     generate_comite_organisation_tex(temp_dir, config)
#     generate_tableau_reviewer_tex(temp_dir)
#     generate_introduction_tex(temp_dir, config)
#     generate_prix_biot_fourier_tex(temp_dir)
#     create_auxiliary_files(temp_dir) 
#     current_app.logger.info("Tous les fichiers LaTeX ont été générés")



def generate_remerciements_tex(temp_dir, config):
    """Génère remerciements.tex depuis static/content/remerciements.yml."""
    try:
        from pathlib import Path
        import yaml
        import os
        from flask import current_app
        
        # Charger depuis remerciements.yml
        content_dir = Path(current_app.root_path) / "static" / "content"
        remerciements_file = content_dir / "remerciements.yml"
        
        if remerciements_file.exists():
            with open(remerciements_file, 'r', encoding='utf-8') as f:
                remerciements_data = yaml.safe_load(f)
        else:
            remerciements_data = {
                'title': 'Remerciements',
                'content': "Le Comité d'organisation remercie tous les participants.",
                'signature': "Le Comité d'organisation"
            }
        
        # Remplacer les variables
        content = remerciements_data['content']
        signature = remerciements_data['signature']
        
        variables = {
            'CONFERENCE_NAME': config.get('conference', {}).get('name', ''),
            'CONFERENCE_SHORT_NAME': config.get('conference', {}).get('short_name', ''),
            'ORGANIZATION_NAME': config.get('conference', {}).get('organizer', {}).get('name', '')
        }
        
        for var, value in variables.items():
            content = content.replace('{' + var + '}', value)
            signature = signature.replace('{' + var + '}', value)
        
        # Gestion des puces
        if "•" in content:
            lines = content.splitlines()
            processed_lines = []
            in_itemize = False
            for line in lines:
                if line.strip().startswith("•"):
                    if not in_itemize:
                        processed_lines.append("\\begin{itemize}")
                        in_itemize = True
                    processed_lines.append(line.replace("•", "\\item", 1).strip())
                else:
                    if in_itemize:
                        processed_lines.append("\\end{itemize}")
                        in_itemize = False
                    processed_lines.append(line)
            if in_itemize:
                processed_lines.append("\\end{itemize}")
            content_latex = "\n".join(processed_lines)
        else:
            content_latex = content
        
        # Construction du LaTeX final
        remerciements_content = f"""\\chapter*{{{remerciements_data['title']}}}

{content_latex}

\\begin{{flushright}}
{signature}
\\end{{flushright}}
"""
        
        with open(os.path.join(temp_dir, "remerciements.tex"), 'w', encoding='utf-8') as f:
            f.write(remerciements_content)
            
    except Exception as e:
        current_app.logger.error(f"Erreur génération remerciements.tex: {e}")
        # Fallback par défaut
        with open(os.path.join(temp_dir, "remerciements.tex"), 'w', encoding='utf-8') as f:
            f.write("\\chapter*{Remerciements}\nRemerciements en cours de rédaction.\n")





def generate_comite_organisation_tex(temp_dir, config):
    """Génère comite-organisation.tex depuis les données CSV existantes."""
    try:
        import csv
        import os
        
        def load_csv_data(filename):
            csv_path = os.path.join(current_app.root_path, 'static', 'content', filename)
            if not os.path.exists(csv_path):
                return []
            
            data = []
            try:
                with open(csv_path, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file, delimiter=';')
                    for row in reader:
                        cleaned_row = {k.strip(): v.strip() for k, v in row.items()}
                        data.append(cleaned_row)
            except Exception as e:
                current_app.logger.error(f"Erreur chargement {filename}: {e}")
                return []
            return data
        
        organizing_members = load_csv_data('comite_local.csv')
        
        # Séparer présidents et membres
        presidents = []
        members = []
        
        for member in organizing_members:
            member_data = {
                'name': member.get('nom', ''),
                'role': member.get('role', ''),
                'institution': member.get('institution', '')
            }
            
            if member.get('role', '').lower() in ['président', 'president', 'présidente']:
                presidents.append(member_data)
            else:
                members.append(member_data)
        
        # Générer le contenu LaTeX
        congress_name = config.get('conference', {}).get('name', 'Congrès')
        lab_name = escape_latex(config.get('conference', {}).get('organizing_lab', {}).get('name', 'Laboratoire'))
        
        comite_content = f"""\\chapter{{Comité d'organisation}}

\\phantomsection\\section*{{Équipe locale}}

Le congrès {congress_name} s'est organisé par l'équipe locale du {lab_name}.

\\vspace{{1cm}}
\\noindent
\\begin{{tabular}}{{lll}}
"""
        
        if presidents:
            comite_content += "\t\\textbf{Président :} &"
            for i, president in enumerate(presidents):
                if i > 0:
                    comite_content += " \\\\\n\t &"
                comite_content += f" {president['name']}"
                if president['institution']:
                    comite_content += f" - {president['institution']}"
                comite_content += "\\\\\n"
        
        if members:
            comite_content += "\t\\textbf{Membres :} &"
            for i, member in enumerate(members):
                if i > 0:
                    comite_content += " \\\\\n\t &"
                comite_content += f" {member['name']}"
                if member['role']:
                    comite_content += f" - {member['role']}"
                if member['institution']:
                    comite_content += f" ({member['institution']})"
                comite_content += "\\\\\n"
        
        comite_content += "\\end{tabular}\n"
        
        with open(os.path.join(temp_dir, "comite-organisation.tex"), 'w', encoding='utf-8') as f:
            f.write(comite_content)
            
    except Exception as e:
        current_app.logger.error(f"Erreur génération comite-organisation.tex: {e}")
        with open(os.path.join(temp_dir, "comite-organisation.tex"), 'w', encoding='utf-8') as f:
            f.write("\\chapter{Comité d'organisation}\nComité en cours de constitution.\n")



############################################################################################################################################################
# def generate_tableau_reviewer_tex(temp_dir):                                                                                                             #
#     """Génère Tableau_Reviewer.tex depuis la base de données des reviewers."""                                                                           #
#     try:                                                                                                                                                 #
#         from .models import User, CommunicationReview                                                                                                    #
#                                                                                                                                                          #
#         # Récupérer tous les reviewers                                                                                                                   #
#         reviewers = db.session.query(User).join(CommunicationReview).distinct().all()                                                                    #
#                                                                                                                                                          #
#         # Trier par nom de famille                                                                                                                       #
#         reviewers_sorted = sorted(reviewers, key=lambda x: x.last_name or x.email)                                                                       #
#                                                                                                                                                          #
#         tableau_content = """\\chapter{Tableau des reviewers}                                                                                            #
#                                                                                                                                                          #
# Le comité d'organisation adresse de très vifs remerciements aux relecteurs qui ont pris le temps de lire et d'expertiser les articles soumis au congrès. #
#                                                                                                                                                          #
# \\vspace{1cm}                                                                                                                                            #
#                                                                                                                                                          #
# """                                                                                                                                                      #
#                                                                                                                                                          #
#         if reviewers_sorted:                                                                                                                             #
#             # Organiser en 3 colonnes                                                                                                                    #
#             tableau_content += "\\begin{multicols}{3}\n\\small\n"                                                                                        #
#                                                                                                                                                          #
#             for reviewer in reviewers_sorted:                                                                                                            #
#                 name = f"{reviewer.first_name or ''} {reviewer.last_name or ''}".strip()                                                                 #
#                 if not name:                                                                                                                             #
#                     name = reviewer.email                                                                                                                #
#                                                                                                                                                          #
#                 institution = reviewer.institution or ""                                                                                                 #
#                                                                                                                                                          #
#                 tableau_content += f"\\textbf{{{name}}}"                                                                                                 #
#                 if institution:                                                                                                                          #
#                     tableau_content += f"\\\\\n\\textit{{{institution}}}"                                                                                #
#                 tableau_content += "\\\\\n\\vspace{0.3em}\n"                                                                                             #
#                                                                                                                                                          #
#             tableau_content += "\\end{multicols}\n"                                                                                                      #
#         else:                                                                                                                                            #
#             tableau_content += "\\textit{Liste des reviewers en cours de constitution.}\n"                                                               #
#                                                                                                                                                          #
#         with open(os.path.join(temp_dir, "Tableau_Reviewer.tex"), 'w', encoding='utf-8') as f:                                                           #
#             f.write(tableau_content)                                                                                                                     #
#                                                                                                                                                          #
#     except Exception as e:                                                                                                                               #
#         current_app.logger.error(f"Erreur génération Tableau_Reviewer.tex: {e}")                                                                         #
#         with open(os.path.join(temp_dir, "Tableau_Reviewer.tex"), 'w', encoding='utf-8') as f:                                                           #
#             f.write("\\chapter{Tableau des reviewers}\nListe des reviewers en cours de constitution.\n")                                                 #
############################################################################################################################################################




def generate_introduction_tex(temp_dir, config):
    """Génère introduction.tex depuis static/content/introduction.yml."""
    try:
        from pathlib import Path
        import yaml
        from .models import Communication, CommunicationStatus
        
        # Charger depuis introduction.yml
        content_dir = Path(current_app.root_path) / "static" / "content"
        introduction_file = content_dir / "introduction.yml"
        
        if introduction_file.exists():
            with open(introduction_file, 'r', encoding='utf-8') as f:
                intro_data = yaml.safe_load(f)
        else:
            intro_data = {
                'title': 'Introduction',
                'content': 'Bienvenue au congrès.',
                'signature': 'Le Comité d\'organisation'
            }
        
        # Compter les communications pour les statistiques
        total_communications = Communication.query.filter_by(status=CommunicationStatus.ACCEPTED).count()
        
        # Variables de remplacement
        content = intro_data['content']
        signature = intro_data['signature']
        
        variables = {
            'CONFERENCE_NAME': config.get('conference', {}).get('name', ''),
            'CONFERENCE_SHORT_NAME': config.get('conference', {}).get('short_name', ''),
            'CONFERENCE_EDITION': config.get('conference', {}).get('edition', ''),
            'CONFERENCE_THEME': config.get('conference', {}).get('theme', ''),
            'CONFERENCE_LOCATION': config.get('location', {}).get('city', ''),
            'CONFERENCE_DATES': config.get('dates', {}).get('dates', ''),
            'ORGANIZATION_NAME': config.get('conference', {}).get('organizer', {}).get('name', ''),
            'TOTAL_COMMUNICATIONS': str(total_communications)
        }
        
        for var, value in variables.items():
            content = content.replace('{' + var + '}', value)
            signature = signature.replace('{' + var + '}', value)
        
        introduction_content = f"""\\chapter*{{{intro_data['title']}}}

{content}

\\begin{{flushright}}
{signature}
\\end{{flushright}}
"""
        
        with open(os.path.join(temp_dir, "introduction.tex"), 'w', encoding='utf-8') as f:
            f.write(introduction_content)
            
    except Exception as e:
        current_app.logger.error(f"Erreur génération introduction.tex: {e}")
        with open(os.path.join(temp_dir, "introduction.tex"), 'w', encoding='utf-8') as f:
            f.write("\\chapter*{Introduction}\nIntroduction en cours de rédaction.\n")


def generate_prix_biot_fourier_tex(temp_dir):
    """Génère prix-biot-fourier.tex depuis la base de données."""
    try:
        from .models import Communication, Review
        
        # Récupérer les communications sélectionnées pour l'audition
        audition_candidates = Communication.query.filter_by(
            biot_fourier_audition_selected=True
        ).all()
        
        prix_content = "\\chapter{Prix Biot-Fourier}\n\n"
        
        if audition_candidates:
            nb_candidates = len(audition_candidates)
            
            # Utiliser la concaténation au lieu de f-string pour éviter les antislashs
            prix_content += str(nb_candidates) + " contributions ont été présélectionnées pour le Prix Biot-Fourier. Les auteurs présenteront leurs travaux à l'occasion de sessions orales.\n\n"
            prix_content += "Le Prix Biot-Fourier sera attribué en fonction des rapports d'expertise et de la qualité des présentations orales.\n\n"
            prix_content += "\\vspace{\\stretch{1}}\n"
            prix_content += "\\hrule\n\n"
            
            for candidate in audition_candidates:
                # Auteurs avec soulignement pour le premier auteur
                authors_list = []
                for i, author in enumerate(candidate.authors):
                    author_name = f"{author.first_name} {author.last_name}"
                    if i == 0:  # Premier auteur souligné
                        authors_list.append("\\underline{" + author_name + "}")
                    else:
                        authors_list.append(author_name)
                
                authors_str = ", ".join(authors_list)
                
                # Récupérer les affiliations
                affiliations = []
                for author in candidate.authors:
                    if author.institution and author.institution not in affiliations:
                        affiliations.append(author.institution)
                
                # Construction avec concaténation
                prix_content += "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
                prix_content += "%% Communication " + str(candidate.id) + "\n"
                prix_content += "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
                prix_content += "% Titre\n"
                prix_content += "\\begin{flushleft}\n"
                prix_content += "\\phantomsection\\addtocounter{section}{1}\n"
                prix_content += "\\addcontentsline{toc}{section}{" + candidate.title + "}\n"
                prix_content += "{\\Large \\textbf{" + candidate.title + "}}\\label{ref:" + str(candidate.id) + "}\n"
                prix_content += "\\end{flushleft}\n"
                prix_content += "%\n"
                prix_content += "% Auteurs\n"
                prix_content += authors_str + "\\\\[2mm]\n"
                
                if affiliations:
                    for i, aff in enumerate(affiliations):
                        prix_content += "{\\footnotesize $^{" + str(i+1) + "}$ " + aff + "}\\\\\\n"
                
                prix_content += "[4mm]\n"
                prix_content += "%\n"
                prix_content += "% Mots clés\n"
                tags_str = ', '.join(candidate.tags or [])
                prix_content += "\\noindent \\textbf{Mots clés : } " + tags_str + "\\\\[4mm]\n\n"
                prix_content += "\\noindent(Cf. page \\pageref{ref:" + str(candidate.id) + "})\n"
                prix_content += "\\vspace{\\stretch{1}}\n"
                prix_content += "\\hrule\n\n"
        else:
            prix_content += "Les communications sélectionnées pour le Prix Biot-Fourier seront annoncées prochainement.\n"
        
        with open(os.path.join(temp_dir, "prix-biot-fourier.tex"), 'w', encoding='utf-8') as f:
            f.write(prix_content)
            
    except Exception as e:
        current_app.logger.error(f"Erreur génération prix-biot-fourier.tex: {e}")
        with open(os.path.join(temp_dir, "prix-biot-fourier.tex"), 'w', encoding='utf-8') as f:
            f.write("\\chapter{Prix Biot-Fourier}\nLes communications sélectionnées seront annoncées prochainement.\n")

def generate_page_garde_tex(temp_dir, config, title, book_type):
    """Génère page-garde.tex dynamiquement."""
    theme = escape_latex(config.get('conference', {}).get('theme', 'Thermique'))
    presidents = get_presidents_names_for_latex(config)
    congress_name = config.get('conference', {}).get('series', 'Congrès')
    short_name = config.get('conference', {}).get('short_name', 'CONF')
    dates = config.get('dates', {}).get('dates', 'Date à définir')
    city = config.get('location', {}).get('city', 'Ville')
    book_title, book_du = get_book_title_type(title)
    organizing_lab = config.get('conference', {}).get('organizing_lab', {})
    lab_name = organizing_lab.get('short_name', 'LAB')
    lab_umr = organizing_lab.get('umr', '')
    lab_university = organizing_lab.get('university', 'Université')
    
    if lab_umr and lab_university:
        organizer_text = lab_name + " (UMR " + lab_umr + " - " + lab_university + ")"
    else:
        organizer_text = lab_name
    
    # Construction avec concaténation pour éviter les problèmes d'antislashs
    page_garde_content = "\\begin{titlepage}\n"
    page_garde_content += "\\centering\\scshape\n\n"
    page_garde_content += "\\LARGE\n\n"
    page_garde_content += theme + "\\\\\n"
    page_garde_content += "%\n"
    page_garde_content += "\\vspace{\\stretch{0.2}}\n"
    page_garde_content += "%\n"
    
    page_garde_content += "{\\large\n\n"
    if presidents:
        page_garde_content += presidents + "\n"
        page_garde_content += "%\n"
        page_garde_content += "\\vspace{\\stretch{1}}\n"
        page_garde_content += "}%\n"

    page_garde_content += "{\\Huge\\bfseries " + escape_latex(book_title) + "}\\\\\n"
    page_garde_content += "%\n"
    page_garde_content += "\\vspace{1em}\n"
    page_garde_content += "%\n"
    page_garde_content += book_du + "\\\\\n"
    page_garde_content += "%\n"
    page_garde_content += "\\vspace{1em}\n"
    page_garde_content += "%\n"
    page_garde_content += "{\\Huge\n"
    page_garde_content += congress_name + "\\\\\n"
    page_garde_content += "}\n"
    page_garde_content += "%\n"
    page_garde_content += "\\vspace{\\stretch{1}}\n"
    page_garde_content += "%\n"
    page_garde_content += "{\\Huge\\bfseries " + short_name + "}\\\\\n"
    page_garde_content += "%\n"
    page_garde_content += "\\vspace{\\stretch{1}}\n"
    page_garde_content += "%\n"
    page_garde_content += dates + "\\\\" + city + "\\\\\n"
    page_garde_content += "%\n"
    page_garde_content += "\\vspace{\\stretch{1}}\n"
    page_garde_content += "%\n"
    page_garde_content += "\\large\n"
    page_garde_content += "Organisé par\\\\\n"
    page_garde_content += "%\n"
    page_garde_content += "\\vspace{1em}\n"
    page_garde_content += "%\n"
    page_garde_content += "\\normalsize\n"
    page_garde_content += organizer_text + "\n"
    page_garde_content += "%\n"
    page_garde_content += "\\end{titlepage}"
    
    with open(os.path.join(temp_dir, "page-garde.tex"), 'w', encoding='utf-8') as f:
        f.write(page_garde_content)

def get_presidents_names_for_latex(config):
    """Récupère les noms des présidents formatés pour LaTeX."""
    presidents_list = config.get('conference', {}).get('presidents', [])
    
    if not presidents_list:
        organizing = config.get('organizing', {})
        presidents_list = organizing.get('presidents', [])
    
    names = []
    for president in presidents_list:
        if isinstance(president, dict):
            name = president.get('name', '')
            if not name:
                first = president.get('first_name', '')
                last = president.get('last_name', '')
                name = (first + " " + last).strip()
            if name:
                names.append(name)
        elif isinstance(president, str):
            names.append(president)
    
    if names:
        return "\\\\".join(names) + "\\\\"
    else:
        return ""





def escape_latex(text):
    """Échappe les caractères spéciaux pour LaTeX."""
    if not text:
        return ""
    
    # Dictionnaire des caractères à échapper
    latex_chars = {
        '\\': r'\textbackslash{}', 
        '&': r'\&',
        '%': r'\%', 
        '$': r'\$',
        '#': r'\#',
        '^': r'\textasciicircum{}',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
    }
    
    escaped_text = str(text)
    for char, replacement in latex_chars.items():
        escaped_text = escaped_text.replace(char, replacement)
    
    return escaped_text


                                                           #

def generate_tableau_reviewer_tex(temp_dir):
    """Génère Tableau_Reviewer.tex depuis la base de données des reviewers."""
    current_app.logger.info("=== DEBUT generate_tableau_reviewer_tex ===")
    
    try:
        from .models import User, ReviewAssignment
        from . import db
        
        # Récupérer tous les reviewers via ReviewAssignment
        reviewer_users = db.session.query(User).join(ReviewAssignment, User.id == ReviewAssignment.reviewer_id).distinct().all()
        current_app.logger.info(f"Nombre de reviewers trouvés: {len(reviewer_users)}")
        
        # Trier par nom de famille
        reviewers_sorted = sorted(reviewer_users, key=lambda x: (x.last_name or x.email).lower())
        
        # Contenu LaTeX SANS multicols - utilisation de supertabular comme dans l'original SFT
        tableau_content = """\\chapter{Liste des relecteurs}

Le comité d'organisation adresse de très vifs remerciements aux relecteurs qui ont pris le temps de lire et d'expertiser les articles soumis au congrès.

\\vspace{1em}

\\begin{center}
\\begin{supertabular}{lll}
"""
        
        if reviewers_sorted:
            # Organiser les noms en groupes de 3 pour le tableau (comme dans l'original SFT)
            names = []
            for reviewer in reviewers_sorted:
                name = f"{reviewer.first_name or ''} {reviewer.last_name or ''}".strip()
                if not name:
                    name = reviewer.email.split('@')[0]  # Prendre la partie avant @
                names.append(name)
            
            # Compléter pour avoir un multiple de 3
            while len(names) % 3 != 0:
                names.append('')
            
            current_app.logger.info(f"Nombres total de noms (avec padding): {len(names)}")
            
            # Créer le tableau par lignes de 3
            for i in range(0, len(names), 3):
                row = names[i:i+3]
                tableau_content += f"{row[0]} & {row[1]} & {row[2]} \\\\\n"
        else:
            current_app.logger.info("Aucun reviewer trouvé, utilisation du message par défaut")
            tableau_content += "\\multicolumn{3}{c}{\\textit{Liste des reviewers en cours de constitution.}} \\\\\n"
        
        tableau_content += """\\end{supertabular}
\\end{center}
"""
        
        # Écrire le fichier
        file_path = os.path.join(temp_dir, "Tableau_Reviewer.tex")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(tableau_content)
        
        current_app.logger.info("✅ Fichier Tableau_Reviewer.tex créé avec succès")
            
    except Exception as e:
        current_app.logger.error(f"❌ ERREUR dans generate_tableau_reviewer_tex: {e}")
        
        # Version de fallback simple
        tableau_content = """\\chapter{Liste des relecteurs}

Le comité d'organisation adresse de très vifs remerciements aux relecteurs qui ont pris le temps de lire et d'expertiser les articles soumis au congrès.

\\vspace{1em}

\\begin{center}
\\textit{Liste des reviewers en cours de constitution.}
\\end{center}
"""
        file_path = os.path.join(temp_dir, "Tableau_Reviewer.tex")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(tableau_content)
        current_app.logger.info("✅ Fichier de fallback créé")
    
    current_app.logger.info("=== FIN generate_tableau_reviewer_tex ===")
