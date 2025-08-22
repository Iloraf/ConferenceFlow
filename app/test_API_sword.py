#!/usr/bin/env python3
"""
Script de test pour l'API SWORD de HAL
Étape 1 : Test de connexion et récupération du service document
"""

import requests
import base64
from xml.etree import ElementTree as ET

class HALSwordClient:
    def __init__(self, username, password, use_test_env=True):
        """
        Initialise le client SWORD pour HAL
        
        Args:
            username (str): Login HAL
            password (str): Mot de passe HAL
            use_test_env (bool): True pour utiliser l'environnement de test
        """
        self.username = username
        self.password = password
        
        if use_test_env:
            self.base_url = "https://api-preprod.archives-ouvertes.fr/sword"
        else:
            self.base_url = "https://api.archives-ouvertes.fr/sword"
        
        # Préparer l'authentification HTTP Basic
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'User-Agent': 'HAL-SWORD-Client/1.0'
        }
    
    def get_service_document(self):
        """
        Récupère le document de service SWORD
        Permet de vérifier la connexion et les capacités de l'API
        """
        url = f"{self.base_url}/servicedocument"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            print(f"✅ Connexion réussie à HAL SWORD")
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'Non spécifié')}")
            
            # Parse du XML pour extraire les informations utiles
            root = ET.fromstring(response.content)
            
            # Afficher les collections disponibles
            namespaces = {
                'app': 'http://www.w3.org/2007/app',
                'atom': 'http://www.w3.org/2005/Atom',
                'sword': 'http://purl.org/net/sword/'
            }
            
            collections = root.findall('.//app:collection', namespaces)
            print(f"\n📁 Collections disponibles:")
            for collection in collections:
                title = collection.find('atom:title', namespaces)
                href = collection.get('href')
                if title is not None and href:
                    print(f"  - {title.text}: {href}")
            
            return response.content
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur de connexion: {e}")
            return None
        except ET.ParseError as e:
            print(f"❌ Erreur de parsing XML: {e}")
            return None

def main():
    print("=== Test de connexion à l'API SWORD HAL ===\n")
    
    # TODO: Remplacer par vos vrais identifiants
    username = "olivier-farges"
    password = "t34aG&iJmz+UZC}["
    
    if username == "VOTRE_LOGIN_HAL":
        print("⚠️  Veuillez remplacer les identifiants de test dans le script")
        return
    
    # Créer le client en mode test
    client = HALSwordClient(username, password, use_test_env=True)
    
    # Tester la connexion
    service_doc = client.get_service_document()
    
    if service_doc:
        print("\n✅ Test de connexion terminé avec succès")
        print("\nÉtape suivante : Créer un fichier XML de métadonnées pour un dépôt de test")
    else:
        print("\n❌ Échec du test de connexion")
        print("Vérifiez vos identifiants et votre connexion internet")

if __name__ == "__main__":
    main()
