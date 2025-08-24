#!/usr/bin/env python3
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

"""
Script pour vérifier vos droits sur HAL
ÉTAPE 1.1 : Vérification des permissions
"""

import requests
import base64
from xml.etree import ElementTree as ET

def check_hal_permissions(username, password):
    """
    Vérifie les permissions HAL d'un utilisateur
    """
    print("🔍 Vérification des droits HAL en cours...\n")
    
    # URL de test pour l'environnement de développement
    base_url = "https://api-preprod.archives-ouvertes.fr/sword"
    
    # Authentification HTTP Basic
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'User-Agent': 'HAL-Rights-Checker/1.0'
    }
    
    # Test 1: Connexion de base
    print("1️⃣ Test de connexion...")
    try:
        response = requests.get(f"{base_url}/servicedocument", headers=headers)
        if response.status_code == 200:
            print("   ✅ Connexion réussie")
        elif response.status_code == 401:
            print("   ❌ Identifiants incorrects")
            return False
        else:
            print(f"   ⚠️ Réponse inattendue: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erreur de connexion: {e}")
        return False
    
    # Test 2: Vérification des collections disponibles
    print("\n2️⃣ Vérification des collections disponibles...")
    try:
        root = ET.fromstring(response.content)
        namespaces = {
            'app': 'http://www.w3.org/2007/app',
            'atom': 'http://www.w3.org/2005/Atom'
        }
        
        collections = root.findall('.//app:collection', namespaces)
        if collections:
            print("   ✅ Collections trouvées:")
            for collection in collections:
                title = collection.find('atom:title', namespaces)
                href = collection.get('href')
                if title is not None:
                    print(f"      - {title.text}: {href}")
        else:
            print("   ⚠️ Aucune collection trouvée")
            
    except Exception as e:
        print(f"   ❌ Erreur parsing XML: {e}")
    
    # Test 3: Tentative de dépôt de test (pour vérifier les droits de dépôt)
    print("\n3️⃣ Test des droits de dépôt...")
    test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title>Test de droits - À SUPPRIMER</title>
            </titleStmt>
            <publicationStmt>
                <distributor>CCSD</distributor>
            </publicationStmt>
            <sourceDesc>
                <p>Document de test des droits</p>
            </sourceDesc>
        </fileDesc>
        <profileDesc>
            <textClass>
                <classCode scheme="halDomain" n="info">Informatique</classCode>
                <classCode scheme="halTypology" n="REPORT">Rapport</classCode>
            </textClass>
        </profileDesc>
    </teiHeader>
    <text><body><p>Test</p></body></text>
</TEI>"""
    
    test_headers = headers.copy()
    test_headers.update({
        'Content-Type': 'text/xml',
        'Packaging': 'http://purl.org/net/sword-types/AOfr',
        'X-test': '1'  # Mode test pour ne pas créer de vrai dépôt
    })
    
    try:
        response = requests.post(f"{base_url}/hal", 
                               data=test_xml.encode('utf-8'), 
                               headers=test_headers)
        
        if response.status_code in [200, 201, 202]:
            print("   ✅ Droits de dépôt confirmés")
            # Essayer de parser la réponse pour voir l'ID créé
            try:
                root = ET.fromstring(response.content)
                hal_id = root.find('.//{http://www.w3.org/2005/Atom}id')
                if hal_id is not None:
                    print(f"      Test ID créé: {hal_id.text}")
            except:
                pass
                
        elif response.status_code == 403:
            print("   ❌ Droits de dépôt insuffisants")
        else:
            print(f"   ⚠️ Réponse inattendue: {response.status_code}")
            if response.content:
                print(f"      Détails: {response.content.decode()[:200]}...")
                
    except Exception as e:
        print(f"   ❌ Erreur test dépôt: {e}")
    
    # Test 4: Vérification spécifique pour les collections
    print("\n4️⃣ Test spécifique collection SFT2026...")
    
    # Tentative d'accès à une collection spécifique
    try:
        # D'abord, essayer de voir si SFT2026 existe déjà
        collection_url = f"{base_url}/SFT2026"
        response = requests.get(collection_url, headers=headers)
        
        if response.status_code == 200:
            print("   ✅ Collection SFT2026 existe déjà !")
        elif response.status_code == 404:
            print("   ⚠️ Collection SFT2026 n'existe pas encore")
            print("   📝 Vous devrez la créer via l'interface web HAL")
        else:
            print(f"   ⚠️ Statut collection: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Erreur vérification collection: {e}")
    
    return True

def main():
    print("=== Vérificateur de droits HAL ===\n")
    
    # Demande des identifiants
    print("Entrez vos identifiants HAL pour vérifier vos droits:")
    username = input("Login HAL: ").strip()
    
    if not username:
        print("❌ Login requis")
        return
    
    # Note: En production, utilisez getpass pour masquer le mot de passe
    import getpass
    try:
        password = getpass.getpass("Mot de passe HAL: ")
    except:
        # Fallback si getpass ne fonctionne pas
        password = input("Mot de passe HAL: ").strip()
    
    if not password:
        print("❌ Mot de passe requis")
        return
    
    # Lancer les vérifications
    success = check_hal_permissions(username, password)
    
    if success:
        print("\n" + "="*50)
        print("📋 RÉSUMÉ DES ACTIONS RECOMMANDÉES:")
        print("="*50)
        print("1. Si droits de dépôt ✅: Vous pouvez utiliser l'API SWORD")
        print("2. Si collection SFT2026 n'existe pas: Créez-la via l'interface web")
        print("3. Étape suivante: Tester un premier dépôt en mode test")
        print("\n🎯 Vous êtes prêt pour l'ÉTAPE 2 !")
    else:
        print("\n❌ Problème détecté. Contactez le support HAL si nécessaire.")

if __name__ == "__main__":
    main()
