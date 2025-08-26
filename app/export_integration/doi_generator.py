# app/export_integration/doi_generator.py
"""
Générateur de DOI pour Conference Flow
"""
from datetime import datetime
from flask import current_app

class DOIGenerator:
    """Génère des DOI selon le format SFT"""
    
    def __init__(self):
        self.base_prefix = "10.25855"  # Préfixe DOI de la SFT
    
    def generate_doi(self, communication):
        """Génère un DOI selon le format: 10.25855/SFT2026-XXX"""
        
        # Récupérer les infos de la conférence
        config = current_app.conference_config
        conference = config.get('conference', {})
        
        # Année et code de la conférence
        year = conference.get('year', datetime.now().year)
        short_name = conference.get('short_name', 'CF')
        
        # Numéro séquentiel (ID de la communication, paddé sur 3 chiffres)
        seq_num = str(communication.id).zfill(3)
        
        # Construction du DOI
        doi = f"{self.base_prefix}/{short_name}{year}-{seq_num}"
        
        return doi
    
    def validate_doi(self, doi):
        """Valide le format d'un DOI"""
        if not doi:
            return False
        
        # Format attendu: 10.25855/XXXYYY-ZZZ
        import re
        pattern = r'^10\.25855\/[A-Z]+\d{4}-\d{3}$'
        return bool(re.match(pattern, doi))
