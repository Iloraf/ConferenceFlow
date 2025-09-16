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

import yaml
import csv
import os
from pathlib import Path
from flask import current_app

class ConfigLoader:
    """Classe pour charger les configurations depuis les fichiers YAML et CSV."""
    
    def __init__(self, config_dir="app/static/content"):
        """
        Initialise le chargeur de configuration.
        
        Args:
            config_dir (str): Dossier contenant les fichiers de configuration
        """
        # Chemin relatif depuis la racine du projet
        import os
        # Obtenir le chemin du module app
        app_path = os.path.dirname(os.path.abspath(__file__))
        # Remonter d'un niveau pour avoir la racine du projet
        project_root = os.path.dirname(app_path)
        self.config_dir = Path(project_root) / config_dir
        
        self._conference_config = None
        self._themes = None
        self._email_config = None

    
    def load_conference_config(self):
        """Charge la configuration générale de la conférence depuis conference.yml"""
        config_file = self.config_dir / "conference.yml"
        
        if not config_file.exists():
            current_app.logger.warning(f"Fichier conference.yml non trouvé : {config_file}")
            return self._get_default_conference_config()
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self._conference_config = yaml.safe_load(f)
                return self._conference_config
        except Exception as e:
            current_app.logger.error(f"Erreur lors du chargement de conference.yml : {e}")
            return self._get_default_conference_config()
    
    def load_themes(self):
        """Charge les thématiques depuis themes.yml"""
        themes_file = self.config_dir / "themes.yml"
        
        if not themes_file.exists():
            current_app.logger.warning(f"Fichier themes.yml non trouvé : {themes_file}")
            return self._get_default_themes()
        
        try:
            with open(themes_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self._themes = config.get('themes', [])
                return self._themes
        except Exception as e:
            current_app.logger.error(f"Erreur lors du chargement de themes.yml : {e}")
            return self._get_default_themes()
    
    def load_email_config(self):
        """Charge la configuration des emails depuis emails.yml"""
        email_file = self.config_dir / "emails.yml"
        
        if not email_file.exists():
            current_app.logger.warning(f"Fichier emails.yml non trouvé : {email_file}")
            return self._get_default_email_config()
        
        try:
            with open(email_file, 'r', encoding='utf-8') as f:
                self._email_config = yaml.safe_load(f)
                return self._email_config
        except Exception as e:
            current_app.logger.error(f"Erreur lors du chargement de emails.yml : {e}")
            return self._get_default_email_config()

    # === NOUVELLES MÉTHODES POUR LES EMAILS ===

    def get_email_template_variables(self):
        """Récupère les variables pour les templates d'emails depuis conference.yml"""
        conference_config = self.load_conference_config()
        
        variables = {}
        
        # Extraire les variables selon la configuration des emails
        email_config = self.load_email_config()
        auto_variables = email_config.get('settings', {}).get('auto_variables', {})
        
        for var_name, config_path in auto_variables.items():
            value = self._get_nested_value(conference_config, config_path)
            if value:
                variables[var_name] = value
        
        return variables

    def _get_nested_value(self, data, path):
        """Récupère une valeur dans un dictionnaire imbriqué à partir d'un chemin"""
        keys = path.split('.')
        current = data
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return None

    def get_email_subject(self, template_key, **context):
        """Récupère un sujet d'email avec remplacement des variables"""
        email_config = self.load_email_config()
        
        # Récupérer le template de sujet
        subject_template = email_config.get('templates', {}).get('subjects', {}).get(template_key, '')
        
        if not subject_template:
            return f"[{template_key}] - Email non configuré"
        
        # Récupérer les variables de conference.yml
        variables = self.get_email_template_variables()
        
        # Ajouter les variables de contexte
        variables.update(context)
        
        # Remplacer les variables dans le sujet
        return self._replace_variables(subject_template, variables)

    def get_email_content(self, template_key, **context):
        """Récupère le contenu d'un email avec remplacement des variables"""
        email_config = self.load_email_config()
        
        # Récupérer le template de contenu
        content_config = email_config.get('content', {}).get(template_key, {})
        
        if not content_config:
            return {
                'greeting': 'Bonjour,',
                'intro': 'Email non configuré',
                'body': 'Ce template d\'email n\'est pas configuré.',
                'call_to_action': None
            }
        
        # Récupérer les variables de conference.yml
        variables = self.get_email_template_variables()
        
        # Ajouter les variables de contexte
        variables.update(context)
        
        # Remplacer les variables dans chaque partie du contenu
        result = {}
        for key, value in content_config.items():
            if isinstance(value, str):
                result[key] = self._replace_variables(value, variables)
            else:
                result[key] = value
        
        return result

    def get_email_signature(self, signature_type='default', **context):
        """Récupère une signature d'email avec remplacement des variables"""
        email_config = self.load_email_config()
        
        # Récupérer la signature
        signature_template = email_config.get('signatures', {}).get(signature_type, '')
        
        if not signature_template:
            signature_template = email_config.get('signatures', {}).get('default', 'Cordialement,\nL\'équipe')
        
        # Récupérer les variables de conference.yml
        variables = self.get_email_template_variables()
        
        # Ajouter les variables de contexte
        variables.update(context)
        
        # Remplacer les variables dans la signature
        return self._replace_variables(signature_template, variables)

    def get_predefined_email_template(self, template_key, **context):
        """Récupère un template d'email prédéfini pour l'interface admin"""
        email_config = self.load_email_config()
        
        # Récupérer le template prédéfini
        template_config = email_config.get('predefined_templates', {}).get(template_key, {})
        
        if not template_config:
            return {
                'subject': f'[{template_key}] - Template non configuré',
                'content': 'Ce template d\'email n\'est pas configuré.'
            }
        
        # Récupérer les variables de conference.yml
        variables = self.get_email_template_variables()
        
        # Ajouter les variables de contexte
        variables.update(context)
        
        # Remplacer les variables
        result = {}
        for key, value in template_config.items():
            if isinstance(value, str):
                result[key] = self._replace_variables(value, variables)
            else:
                result[key] = value
        
        return result

    def _replace_variables(self, text, variables):
        """Remplace les variables dans un texte"""
        if not text or not isinstance(text, str):
            return text
        
        # Remplacer les variables {VARIABLE_NAME}
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            if placeholder in text:
                # Convertir la valeur en string et gérer les valeurs None
                str_value = str(var_value) if var_value is not None else f"[{var_name}]"
                text = text.replace(placeholder, str_value)
        
        return text

    def get_admin_email_templates(self):
        """Retourne les templates d'emails pour l'interface admin."""
        # Contexte factice pour les templates
        context = {
            'COMMUNICATION_TITLE': '[TITRE_COMMUNICATION]',
            'COMMUNICATION_ID': '[ID_COMMUNICATION]'
        }
        
        templates = {}
        
        # Récupérer tous les templates prédéfinis
        email_config = self.load_email_config()
        predefined = email_config.get('predefined_templates', {})
        
        for template_key, template_config in predefined.items():
            template_data = self.get_predefined_email_template(template_key, **context)
            templates[template_key] = {
                'subject': template_data.get('subject', ''),
                'content': template_data.get('content', '')
            }
        
        # Ajouter des templates par défaut si nécessaire
        if not templates:
            # Récupérer les variables de conference pour les templates par défaut
            variables = self.get_email_template_variables()
            conference_short = variables.get('CONFERENCE_SHORT_NAME', 'Congrès')
            
            templates = {
                'information': {
                    'subject': f'Information importante - {conference_short}',
                    'content': '''Bonjour [PRENOM] [NOM],

[Votre message ici]

Concernant votre communication "[TITRE_COMMUNICATION]" (ID: [ID_COMMUNICATION]),

Cordialement,
L'équipe d'organisation'''
                },
                'rappel': {
                    'subject': f'Rappel important - {conference_short}',
                    'content': '''Bonjour [PRENOM] [NOM],

Nous vous rappelons que...

Communication concernée : [TITRE_COMMUNICATION] (ID: [ID_COMMUNICATION])

Cordialement,
L'équipe d'organisation'''
                }
            }
        
        return templates

    # === MÉTHODES EXISTANTES ===

    def reload_all_configs(self):
        """Force le rechargement de toutes les configurations."""
        try:
            # Réinitialiser le cache
            self._conference_config = None
            self._themes = None
            self._email_config = None
        
            # Recharger toutes les configurations
            conference_config = self.load_conference_config()
            themes_config = self.load_themes()
            email_config = self.load_email_config()
        
            return {
                'success': True,
                'message': 'Configuration rechargée avec succès',
                'details': {
                    'conference_sections': len(conference_config.keys()) if conference_config else 0,
                    'themes_count': len(themes_config) if themes_config else 0,
                    'email_templates': len(email_config.get('templates', {})) if email_config else 0
                }
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Erreur lors du rechargement: {str(e)}',
                'details': {}
            }

    def get_config_status(self):
        """Retourne le statut actuel des configurations."""
        status = {
            'conference_yml': {
                'loaded': self._conference_config is not None,
                'file_exists': (self.config_dir / "conference.yml").exists(),
                'sections': len(self._conference_config.keys()) if self._conference_config else 0
            },
            'themes_yml': {
                'loaded': self._themes is not None,
                'file_exists': (self.config_dir / "themes.yml").exists(),
                'count': len(self._themes) if self._themes else 0
            },
            'email_yml': {
                'loaded': self._email_config is not None,
                'file_exists': (self.config_dir / "emails.yml").exists(),
                'templates': len(self._email_config.get('templates', {})) if self._email_config else 0
            }
        }
        return status

        
    def load_csv_data(self, filename):
        """
        Charge des données depuis un fichier CSV.
        
        Args:
            filename (str): Nom du fichier CSV dans config/data/
            
        Returns:
            list: Liste de dictionnaires représentant les lignes du CSV
        """
        csv_file = self.config_dir / "data" / filename
        
        if not csv_file.exists():
            current_app.logger.warning(f"Fichier CSV non trouvé : {csv_file}")
            return []
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                return [row for row in reader]
        except Exception as e:
            current_app.logger.error(f"Erreur lors du chargement de {filename} : {e}")
            return []
    
    def _get_default_conference_config(self):
        """Configuration par défaut si le fichier YAML n'existe pas"""
        return {
            'conference': {
                'name': 'ConferenceFlow Demo',
                'short_name': 'CF Demo',
                'theme': 'Configuration par défaut',
                'year': 2024
            },
            'dates': {
                'start': '2024-06-01',
                'end': '2024-06-04'
            },
            'location': {
                'venue': 'Centre de congrès',
                'city': 'Ville',
                'country': 'France'
            },
            'contacts': {
                'general': {
                    'email': 'contact@conference.fr'
                }
            }
        }

    def load_sponsors(self):
        """Charge la configuration des sponsors depuis sponsors.yml"""
        sponsors_file = self.config_dir / "sponsors.yml"
        
        if not sponsors_file.exists():
            current_app.logger.warning(f"Fichier sponsors.yml non trouvé : {sponsors_file}")
            return self._get_default_sponsors()
        
        try:
            with open(sponsors_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config
        except Exception as e:
            current_app.logger.error(f"Erreur lors du chargement de sponsors.yml : {e}")
            return self._get_default_sponsors()
    
    def _get_default_sponsors(self):
        """Configuration par défaut pour les sponsors"""
        return {
            'title': 'Parrainages',
            'introduction': 'Le congrès bénéficie du soutien des organismes suivants :',
            'sponsors': []
        }

    
    def _get_default_themes(self):
        """Thématiques par défaut (celles actuellement dans models.py)"""
        return [
            {
                'code': 'COND', 
                'nom': 'Conduction, convection, rayonnement',
                'description': 'Transferts de chaleur par conduction, convection et rayonnement',
                'couleur': '#dc3545',
                'actif': True
            },
            {
                'code': 'MULTI', 
                'nom': 'Changement de phase et transferts multiphasiques',
                'description': 'Phénomènes de changement de phase et écoulements multiphasiques',
                'couleur': '#20c997',
                'actif': True
            },
            {
                'code': 'POREUX', 
                'nom': 'Transferts en milieux poreux',
                'description': 'Transferts de masse et de chaleur en milieux poreux',
                'couleur': '#0dcaf0',
                'actif': True
            },
            {
                'code': 'MICRO', 
                'nom': 'Micro et nanothermique',
                'description': 'Transferts thermiques à l\'échelle micro et nanométrique',
                'couleur': '#198754',
                'actif': True
            },
            {
                'code': 'BIO', 
                'nom': 'Thermique du vivant',
                'description': 'Applications thermiques dans le domaine du vivant',
                'couleur': '#fd7e14',
                'actif': True
            },
            {
                'code': 'SYST', 
                'nom': 'Énergétique des systèmes',
                'description': 'Énergétique et optimisation des systèmes',
                'couleur': '#d63384',
                'actif': True
            },
            {
                'code': 'COMBUST', 
                'nom': 'Combustion et flammes',
                'description': 'Phénomènes de combustion et étude des flammes',
                'couleur': '#ff6b35',
                'actif': True
            },
            {
                'code': 'MACHINE', 
                'nom': 'Machines thermiques et frigorifiques',
                'description': 'Machines thermiques, pompes à chaleur, systèmes frigorifiques',
                'couleur': '#007bff',
                'actif': True
            },
            {
                'code': 'ECHANG', 
                'nom': 'Échangeurs de chaleur',
                'description': 'Conception et optimisation des échangeurs de chaleur',
                'couleur': '#6f42c1',
                'actif': True
            },
            {
                'code': 'STOCK', 
                'nom': 'Stockage thermique',
                'description': 'Technologies de stockage de l\'énergie thermique',
                'couleur': '#6610f2',
                'actif': True
            },
            {
                'code': 'RENOUV', 
                'nom': 'Énergies renouvelables',
                'description': 'Applications thermiques des énergies renouvelables',
                'couleur': '#28a745',
                'actif': True
            },
            {
                'code': 'BATIM', 
                'nom': 'Thermique du bâtiment',
                'description': 'Efficacité énergétique et confort thermique des bâtiments',
                'couleur': '#ffc107',
                'actif': True
            },
            {
                'code': 'INDUS', 
                'nom': 'Thermique industrielle',
                'description': 'Applications thermiques dans l\'industrie',
                'couleur': '#17a2b8',
                'actif': True
            },
            {
                'code': 'METRO', 
                'nom': 'Métrologie et techniques inverses',
                'description': 'Mesures thermiques et méthodes inverses',
                'couleur': '#6c757d',
                'actif': True
            },
            {
                'code': 'SIMUL', 
                'nom': 'Modélisation et simulation numérique',
                'description': 'Méthodes numériques et modélisation en thermique',
                'couleur': '#343a40',
                'actif': True
            }
        ]
    
    def _get_default_email_config(self):
        """Configuration email par défaut si le fichier n'existe pas."""
        return {
            'metadata': {
                'name': 'Configuration par défaut',
                'version': '1.0'
            },
            'templates': {
                'subjects': {
                    'welcome': 'Bienvenue au congrès',
                    'activation': 'Activez votre compte',
                    'coauthor_notification': 'Nouvelle communication',
                    'review_reminder': 'Rappel : Reviews en attente'
                }
            },
            'content': {
                'welcome': {
                    'greeting': 'Bonjour,',
                    'intro': 'Bienvenue !',
                    'body': 'Votre compte a été créé.'
                },
                'coauthor_notification': {
                    'greeting': 'Bonjour,',
                    'intro': 'Vous avez été ajouté comme co-auteur',
                    'body': 'Une nouvelle communication a été soumise.'
                }
            },
            'signatures': {
                'default': 'Cordialement,\nL\'équipe'
            },
            'settings': {
                'auto_variables': {
                    'CONFERENCE_NAME': 'conference.name',
                    'CONFERENCE_SHORT_NAME': 'conference.short_name',
                    'CONTACT_EMAIL': 'contacts.general.email'
                }
            }
        }


class ThematiqueLoader:
    """Classe utilitaire pour charger les thématiques depuis la configuration."""
    
    @staticmethod
    def load_themes():
        """Charge toutes les thématiques depuis themes.yml"""
        loader = ConfigLoader()
        return loader.load_themes()
    
    @staticmethod 
    def get_active_themes():
        """Retourne seulement les thématiques actives"""
        themes = ThematiqueLoader.load_themes()
        return [t for t in themes if t.get('actif', True)]
    
    @staticmethod
    def get_theme_by_code(code):
        """Récupère une thématique par son code"""
        themes = ThematiqueLoader.load_themes()
        return next((t for t in themes if t['code'] == code.upper()), None)
    
    @staticmethod
    def is_valid_code(code):
        """Vérifie si un code de thématique est valide"""
        theme = ThematiqueLoader.get_theme_by_code(code)
        return theme is not None and theme.get('actif', True)

