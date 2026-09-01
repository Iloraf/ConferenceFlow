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
import csv
import zipfile
import logging
from datetime import datetime

from ..models import Communication, CommunicationStatus, db
from .doi_generator import DOIGenerator, DOIConfigError
from .doi_xml_generator import DOIXMLGenerator, DOIXMLError


class DOIExporter:
    """
    Produit le lot à transmettre à l'Inist :
      - un fichier XML DataCite par communication
      - un CSV de correspondance DOI vers URL de destination

    Le schéma DataCite ne comporte pas la page de destination, d'où le
    CSV : sans lui, l'Inist ne peut pas enregistrer les DOI.
    """

    # Types de communication exclus de l'attribution de DOI
    ALLOWED_TYPES = {'article'}

    CSV_FILENAME = "correspondance_doi_url.csv"
    XML_DIRECTORY = "xml"

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.doi_generator = DOIGenerator()
        self.xml_generator = DOIXMLGenerator()

    # ------------------------------------------------------------------
    # Sélection
    # ------------------------------------------------------------------

    def get_eligible_communications(self):
        """
        Communications acceptées, hors types exclus, triées par id
        (l'id est aussi le numéro de séquence du DOI).
        """
        communications = (
            Communication.query
            .filter(Communication.status == CommunicationStatus.ACCEPTE)
            .order_by(Communication.id)
            .all()
        )
        return [
            c for c in communications
            if (c.type or '').lower() in self.ALLOWED_TYPES
        ]

    # ------------------------------------------------------------------
    # Attribution des identifiants
    # ------------------------------------------------------------------

    def assign_identifiers(self, dry_run=True):
        """
        Attribue DOI et public_url aux communications éligibles qui n'en
        ont pas encore.

        En dry_run (défaut), rien n'est écrit en base : la méthode se
        contente de rapporter ce qu'elle ferait.

        Retourne un rapport : liste de dictionnaires
        {id, title, doi, url, action, error}.
        """
        report = []
        touched = False

        for comm in self.get_eligible_communications():
            entry = {
                'id': comm.id,
                'title': comm.title,
                'doi': comm.doi,
                'url': comm.public_url,
                'action': 'inchangé',
                'error': None,
            }

            try:
                doi = self.doi_generator.generate_doi(comm)
                url = self.doi_generator.generate_landing_page_url(comm)

                actions = []

                if not comm.doi:
                    entry['doi'] = doi
                    actions.append('DOI attribué')
                    if not dry_run:
                        comm.doi = doi
                        comm.doi_generated_at = datetime.utcnow()
                        touched = True
                elif comm.doi.strip() != doi:
                    entry['error'] = (
                        f"DOI existant {comm.doi} différent du DOI attendu "
                        f"{doi} : vérification manuelle requise"
                    )

                if not comm.public_url:
                    entry['url'] = url
                    actions.append('URL attribuée')
                    if not dry_run:
                        comm.public_url = url
                        touched = True
                elif comm.public_url.strip() != url:
                    entry['error'] = (
                        (entry['error'] + ' ; ') if entry['error'] else ''
                    ) + (
                        f"URL existante {comm.public_url} différente de "
                        f"l'URL attendue {url}"
                    )

                if actions:
                    entry['action'] = ', '.join(actions)

            except DOIConfigError as e:
                entry['error'] = str(e)

            report.append(entry)

        if touched and not dry_run:
            db.session.commit()
            self.logger.info(
                "Attribution DOI : %d communications traitées",
                len(report)
            )

        return report

    # ------------------------------------------------------------------
    # Construction de l'archive
    # ------------------------------------------------------------------

    def build_archive(self, assign=False):
        """
        Construit l'archive ZIP à livrer à l'Inist.

        Si assign vaut True, les DOI et URL manquants sont attribués et
        écrits en base avant la génération. Sinon, les communications
        sans DOI sont signalées en erreur et exclues de l'archive.

        Retourne (contenu_zip_en_octets, rapport).
        """
        if assign:
            self.assign_identifiers(dry_run=False)

        communications = self.get_eligible_communications()

        rows = []
        errors = []
        xml_files = {}

        for comm in communications:
            if not comm.doi:
                errors.append({
                    'id': comm.id,
                    'title': comm.title,
                    'error': "DOI absent",
                })
                continue

            if not comm.public_url:
                errors.append({
                    'id': comm.id,
                    'title': comm.title,
                    'error': "URL de destination absente",
                })
                continue

            try:
                xml_bytes = self.xml_generator.generate_datacite_file(comm)
            except (DOIXMLError, Exception) as e:
                errors.append({
                    'id': comm.id,
                    'title': comm.title,
                    'error': str(e),
                })
                continue

            filename = f"{self._safe_name(comm.doi)}.xml"
            xml_files[filename] = xml_bytes
            rows.append({
                'doi': comm.doi,
                'url': comm.public_url,
                'titre': comm.title,
            })

        archive = self._package(xml_files, rows)

        report = {
            'total_eligible': len(communications),
            'exported': len(rows),
            'errors': errors,
            'generated_at': datetime.utcnow(),
        }

        return archive, report

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _package(self, xml_files, rows):
        """Assemble le ZIP en mémoire."""
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for filename, content in sorted(xml_files.items()):
                archive.writestr(
                    f"{self.XML_DIRECTORY}/{filename}", content
                )
            archive.writestr(self.CSV_FILENAME, self._build_csv(rows))

        buffer.seek(0)
        return buffer.getvalue()

    def _build_csv(self, rows):
        """
        CSV de correspondance, séparateur point-virgule comme le reste
        de l'application, encodage UTF-8 avec BOM pour rester lisible
        dans Excel.
        """
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=['doi', 'url', 'titre'],
            delimiter=';',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator='\r\n',
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

        return output.getvalue().encode('utf-8-sig')

    def _safe_name(self, doi):
        """10.25855/SFT2026-051 devient SFT2026-051."""
        return doi.split('/', 1)[-1].replace('/', '_').strip()
