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

import io
import os
import re
import csv
import shutil
import logging
import tempfile
import unicodedata
from datetime import datetime

from flask import current_app

from ..models import Communication, CommunicationStatus, CommunicationAuthor
from .pdf_export import PDFExporter
from .site_books import SiteBooksGenerator

CSS_FILENAME = "markdown-pandoc.css"

PAGE_TEMPLATE = """<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="fr" xml:lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="generator" content="Conference Flow" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, \
user-scalable=yes" />
  <title>{page_id}</title>
  <link rel="stylesheet" href="{css}" />
</head>
<body>
{body}
</body>
</html>
"""


class SiteExporter:
    """
    Construit l'archive d'intégration pour le site de la SFT.

    Arborescence produite :

        CFT{year}/
        ├── Table_of_contents.html
        ├── markdown-pandoc.css
        ├── bandeau-sft{year}.png
        ├── doi_thematique.csv
        ├── Abstracts/
        │   ├── markdown-pandoc.css
        │   └── p{N}.html
        ├── Media/
        └── PDF/
            ├── {N}_doi.pdf
            ├── Actes_SFT{year}.pdf
            └── Resumes_SFT{year}.pdf
    """

    ARTICLE_STATUSES = {CommunicationStatus.ACCEPTE}
    WIP_STATUSES = {
        CommunicationStatus.WIP_SOUMIS,
        CommunicationStatus.POSTER_SOUMIS,
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pdf_exporter = PDFExporter()
        self.books = SiteBooksGenerator()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _config(self):
        config = current_app.conference_config
        conference = config.get('conference', {}) or {}
        site = config.get('integrations', {}).get('site_sft', {}) or {}
        year = conference.get('year', datetime.now().year)

        base_url = (
            site.get('base_url')
            or "https://www.sft.asso.fr/DOIeditions/CFT{year}"
        ).format(year=year).rstrip('/')

        banner = (
            site.get('banner_filename') or "bandeau-sft{year}.png"
        ).format(year=year)

        return {
            'year': year,
            'conference': conference,
            'site': site,
            'base_url': base_url,
            'banner': banner,
            'root': f"CFT{year}",
        }

    # ------------------------------------------------------------------
    # Sélection
    # ------------------------------------------------------------------

    def get_communications(self):
        """Articles acceptés et WIP, triés par id."""
        selected = []
        for comm in Communication.query.order_by(Communication.id).all():
            comm_type = (comm.type or '').lower()
            if comm_type == 'article' and comm.status in self.ARTICLE_STATUSES:
                selected.append(comm)
            elif comm_type == 'wip' and comm.status in self.WIP_STATUSES:
                selected.append(comm)
        return selected

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def build_archive(self):
        """
        Retourne (chemin_archive_temporaire, rapport).

        L'archive est écrite sur disque et non en mémoire : avec les 73
        PDF et les deux livres, elle peut peser plusieurs centaines de
        mégaoctets. L'appelant est responsable de sa suppression.
        """
        cfg = self._config()
        communications = self.get_communications()
        warnings = []

        workdir = tempfile.mkdtemp(prefix='cf_site_')
        root = os.path.join(workdir, cfg['root'])
        abstracts_dir = os.path.join(root, 'Abstracts')
        pdf_dir = os.path.join(root, 'PDF')
        os.makedirs(abstracts_dir)
        os.makedirs(pdf_dir)

        # Pages individuelles
        for comm in communications:
            html = self._render_page(comm, cfg, warnings)
            path = os.path.join(abstracts_dir, f"p{comm.id}.html")
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(html)

        # Feuille de style, en deux exemplaires
        css_source = self._css_source()
        if css_source:
            shutil.copy2(css_source, os.path.join(root, CSS_FILENAME))
            shutil.copy2(css_source,
                         os.path.join(abstracts_dir, CSS_FILENAME))
        else:
            warnings.append({
                'id': None,
                'message': f"{CSS_FILENAME} introuvable dans static/content",
            })

        # Bandeau
        banner_source = self._banner_source()
        if banner_source:
            shutil.copy2(banner_source, os.path.join(root, cfg['banner']))
        else:
            warnings.append({
                'id': None,
                'message': "bandeau introuvable dans static/content",
            })

        # Supports de la médiathèque (avant la table, qui les liste)
        media = self._copy_media(root, warnings)

        # Table des matières et CSV des thématiques
        grouped = self._group_by_thematique(communications)

        with open(os.path.join(root, 'Table_of_contents.html'),
                  'w', encoding='utf-8') as handle:
            handle.write(self._render_toc(grouped, cfg, media))
        
        with open(os.path.join(root, 'doi_thematique.csv'),
                  'wb') as handle:
            handle.write(self._render_thematique_csv(grouped))

        # PDF des articles, tamponnés du DOI
        pdf_count = self._copy_article_pdfs(pdf_dir, warnings)

        # Livres
        books_included = self._copy_books(pdf_dir, warnings)

        archive_path = self._package(workdir, cfg)

        report = {
            'total': len(communications),
            'articles': len([
                c for c in communications
                if (c.type or '').lower() == 'article'
            ]),
            'wip': len([
                c for c in communications if (c.type or '').lower() == 'wip'
            ]),
            'pdf': pdf_count,
            'livres': books_included,
            'media': len(media),
            'warnings': warnings,
            'archive': os.path.basename(archive_path),
            'taille_octets': os.path.getsize(archive_path),
            'workdir': workdir,
            'generated_at': datetime.utcnow(),
        }

        return archive_path, report

    # ------------------------------------------------------------------
    # Pages individuelles
    # ------------------------------------------------------------------

    def _render_page(self, comm, cfg, warnings):
        from markupsafe import escape

        authors = self._ordered_authors(comm)
        if not authors:
            warnings.append({'id': comm.id, 'message': "aucun auteur"})

        affiliations, author_marks = self._affiliation_map(authors)

        lines = []
        lines.append('<div class="flushleft">')
        lines.append(
            f'<p><span><strong>{escape(comm.title or "")}'
            f'</strong></span></p>'
        )
        lines.append('</div>')

        block = []

        names = []
        for assoc in authors:
            user = assoc.user
            name = f"{(user.first_name or '').strip()} " \
                   f"{(user.last_name or '').strip()}".strip()
            marks = author_marks.get(user.id, [])
            sup = ','.join(str(m) for m in marks)
            names.append(
                f'{escape(name)}<sup>{sup}</sup>' if sup else escape(name)
            )
        block.append(', '.join(names))

        contact = self._corresponding(authors)
        if contact and contact.email:
            block.append(
                f'<sup>\u22c6</sup> : '
                f'<a href="mailto:{escape(contact.email)}">'
                f'{escape(contact.email)}</a>'
            )
        else:
            warnings.append({'id': comm.id, 'message': "aucun contact"})

        for index, label in affiliations:
            block.append(
                f'<span><sup>{index}</sup> {escape(label)}</span>'
            )

        if comm.keywords:
            keywords = '; '.join(
                k.strip() for k in comm.keywords.split(',') if k.strip()
            )
            block.append(
                f'<strong>Mots clés :</strong> {escape(keywords)}'
            )

        block.append('<strong>Résumé :</strong>')

        lines.append('<p>' + '<br />\n'.join(block) + '</p>')

        abstract = comm.abstract_fr or comm.abstract_en or ''
        if not abstract.strip():
            warnings.append({'id': comm.id, 'message': "aucun résumé"})
        for paragraph in self._paragraphs(abstract):
            lines.append(f'<p>{escape(paragraph)}</p>')

        if (comm.type or '').lower() == 'article':
            lines.append('<p>Article</p>')
            lines.append(
                f'<p>PDF : <a href="{cfg["base_url"]}/PDF/'
                f'{comm.id}_doi.pdf">download</a></p>'
            )
        else:
            lines.append('<p>Work In Progress</p>')

        return PAGE_TEMPLATE.format(
            page_id=f"p{comm.id}",
            css=CSS_FILENAME,
            body='\n'.join(lines),
        )

    # ------------------------------------------------------------------
    # Table des matières
    # ------------------------------------------------------------------

    def _render_toc(self, grouped, cfg, media=None):
        from markupsafe import escape
        from ..conference_books import get_presidents_names

        conference = cfg['conference']
        year = cfg['year']
        base = cfg['base_url']

        title = (
            f"Actes du Congrès Annuel de la Société Française "
            f"de Thermique {year}."
        )
        subtitle = ' - '.join(
            part for part in (
                (current_app.conference_config.get('location', {}) or {})
                .get('city', ''),
                conference.get('theme', ''),
            ) if part
        )

        presidents = (
            get_presidents_names(current_app.conference_config) or ''
        ).replace('<br>', ', ')

        proceedings = self.books.target_name('proceedings')

        lines = []
        lines.append(
            f'<p><img src="{base}/{cfg["banner"]}" /></p>'
        )
        lines.append(
            f'<h1 id="{self._slug(title)}">{escape(title)}<br></h1>'
        )
        if subtitle:
            lines.append(
                f'<h1 id="{self._slug(subtitle)}">{escape(subtitle)}</h1>'
            )
        if presidents:
            lines.append(
                f'<p><strong>Présidents :</strong> {escape(presidents)}</p>'
            )
        lines.append(
            f'<p>Vous trouverez ci-dessous l\'ensemble des articles '
            f'sélectionnés. L\'intégralité des actes en PDF est '
            f'disponible ici <a href="{base}/PDF/{proceedings}">'
            f'Actes-SFT{year}</a></p>'
        )

        if media:
            lines.append(
                '<h3 id="supports">Supports des conférences plénières '
                'et ateliers</h3>'
            )
            for fichier, description in media:
                lines.append(
                    f'<p><a href="{base}/Media/{escape(fichier)}">'
                    f'{escape(description or fichier)}</a></p>'
                )
        
        for thematique, communications in grouped.items():
            lines.append(
                f'<h3 id="{self._slug(thematique)}">'
                f'{escape(thematique)}</h3>'
            )
            for comm in communications:
                authors = ', '.join(
                    f"{(a.user.first_name or '').strip()} "
                    f"{(a.user.last_name or '').strip()}".strip()
                    for a in self._ordered_authors(comm)
                )
                lines.append(
                    f'<p><a href="{base}/Abstracts/p{comm.id}.html">'
                    f'{escape(comm.title or "")}</a><br>'
                    f'{escape(authors)}</p>'
                )

        return PAGE_TEMPLATE.format(
            page_id="Table_of_contents",
            css=CSS_FILENAME,
            body='\n'.join(lines),
        )

    # ------------------------------------------------------------------
    # CSV des thématiques
    # ------------------------------------------------------------------

    def _render_thematique_csv(self, grouped):
        """
        Reproduit le format 2025 : en-tête entre guillemets, une ligne
        par communication, numéro puis thématique principale.
        """
        output = io.StringIO()
        writer = csv.writer(
            output, delimiter=',', quoting=csv.QUOTE_NONNUMERIC,
            lineterminator='\n'
        )
        writer.writerow(['doi', 'thématique'])
        for thematique, communications in grouped.items():
            for comm in communications:
                writer.writerow([comm.id, thematique])

        return output.getvalue().encode('utf-8')

    # ------------------------------------------------------------------
    # Fichiers binaires
    # ------------------------------------------------------------------

    def _copy_article_pdfs(self, pdf_dir, warnings):
        """
        Reprend la sélection et le tamponnage de PDFExporter, mais écrit
        directement sur le disque sous le nom {id}_doi.pdf.
        """
        count = 0
        for comm in self.pdf_exporter.get_communications():
            submission_file = comm.get_latest_file('article')
            if submission_file is None:
                warnings.append({
                    'id': comm.id, 'message': "aucun fichier article"
                })
                continue

            path = self.pdf_exporter._resolve_path(submission_file)
            if path is None:
                warnings.append({
                    'id': comm.id,
                    'message': f"fichier introuvable "
                               f"({submission_file.filename})",
                })
                continue

            with open(path, 'rb') as handle:
                payload = handle.read()

            if not payload.startswith(b'%PDF'):
                warnings.append({
                    'id': comm.id, 'message': "le fichier n'est pas un PDF"
                })
                continue

            if not comm.doi:
                warnings.append({
                    'id': comm.id, 'message': "DOI absent, PDF non tamponné"
                })
            else:
                try:
                    payload = self.pdf_exporter._stamp_doi(payload, comm.doi)
                except Exception as e:
                    warnings.append({
                        'id': comm.id,
                        'message': f"tamponnage impossible : {e}",
                    })

            target = os.path.join(pdf_dir, f"{comm.id}_doi.pdf")
            with open(target, 'wb') as handle:
                handle.write(payload)
            count += 1

        return count

    def _copy_books(self, pdf_dir, warnings):
        included = []
        for key, label in (
            ('proceedings', "actes"),
            ('abstracts_book', "recueil des résumés"),
        ):
            path = self.books.path_for(key)
            if path is None:
                warnings.append({
                    'id': None,
                    'message': f"{label} absent : générez les livres "
                               f"avant de construire l'archive",
                })
                continue
            shutil.copy2(path, os.path.join(pdf_dir, os.path.basename(path)))
            included.append(os.path.basename(path))
        return included

    def _copy_media(self, root, warnings):
        """
        Copie dans Media/ les PDF décrits dans static/content/media/media.csv,
        avec le même filtrage que la route /mediatheque.
        Retourne la liste [(fichier, description)] des documents copiés.
        """
        media_dir = os.path.join(current_app.static_folder, 'content', 'media')
        csv_path = os.path.join(media_dir, 'media.csv')
        if not os.path.exists(csv_path):
            return []

        copied = []
        target_dir = os.path.join(root, 'Media')

        with open(csv_path, 'r', encoding='utf-8') as handle:
            for row in csv.DictReader(handle, delimiter=';'):
                fichier = (row.get('fichier') or '').strip()
                description = (row.get('description') or '').strip()
                if not fichier:
                    continue
                source = os.path.join(media_dir, fichier)
                if not os.path.exists(source):
                    warnings.append({
                        'id': None,
                        'message': f"médiathèque : fichier absent {fichier}",
                    })
                    continue
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(source, os.path.join(target_dir, fichier))
                copied.append((fichier, description))

        return copied
    
    # ------------------------------------------------------------------
    # Empaquetage
    # ------------------------------------------------------------------

    def _package(self, workdir, cfg):
        """
        Produit une archive 7z si py7zr est disponible, un ZIP sinon.
        """
        base = os.path.join(workdir, f"integration_sft_{cfg['year']}")

        try:
            import py7zr
        except ImportError:
            self.logger.warning(
                "py7zr absent : archive produite au format ZIP"
            )
            return shutil.make_archive(
                base, 'zip', root_dir=workdir, base_dir=cfg['root']
            )

        archive_path = f"{base}.7z"
        with py7zr.SevenZipFile(archive_path, 'w') as archive:
            archive.writeall(
                os.path.join(workdir, cfg['root']), cfg['root']
            )
        return archive_path

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _ordered_authors(self, comm):
        associations = (
            CommunicationAuthor.query
            .filter_by(communication_id=comm.id)
            .order_by(CommunicationAuthor.author_order)
            .all()
        )
        seen = set()
        ordered = []
        for assoc in associations:
            if assoc.user_id in seen or assoc.user is None:
                continue
            seen.add(assoc.user_id)
            ordered.append(assoc)
        return ordered

    def _corresponding(self, authors):
        for assoc in authors:
            if getattr(assoc, 'is_corresponding', False):
                return assoc.user
        return authors[0].user if authors else None

    def _affiliation_map(self, authors):
        """
        Numérote les affiliations dans l'ordre d'apparition et retourne
        la liste [(indice, libellé)] ainsi que les exposants par auteur.
        """
        labels = []
        index_of = {}
        marks = {}

        for assoc in authors:
            user = assoc.user
            user_marks = []
            for affiliation in (user.affiliations or []):
                label = (
                    getattr(affiliation, 'citation', None)
                    or getattr(affiliation, 'nom_complet', None)
                    or getattr(affiliation, 'sigle', None)
                    or ''
                ).strip()
                if not label:
                    continue
                if label not in index_of:
                    index_of[label] = len(labels) + 1
                    labels.append((index_of[label], label))
                user_marks.append(index_of[label])
            marks[user.id] = user_marks

        return labels, marks

    def _group_by_thematique(self, communications):
        from ..conference_books import group_communications_by_thematique
        return group_communications_by_thematique(communications)

    def _paragraphs(self, text):
        parts = re.split(r'\n\s*\n', (text or '').strip())
        return [' '.join(p.split()) for p in parts if p.strip()]

    def _slug(self, text):
        normalized = unicodedata.normalize('NFKD', text or '')
        ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_text).strip('-').lower()
        return slug or 'section'

    def _css_source(self):
        path = os.path.join(
            current_app.static_folder, 'content', CSS_FILENAME
        )
        return path if os.path.exists(path) else None

    def _banner_source(self):
        site = self._config()['site']
        relative = site.get('banner_source') or 'content/bandeau.png'
        path = os.path.join(current_app.static_folder, relative)
        return path if os.path.exists(path) else None
