"""
Gestionnaire des zones d'accès pour Conference Flow
"""
import yaml
import os
from flask import current_app
from pathlib import Path





class ZonesManager:
    """Gestionnaire simple pour les zones d'accès de l'application."""
    
    def __init__(self):
        self.zones_file = Path(current_app.root_path) / 'static' / 'content' / 'zones.yml'
    
    def load_zones_config(self):
        """Charge la configuration des zones depuis le fichier YAML."""
        try:
            if not self.zones_file.exists():
                # Créer le fichier avec la config par défaut si il n'existe pas
                self._create_default_config()
            
            with open(self.zones_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('zones', {})
        except Exception as e:
            current_app.logger.error(f"Erreur chargement zones.yml: {e}")
            return self._get_default_zones()
    
    def save_zones_config(self, zones_config):
        """Sauvegarde la configuration des zones."""
        try:
            config = {'zones': zones_config}
            with open(self.zones_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
            return True
        except Exception as e:
            current_app.logger.error(f"Erreur sauvegarde zones.yml: {e}")
            return False
    
    def is_zone_open(self, zone_name):
        """Vérifie si une zone est ouverte."""
        zones = self.load_zones_config()
        zone = zones.get(zone_name, {})
        return zone.get('is_open', False)
    
    def get_zone_message(self, zone_name):
        """Récupère le message d'une zone fermée."""
        zones = self.load_zones_config()
        zone = zones.get(zone_name, {})
        return zone.get('message', 'Cette zone sera bientôt disponible.')
    
    def get_zone_info(self, zone_name):
        """Récupère toutes les infos d'une zone."""
        zones = self.load_zones_config()
        return zones.get(zone_name, {})
    
    def toggle_zone(self, zone_name):
        """Bascule l'état d'une zone."""
        zones = self.load_zones_config()
        if zone_name in zones:
            zones[zone_name]['is_open'] = not zones[zone_name].get('is_open', False)
            return self.save_zones_config(zones)
        return False
    
    def set_zone_status(self, zone_name, is_open, message=None):
        """Définit l'état d'une zone."""
        zones = self.load_zones_config()
        if zone_name in zones:
            zones[zone_name]['is_open'] = is_open
            if message is not None:
                zones[zone_name]['message'] = message
            return self.save_zones_config(zones)
        return False
    
    def get_all_zones(self):
        """Récupère la configuration de toutes les zones."""
        return self.load_zones_config()
    
    def _create_default_config(self):
        """Crée le fichier de configuration par défaut."""
        default_config = {
            'zones': self._get_default_zones()
        }
        
        # Créer le dossier si nécessaire
        self.zones_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.zones_file, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    def _get_default_zones(self):
        """Configuration par défaut des zones."""
        return {
            'registration': {
                'is_open': False,
                'message': 'Les inscriptions seront bientôt ouvertes.',
                'display_name': 'Création de compte et inscription',
                'description': 'Permet aux utilisateurs de créer un compte et de s\'inscrire à la conférence'
            },
            'submission': {
                'is_open': False,
                'message': 'Le dépôt de communications sera bientôt ouvert.',
                'display_name': 'Dépôt de communications',
                'description': 'Permet aux utilisateurs de soumettre leurs communications'
            }
        }


# Instance globale pour faciliter l'utilisation
zones_manager = ZonesManager()
