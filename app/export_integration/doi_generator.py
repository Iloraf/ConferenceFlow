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

import re
import logging
from datetime import datetime

from flask import current_app


class DOIConfigError(Exception):
    """Exception levée en cas de configuration DOI manquante ou invalide"""
    pass


class DOIGenerator:
    """
    Construit les DOI et les URL de destination à partir de
    conference.yml > integrations > doi.

    Le numéro de séquence est communication.id : il est aussi celui
    utilisé par les pages de destination du site de la SFT.
    """

    DEFAULT_PREFIX = "10.25855"
    DEFAULT_SUFFIX_PATTERN = "{short_name}{year}-{seq:03d}"

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Génération
    # ------------------------------------------------------------------

    def generate_doi(self, communication):
        """
        Retourne le DOI complet, par exemple 10.25855/SFT2026-051.
        """
        doi_config = self._doi_config()
        prefix = str(doi_config.get('prefix') or self.DEFAULT_PREFIX).strip()
        pattern = doi_config.get('suffix_pattern') or self.DEFAULT_SUFFIX_PATTERN

        suffix = self._format(pattern, communication, 'suffix_pattern')
        return f"{prefix}/{suffix}"

    def generate_landing_page_url(self, communication):
        """
        Retourne l'URL de la page de destination sur le site de la SFT.

        Cette URL n'apparaît pas dans le XML DataCite : elle doit être
        transmise séparément à l'Inist.
        """
        doi_config = self._doi_config()
        pattern = doi_config.get('landing_page_pattern')

        if not pattern:
            raise DOIConfigError(
                "landing_page_pattern manquant dans "
                "conference.yml > integrations > doi"
            )

        return self._format(pattern, communication, 'landing_page_pattern')

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_doi(self, doi):
        """
        Vérifie qu'un DOI est bien formé et porte le préfixe configuré.
        """
        if not doi or not isinstance(doi, str):
            return False

        prefix = str(
            self._doi_config().get('prefix') or self.DEFAULT_PREFIX
        ).strip()

        pattern = r'^' + re.escape(prefix) + r'/[^\s/]+$'
        return bool(re.match(pattern, doi.strip()))

    def matches_communication(self, doi, communication):
        """
        Vérifie qu'un DOI existant correspond bien à celui que produirait
        la configuration actuelle pour cette communication. Utile pour
        détecter une dérive après un changement de motif.
        """
        if not doi:
            return False
        return doi.strip() == self.generate_doi(communication)

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _doi_config(self):
        try:
            config = current_app.conference_config
        except AttributeError:
            raise DOIConfigError(
                "Configuration Conference Flow non disponible "
                "(current_app.conference_config)"
            )
        return config.get('integrations', {}).get('doi', {}) or {}

    def _placeholders(self, communication):
        """
        Valeurs disponibles dans les motifs : {seq}, {year}, {short_name}.

        short_name est débarrassé de ses espaces, car conference.yml le
        renseigne sous une forme du type "SFT 2026".
        """
        if not communication.id:
            raise DOIConfigError(
                "Communication sans identifiant : impossible de construire "
                "le DOI (l'objet n'a pas encore été écrit en base)"
            )

        conference = current_app.conference_config.get('conference', {}) or {}
        short_name = (conference.get('short_name') or 'CF')
        short_name = re.sub(r'\s+', '', str(short_name))

        return {
            'seq': communication.id,
            'year': conference.get('year') or datetime.now().year,
            'short_name': short_name,
        }

    def _format(self, pattern, communication, key_name):
        try:
            return pattern.format(**self._placeholders(communication))
        except KeyError as e:
            raise DOIConfigError(
                f"{key_name} : variable inconnue {e} dans "
                f"conference.yml > integrations > doi"
            )
        except (ValueError, IndexError) as e:
            raise DOIConfigError(
                f"{key_name} : motif invalide ({e})"
            )
