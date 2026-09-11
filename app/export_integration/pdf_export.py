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
import csv
import zipfile
import pikepdf
import logging
from datetime import datetime

from flask import current_app

from ..models import Communication, CommunicationStatus


class PDFExporter:
    """
    Constitue l'archive des articles en version définitive.

    Seuls les articles acceptés sont concernés : les WIP n'ont pas de
    PDF associé sur le site de la SFT.

    Pour chaque article, seule la dernière version du fichier est
    retenue, via Communication.get_latest_file('article'). Les fichiers
    sont renommés p{id}.pdf pour correspondre aux pages p{id}.html.
    """

    MANIFEST_FILENAME = "contenu.csv"
    PDF_DIRECTORY = "pdf"

    DOI_X = 85
    DOI_Y = 30
    DOI_FONT_SIZE = 11
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Sélection
    # ------------------------------------------------------------------

    def get_communications(self):
        """Articles acceptés, triés par id."""
        communications = (
            Communication.query
            .filter(Communication.status == CommunicationStatus.ACCEPTE)
            .order_by(Communication.id)
            .all()
        )

        return [c for c in communications if (c.type or '').lower() == 'article']

    # ------------------------------------------------------------------
    # Construction de l'archive
    # ------------------------------------------------------------------
    def build_archive(self, stamp_doi=True):
        """
        Retourne (contenu_zip_en_octets, rapport).

        Le rapport détaille les fichiers inclus et les articles écartés
        avec le motif.
        """
        rows = []
        errors = []
        contents = {}

        for comm in self.get_communications():
            submission_file = comm.get_latest_file('article')

            if submission_file is None:
                errors.append({
                    'id': comm.id,
                    'title': comm.title,
                    'error': "aucun fichier article",
                })
                continue

            path = self._resolve_path(submission_file)
            if path is None:
                errors.append({
                    'id': comm.id,
                    'title': comm.title,
                    'error': (
                        f"fichier introuvable sur le disque "
                        f"({submission_file.filename})"
                    ),
                })
                continue

            try:
                with open(path, 'rb') as handle:
                    payload = handle.read()
            except OSError as e:
                errors.append({
                    'id': comm.id,
                    'title': comm.title,
                    'error': f"lecture impossible : {e}",
                })
                continue

            if not payload.startswith(b'%PDF'):
                errors.append({
                    'id': comm.id,
                    'title': comm.title,
                    'error': (
                        f"le fichier n'est pas un PDF "
                        f"({submission_file.filename})"
                    ),
                })
                continue

            tampon = False
            if stamp_doi:
                if not comm.doi:
                    errors.append({
                        'id': comm.id,
                        'title': comm.title,
                        'error': "DOI absent : impossible de tamponner le PDF",
                    })
                    continue
                try:
                    payload = self._stamp_doi(payload, comm.doi)
                    tampon = True
                except Exception as e:
                    errors.append({
                        'id': comm.id,
                        'title': comm.title,
                        'error': f"tamponnage impossible : {e}",
                    })
                    continue


            
            archive_name = f"p{comm.id}.pdf"
            contents[archive_name] = payload

            rows.append({
                'numero': comm.id,
                'fichier': archive_name,
                'doi': comm.doi or '',
                'titre': comm.title or '',
                'version': submission_file.version,
                'tampon_doi': 'oui' if tampon else 'non',
                'fichier_origine': submission_file.filename,
                'taille_octets': len(payload),
            })

        archive = self._package(contents, rows)

        report = {
            'total_articles': len(rows) + len(errors),
            'exportes': len(rows),
            'errors': errors,
            'taille_totale': sum(r['taille_octets'] for r in rows),
            'generated_at': datetime.utcnow(),
        }

        return archive, report

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _resolve_path(self, submission_file):
        """
        Localise le fichier sur le disque.

        file_path contient normalement un chemin absolu, mais certains
        enregistrements ne portent que le nom du fichier. On reconstruit
        alors le chemin depuis le dossier statique.
        """
        path = (submission_file.file_path or '').strip()

        if path and os.path.isabs(path) and os.path.exists(path):
            return path

        candidate = os.path.join(
            current_app.static_folder, 'uploads', 'articles',
            submission_file.filename
        )
        if os.path.exists(candidate):
            return candidate

        if path and os.path.exists(path):
            return path

        return None
    
    def _stamp_doi(self, payload, doi):
        """
        Imprime l'URL du DOI en bas de la première page.

        Le PDF d'origine n'est pas réécrit : un second flux de contenu
        est ajouté à la page, comme le faisait l'outil utilisé pour les
        éditions précédentes. Le texte n'est pas cliquable.
        """
        url = f"https://doi.org/{doi}"

        with pikepdf.open(io.BytesIO(payload)) as pdf:
            page = pdf.pages[0]

            font = pdf.make_indirect(pikepdf.Dictionary(
                Type=pikepdf.Name.Font,
                Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica,
                Encoding=pikepdf.Name.WinAnsiEncoding,
            ))

            resources = page.get('/Resources')
            if '/Font' not in resources:
                resources['/Font'] = pikepdf.Dictionary()
            resources['/Font']['/CFDOI'] = font

            escaped = (url.replace('\\', '\\\\')
                          .replace('(', '\\(')
                          .replace(')', '\\)'))

            overlay = (
                f"q BT 1 0 0 1 {self.DOI_X} {self.DOI_Y} Tm "
                f"/CFDOI {self.DOI_FONT_SIZE} Tf 0 0 0 rg "
                f"({escaped}) Tj ET Q"
            ).encode('latin-1')

            page.contents_add(pikepdf.Stream(pdf, overlay), prepend=False)

            output = io.BytesIO()
            pdf.save(output)
            return output.getvalue()

    def _package(self, contents, rows):
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for filename, payload in sorted(contents.items()):
                archive.writestr(f"{self.PDF_DIRECTORY}/{filename}", payload)
            archive.writestr(self.MANIFEST_FILENAME, self._build_manifest(rows))

        buffer.seek(0)
        return buffer.getvalue()

    def _build_manifest(self, rows):
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                'numero', 'fichier', 'doi', 'titre',
                'version', 'tampon_doi', 'fichier_origine', 'taille_octets',
            ],
            delimiter=';',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator='\r\n',
        )
        writer.writeheader()
        for row in sorted(rows, key=lambda r: r['numero']):
            writer.writerow(row)

        return output.getvalue().encode('utf-8-sig')
