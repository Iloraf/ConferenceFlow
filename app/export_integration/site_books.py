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

import os
import shutil
import logging
from datetime import datetime

from flask import current_app


class SiteBooksGenerator:
    """
    Compile les deux livres numériques destinés à l'archive SFT et les
    dépose sous un nom stable, indépendamment de la médiathèque.

    Les actes sont produits en un seul volume, sans découpage en tomes.
    """

    OUTPUT_SUBDIR = 'uploads/site_sft'

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Génération
    # ------------------------------------------------------------------

    def generate_proceedings(self):
        """
        Compile les actes complets, tous les articles acceptés groupés
        par thématique, en un seul volume.

        Retourne le chemin du fichier déposé.
        """
        from ..conference_books import (
            get_communications_by_type_and_status,
            group_communications_by_thematique,
            compile_latex_book,
        )

        communications = get_communications_by_type_and_status()
        articles = communications['articles_acceptes']

        if not articles:
            raise RuntimeError("Aucun article accepté : actes impossibles")

        grouped = group_communications_by_thematique(articles)

        # book_type 'tome1' sélectionne le fichier « article » de chaque
        # communication ; le titre « Actes » pilote la page de couverture.
        pdf_path = compile_latex_book("Actes", grouped, 'tome1')

        return self._deposit(pdf_path, self.target_name('proceedings'))

    def generate_abstracts_book(self):
        """
        Compile le recueil des résumés et des Work in Progress.

        Retourne le chemin du fichier déposé.
        """
        from ..conference_books import (
            get_communications_by_type_and_status,
            group_communications_by_thematique,
            compile_latex_book,
        )

        communications = get_communications_by_type_and_status()
        all_communications = (
            communications['resumes'] + communications['wips']
        )

        if not all_communications:
            raise RuntimeError("Aucun résumé : recueil impossible")

        grouped = group_communications_by_thematique(all_communications)
        pdf_path = compile_latex_book(
            "Résumés et Work in Progress", grouped, 'resumes-wip'
        )

        return self._deposit(pdf_path, self.target_name('abstracts_book'))

    def generate_all(self):
        """
        Compile les deux livres. Retourne un rapport détaillant chaque
        opération, sans interrompre la seconde si la première échoue.
        """
        report = []

        for label, method in (
            ("Actes", self.generate_proceedings),
            ("Recueil des résumés", self.generate_abstracts_book),
        ):
            entry = {'livre': label, 'fichier': None, 'error': None}
            try:
                path = method()
                entry['fichier'] = os.path.basename(path)
                entry['taille_octets'] = os.path.getsize(path)
            except Exception as e:
                entry['error'] = str(e)
                self.logger.error(f"Génération {label} : {e}")
            report.append(entry)

        return report

    # ------------------------------------------------------------------
    # Emplacement et nommage
    # ------------------------------------------------------------------

    def output_dir(self):
        """Dossier de dépôt, créé au besoin."""
        path = os.path.join(current_app.static_folder, self.OUTPUT_SUBDIR)
        os.makedirs(path, exist_ok=True)
        return path

    def target_name(self, key):
        """
        Nom attendu dans l'archive SFT, lu dans
        conference.yml > integrations > site_sft.

        key vaut 'proceedings' ou 'abstracts_book'.
        """
        config = current_app.conference_config
        site = config.get('integrations', {}).get('site_sft', {}) or {}
        conference = config.get('conference', {}) or {}
        year = conference.get('year', datetime.now().year)

        defaults = {
            'proceedings': "Actes_SFT{year}.pdf",
            'abstracts_book': "Resumes_SFT{year}.pdf",
        }
        pattern = site.get(f'{key}_filename') or defaults[key]

        return pattern.format(year=year)

    def status(self):
        """
        Indique, pour chaque livre, s'il est présent et depuis quand.
        """
        result = {}
        for key in ('proceedings', 'abstracts_book'):
            name = self.target_name(key)
            path = os.path.join(self.output_dir(), name)
            if os.path.exists(path):
                result[key] = {
                    'fichier': name,
                    'present': True,
                    'taille_octets': os.path.getsize(path),
                    'modifie': datetime.fromtimestamp(
                        os.path.getmtime(path)
                    ).isoformat(timespec='seconds'),
                }
            else:
                result[key] = {'fichier': name, 'present': False}
        return result

    def path_for(self, key):
        """Chemin du livre déposé, ou None s'il est absent."""
        path = os.path.join(self.output_dir(), self.target_name(key))
        return path if os.path.exists(path) else None

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _deposit(self, source, target_name):
        """
        Copie le PDF compilé sous son nom définitif.

        compile_latex_book renvoie tantôt un chemin absolu, tantôt un
        chemin relatif à la racine de l'application : les deux sont
        acceptés.
        """
        if not os.path.isabs(source):
            source = os.path.join(current_app.root_path, source)

        if not os.path.exists(source):
            raise RuntimeError(f"PDF compilé introuvable : {source}")

        destination = os.path.join(self.output_dir(), target_name)
        shutil.copy2(source, destination)

        self.logger.info(
            f"Livre déposé : {destination} "
            f"({os.path.getsize(destination)} octets)"
        )
        return destination
