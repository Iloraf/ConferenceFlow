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

import logging
import re

try:
    import PyPDF2
    PDF_EXTRACTION_AVAILABLE = True
except ImportError:
    PDF_EXTRACTION_AVAILABLE = False

class PDFExtractor:
    """Classe pour extraire des résumés depuis les fichiers PDF"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_abstract_from_pdf(self, pdf_path):
        """
        Extrait le résumé d'un fichier PDF
        
        Args:
            pdf_path: Chemin vers le fichier PDF
            
        Returns:
            str: Le résumé extrait, ou None si non trouvé
        """
        if not PDF_EXTRACTION_AVAILABLE:
            self.logger.warning("PyPDF2 non disponible pour l'extraction PDF")
            return None
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                # Extraire le texte des premières pages (généralement 1-2)
                text = ""
                max_pages = min(len(reader.pages), 3)
                
                for page_num in range(max_pages):
                    page = reader.pages[page_num]
                    text += page.extract_text() + "\n"
                
                # Rechercher le résumé dans le texte
                abstract = self._find_abstract_in_text(text)
                
                if abstract:
                    self.logger.info(f"Résumé extrait avec succès depuis {pdf_path}")
                    return abstract
                else:
                    self.logger.warning(f"Aucun résumé trouvé dans {pdf_path}")
                    return None
        
        except Exception as e:
            self.logger.error(f"Erreur extraction PDF {pdf_path}: {e}")
            return None
    
    def _find_abstract_in_text(self, text):
        """
        Recherche le résumé dans le texte extrait du PDF
        
        Args:
            text: Texte complet du PDF
            
        Returns:
            str: Le résumé trouvé, ou None
        """
        # Nettoyer le texte
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = ' '.join(text.split())  # Supprimer les espaces multiples
        
        # Motifs de recherche pour identifier le résumé
        patterns = [
            # Format français
            r'Résumé\s*:?\s*(.*?)(?:Mots[-\s]*clés|Keywords|Abstract|Introduction|\n\n)',
            r'RÉSUMÉ\s*:?\s*(.*?)(?:MOTS[-\s]*CLÉS|KEYWORDS|ABSTRACT|INTRODUCTION)',
            
            # Format anglais
            r'Abstract\s*:?\s*(.*?)(?:Keywords|Mots[-\s]*clés|Introduction|\n\n)',
            r'ABSTRACT\s*:?\s*(.*?)(?:KEYWORDS|MOTS[-\s]*CLÉS|INTRODUCTION)',
            
            # Formats plus flexibles
            r'(?:Résumé|Abstract)\s*[:\-]?\s*(.*?)(?:(?:Mots[-\s]*clés|Keywords|Introduction|1\.|I\.|\d+\s+[A-Z])[^a-z])',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                abstract_text = match.group(1).strip()
                
                # Vérifications de qualité
                if self._is_valid_abstract(abstract_text):
                    return self._clean_abstract(abstract_text)
        
        return None
    
    def _is_valid_abstract(self, text):
        """
        Vérifie si le texte extrait ressemble à un résumé valide
        
        Args:
            text: Texte candidat pour le résumé
            
        Returns:
            bool: True si le texte semble être un résumé valide
        """
        if not text or len(text.strip()) < 50:
            return False
        
        if len(text) > 3000:  # Trop long pour être un résumé
            return False
        
        # Vérifier qu'il n'y a pas trop de caractères spéciaux/formules
        special_chars = sum(1 for c in text if c in '\\{}[]()$^_')
        if special_chars > len(text) * 0.1:  # Plus de 10% de caractères spéciaux
            return False
        
        return True
    
    def _clean_abstract(self, text):
        """
        Nettoie le texte du résumé extrait
        
        Args:
            text: Texte brut du résumé
            
        Returns:
            str: Texte nettoyé
        """
        # Supprimer les caractères de fin de ligne multiples
        text = re.sub(r'\s+', ' ', text)
        
        # Supprimer les références LaTeX restantes
        text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', text)
        text = re.sub(r'\\[a-zA-Z]+', '', text)
        
        # Nettoyer les caractères spéciaux
        text = text.replace('{', '').replace('}', '')
        text = text.replace('$', '')
        
        # Nettoyer les espaces
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        
        return text

# Fonction utilitaire pour l'export_manager
def extract_abstract_from_pdf(pdf_path):
    """
    Fonction wrapper pour maintenir la compatibilité
    
    Args:
        pdf_path: Chemin vers le fichier PDF
        
    Returns:
        str: Le résumé extrait ou None
    """
    extractor = PDFExtractor()
    return extractor.extract_abstract_from_pdf(pdf_path)
