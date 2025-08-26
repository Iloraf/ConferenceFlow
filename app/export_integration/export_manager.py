# app/export_integration/export_manager.py
"""
Gestionnaire unifié pour les exports HAL et DOI
"""
from datetime import datetime
from flask import current_app
from ..models import Communication, db
from .hal_client import HALClient
from .hal_xml_generator import HALXMLGenerator
from .doi_generator import DOIGenerator
from .doi_xml_generator import DOIXMLGenerator

class ExportManager:
    """Gestionnaire principal pour tous les exports"""
    
    def __init__(self):
        self.hal_client = HALClient(test_mode=True)
        self.hal_xml_generator = HALXMLGenerator()
        self.doi_generator = DOIGenerator()
        self.doi_xml_generator = DOIXMLGenerator()
    
    def prepare_communication_for_export(self, communication_id: int):
        """Prépare une communication pour l'export (HAL + DOI)"""
        comm = Communication.query.get(communication_id)
        if not comm:
            return None, "Communication introuvable"
        
        # 1. Extraire le résumé du PDF si nécessaire
        if not comm.abstract:
            success, message = self._extract_abstract(comm)
            if not success:
                current_app.logger.warning(f"Extraction résumé échouée: {message}")
        
        # 2. Générer le DOI si nécessaire
        if not comm.doi:
            doi = self.doi_generator.generate_doi(comm)
            comm.doi = doi
            comm.doi_generated_at = datetime.utcnow()
        
        # 3. Préparer l'URL publique (sera remplie après dépôt HAL)
        if not comm.public_url:
            comm.public_url = None  # Sera mise à jour après HAL
        
        db.session.commit()
        return comm, "Communication préparée pour l'export"
    
    def export_to_hal(self, communication_id: int):
        """Exporte une communication vers HAL"""
        comm, message = self.prepare_communication_for_export(communication_id)
        if not comm:
            return False, message
        
        try:
            # Générer le XML HAL
            xml_content = self.hal_xml_generator.generate_for_communication(comm)
            
            # Déposer sur HAL
            success, hal_response = self.hal_client.deposit(xml_content, comm)
            
            if success:
                # Récupérer l'URL HAL et la stocker
                hal_url = hal_response.get('url')
                if hal_url:
                    comm.hal_url = hal_url
                    comm.public_url = hal_url  # URL publique = URL HAL
                    comm.hal_deposited_at = datetime.utcnow()
                    db.session.commit()
                
                return True, f"Dépôt HAL réussi. URL: {hal_url}"
            else:
                return False, f"Erreur dépôt HAL: {hal_response.get('error', 'Erreur inconnue')}"
        
        except Exception as e:
            return False, f"Erreur export HAL: {str(e)}"
    
    def generate_doi_xml(self, communication_id: int):
        """Génère le XML DataCite pour le DOI"""
        comm = Communication.query.get(communication_id)
        if not comm or not comm.doi:
            return None, "Communication ou DOI introuvable"
        
        try:
            xml_content = self.doi_xml_generator.generate_datacite_xml(comm)
            return xml_content, "XML DOI généré avec succès"
        except Exception as e:
            return None, f"Erreur génération XML DOI: {str(e)}"
    
    def get_export_status(self, communication_id: int):
        """Retourne le statut complet des exports"""
        comm = Communication.query.get(communication_id)
        if not comm:
            return None
        
        return {
            'communication_id': comm.id,
            'title': comm.title,
            'has_abstract': bool(comm.abstract),
            'has_doi': bool(comm.doi),
            'doi': comm.doi,
            'hal_deposited': bool(comm.hal_deposited_at),
            'hal_url': comm.hal_url,
            'public_url': comm.public_url,
            'ready_for_export': bool(comm.abstract and comm.doi),
            'export_date': comm.hal_deposited_at
        }
    
    def _extract_abstract(self, communication):
        """Extrait le résumé du PDF"""
        from .pdf_extractor import extract_abstract_from_pdf
        
        # Chercher le fichier PDF
        pdf_file = communication.get_file('article') or communication.get_file('résumé')
        if not pdf_file:
            return False, "Aucun fichier PDF trouvé"
        
        try:
            import os
            pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_file.file_path)
            abstract = extract_abstract_from_pdf(pdf_path)
            
            if abstract:
                communication.abstract = abstract
                db.session.commit()
                return True, "Résumé extrait avec succès"
            else:
                return False, "Résumé non trouvé dans le PDF"
        
        except Exception as e:
            return False, f"Erreur extraction: {str(e)}"
