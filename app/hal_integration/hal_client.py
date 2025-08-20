"""
Client HAL spécialisé pour Conference Flow - SFT 2026
Mode TEST uniquement pour le développement
"""

import requests
import base64
import os
import hashlib
import zipfile
from xml.etree import ElementTree as ET
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
from flask import current_app

class HALClient:
    """Client HAL intégré à Conference Flow"""
    
    def __init__(self, test_mode: bool = True):
        """
        Initialise le client HAL en mode TEST
        
        Args:
            test_mode: True pour utiliser l'environnement de test (OBLIGATOIRE pour dev)
        """
        self.test_mode = test_mode
        self.logger = logging.getLogger(__name__)
        
        # SÉCURITÉ: Force le mode test en développement
        if not test_mode:
            raise ValueError("Mode production désactivé en développement!")
        
        # Configuration depuis les variables d'environnement
        self.username = os.getenv('HAL_USERNAME')
        self.password = os.getenv('HAL_PASSWORD')
        
        if not self.username or not self.password:
            raise ValueError("HAL_USERNAME et HAL_PASSWORD requis dans .env")
        
        # URLs selon l'environnement (TEST uniquement)
        self.base_url = "https://api-preprod.archives-ouvertes.fr/sword"
        self.collection_id = "SFT2026"
        
        # Authentification
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'User-Agent': 'ConferenceFlow-HAL/1.0'
        }
        
        self.logger.info(f"HAL Client initialisé en mode TEST")
    
    def check_connection(self) -> Tuple[bool, str]:
        """
        Vérifie la connexion à HAL et l'accès à la collection SFT2026
        
        Returns:
            Tuple[bool, str]: (succès, message)
        """
        try:
            # Test 1: Service document
            response = requests.get(f"{self.base_url}/servicedocument", 
                                  headers=self.headers, timeout=30)
            
            if response.status_code == 401:
                return False, "Identifiants HAL incorrects"
            elif response.status_code != 200:
                return False, f"Erreur service HAL: {response.status_code}"
            
            # Test 2: Collection SFT2026
            collection_response = requests.get(f"{self.base_url}/{self.collection_id}", 
                                             headers=self.headers, timeout=30)
            
            if collection_response.status_code == 200:
                return True, "Connexion HAL OK - Collection SFT2026 accessible"
            elif collection_response.status_code == 404:
                return True, "Connexion HAL OK - Collection SFT2026 pas encore visible"
            else:
                return False, f"Erreur collection: {collection_response.status_code}"
                
        except requests.RequestException as e:
            return False, f"Erreur connexion: {str(e)}"
    
    def test_deposit_metadata(self, xml_content: str) -> Tuple[bool, Dict]:
        """
        Test de dépôt de métadonnées uniquement (mode test)
        
        Args:
            xml_content: Contenu XML HAL
            
        Returns:
            Tuple[bool, Dict]: (succès, données_réponse)
        """
        url = f"{self.base_url}/hal"
        
        headers = self.headers.copy()
        headers.update({
            'Content-Type': 'text/xml',
            'Packaging': 'http://purl.org/net/sword-types/AOfr',
            'Content-MD5': self._calculate_md5(xml_content),
            'X-test': '1'  # Mode test - OBLIGATOIRE
        })
        
        try:
            self.logger.info("Test de dépôt HAL en cours...")
            response = requests.post(url, 
                                   data=xml_content.encode('utf-8'), 
                                   headers=headers,
                                   timeout=60)
            
            if response.status_code in [200, 201, 202]:
                result = self._parse_response(response)
                self.logger.info(f"Test dépôt réussi: {result.get('id', 'N/A')}")
                return True, result
            else:
                error_msg = self._parse_error(response)
                self.logger.error(f"Échec test dépôt: {error_msg}")
                return False, {'error': error_msg, 'status_code': response.status_code}
                
        except requests.RequestException as e:
            self.logger.error(f"Erreur réseau test dépôt: {e}")
            return False, {'error': str(e)}
    
    def get_deposit_status(self, hal_id: str, version: Optional[int] = None) -> Tuple[bool, Dict]:
        """
        Récupère le statut d'un dépôt HAL
        
        Args:
            hal_id: Identifiant HAL (ex: hal-00000001)
            version: Numéro de version (optionnel)
            
        Returns:
            Tuple[bool, Dict]: (succès, informations_statut)
        """
        url_id = f"{hal_id}v{version}" if version else hal_id
        url = f"{self.base_url}/{url_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                # Parser le XML de statut
                root = ET.fromstring(response.content)
                status = root.find('status')
                comment = root.find('comment')
                
                return True, {
                    'id': hal_id,
                    'version': version,
                    'status': status.text if status is not None else 'inconnu',
                    'comment': comment.text if comment is not None else ''
                }
            else:
                return False, {'error': f'Status HTTP: {response.status_code}'}
                
        except Exception as e:
            return False, {'error': str(e)}
    
    def _calculate_md5(self, content: str) -> str:
        """Calcule le MD5 d'un contenu"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _parse_response(self, response) -> Dict:
        """Parse une réponse SWORD HAL"""
        try:
            root = ET.fromstring(response.content)
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'hal': 'http://hal.archives-ouvertes.fr/',
                'sword': 'http://purl.org/net/sword/'
            }
            
            result = {'status_code': response.status_code}
            
            # Extraire les informations principales
            hal_id = root.find('atom:id', namespaces)
            if hal_id is not None:
                result['id'] = hal_id.text
            
            hal_version = root.find('hal:version', namespaces)
            if hal_version is not None:
                result['version'] = hal_version.text
            
            hal_password = root.find('hal:password', namespaces)
            if hal_password is not None:
                result['password'] = hal_password.text
            
            link = root.find('atom:link[@rel="alternate"]', namespaces)
            if link is not None:
                result['url'] = link.get('href')
            
            treatment = root.find('sword:treatment', namespaces)
            if treatment is not None:
                result['treatment'] = treatment.text
            
            return result
            
        except ET.ParseError:
            return {'status_code': response.status_code, 'raw_response': response.content.decode()}
    
    def _parse_error(self, response) -> str:
        """Parse une erreur SWORD"""
        try:
            root = ET.fromstring(response.content)
            
            # Erreur SWORD
            if root.tag.endswith('error'):
                title = root.find('.//{http://www.w3.org/2005/Atom}title')
                summary = root.find('.//{http://www.w3.org/2005/Atom}summary')
                
                if title is not None and summary is not None:
                    return f"{title.text}: {summary.text}"
                elif summary is not None:
                    return summary.text
            
            return f"Erreur HTTP {response.status_code}"
            
        except:
            return f"Erreur HTTP {response.status_code}: {response.content.decode()[:200]}"

