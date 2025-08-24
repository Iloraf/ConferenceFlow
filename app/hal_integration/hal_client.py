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

class HALConfigError(Exception):
    """Exception levée en cas d'erreur de configuration HAL"""
    pass

class HALClient:
    """Client HAL intégré à Conference Flow"""
    
    def __init__(self, test_mode: bool = True):
        """
        Initialise le client HAL en mode TEST
        
        Args:
            test_mode: True pour utiliser l'environnement de test (OBLIGATOIRE pour dev)
            
        Raises:
            HALConfigError: Si la configuration HAL est incorrecte
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
        
        # NOUVEAU : Charger collection_id depuis conference.yml (OBLIGATOIRE)
        self.collection_id = self._load_collection_id()
        
        # URLs selon l'environnement (TEST uniquement)
        self.base_url = "https://api-preprod.archives-ouvertes.fr/sword"
        
        # Authentification
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'User-Agent': f'ConferenceFlow-HAL/1.0 ({self.collection_id})'
        }
        
        self.logger.info(f"HAL Client initialisé en mode TEST pour collection {self.collection_id}")
    
    def _load_collection_id(self) -> str:
        """
        Charge l'ID de collection HAL depuis conference.yml
        LÈVE UNE EXCEPTION si la configuration est manquante ou incorrecte
        """
        try:
            config = current_app.conference_config
            hal_config = config.get('integrations', {}).get('hal', {})
            
            if not hal_config:
                raise HALConfigError("Configuration HAL manquante dans conference.yml")
            
            collection_id = hal_config.get('collection_id')
            
            if not collection_id:
                raise HALConfigError("collection_id manquant dans conference.yml > integrations > hal")
            
            if not isinstance(collection_id, str) or len(collection_id.strip()) == 0:
                raise HALConfigError("collection_id invalide dans conference.yml")
            
            collection_id = collection_id.strip()
            self.logger.info(f"Collection HAL chargée depuis conference.yml: {collection_id}")
            return collection_id
            
        except AttributeError:
            raise HALConfigError("Configuration Conference Flow non disponible (current_app.conference_config)")
        except Exception as e:
            raise HALConfigError(f"Erreur lors du chargement collection_id: {e}")
    
    def check_connection(self) -> Tuple[bool, str]:
        """
        Vérifie la connexion à HAL et l'accès à la collection configurée
        
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
            
            # Test 2: Collection configurée
            collection_response = requests.get(f"{self.base_url}/{self.collection_id}", 
                                             headers=self.headers, timeout=30)
            
            if collection_response.status_code == 200:
                return True, f"Connexion HAL OK - Collection {self.collection_id} accessible"
            elif collection_response.status_code == 404:
                return True, f"Connexion HAL OK - Collection {self.collection_id} pas encore visible (normal en test)"
            else:
                return False, f"Erreur collection {self.collection_id}: {collection_response.status_code}"
                
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
        # SÉCURITÉ : Vérifier que le XML contient la bonne collection
        if self.collection_id not in xml_content:
            self.logger.warning(f"XML ne contient pas la collection {self.collection_id}")
        
        url = f"{self.base_url}/hal"
        
        headers = self.headers.copy()
        headers.update({
            'Content-Type': 'text/xml',
            'Packaging': 'http://purl.org/net/sword-types/AOfr',
            'Content-MD5': self._calculate_md5(xml_content),
            'X-test': '1'  # Mode test - OBLIGATOIRE
        })
        
        try:
            self.logger.info(f"Test de dépôt HAL en cours pour collection {self.collection_id}...")
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
                    'comment': comment.text if comment is not None else '',
                    'collection': self.collection_id
                }
            else:
                return False, {'error': f'Status HTTP: {response.status_code}'}
                
        except Exception as e:
            return False, {'error': str(e)}
    
    def get_collection_info(self) -> Dict:
        """
        Retourne les informations sur la collection configurée
        
        Returns:
            Dict: Informations de collection
        """
        try:
            config = current_app.conference_config
            hal_config = config.get('integrations', {}).get('hal', {})
            conference_info = config.get('conference', {})
            
            return {
                'collection_id': self.collection_id,
                'conference_name': conference_info.get('full_name', 'Conférence inconnue'),
                'enabled': hal_config.get('enabled', False),
                'test_mode': hal_config.get('test_mode', True),
                'auto_deposit': hal_config.get('auto_deposit', False)
            }
        except Exception as e:
            self.logger.error(f"Erreur récupération infos collection: {e}")
            return {
                'collection_id': self.collection_id,
                'error': str(e)
            }
    
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
            
            result = {
                'status_code': response.status_code,
                'collection': self.collection_id
            }
            
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
            return {
                'status_code': response.status_code, 
                'raw_response': response.content.decode(),
                'collection': self.collection_id
            }
    
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


