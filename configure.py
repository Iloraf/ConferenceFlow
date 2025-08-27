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

#!/usr/bin/env python3
"""Script de configuration locale pour ConferenceFlow."""

import sys
import subprocess
import secrets
from pathlib import Path

def print_header():
    print("🔧 Configuration ConferenceFlow")
    print("=" * 50)
    print("Ce script génère la configuration pour le déploiement")
    print()

def generate_secure_password(length=16):
    """
    Génère un mot de passe sécurisé.
    
    Args:
        length (int): Longueur du mot de passe (défaut: 16)
    
    Returns:
        str: Mot de passe généré
    """
    # Caractères autorisés (évite les caractères ambigus comme 0, O, l, I)
    letters = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    special = "!@#$%&*+"
    
    # Assurer au moins un caractère de chaque type
    password = [
        secrets.choice(letters.upper()),  # Au moins 1 majuscule
        secrets.choice(letters.lower()),  # Au moins 1 minuscule  
        secrets.choice(digits),           # Au moins 1 chiffre
        secrets.choice(special)           # Au moins 1 caractère spécial
    ]
    
    # Compléter avec des caractères aléatoires
    all_chars = letters + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))
    
    # Mélanger le mot de passe
    import random
    random.SystemRandom().shuffle(password)
    
    return ''.join(password)

def generate_vapid_keys():
    """Génère les clés VAPID - version compatible avec versions actuelles."""
    try:
        import base64
        # AJOUT DE L'IMPORT MANQUANT :
        from cryptography.hazmat.primitives import serialization
        
        # Méthode 1 : Essayer avec py_vapid moderne
        try:
            from py_vapid import Vapid01
            vapid = Vapid01()
            vapid.generate_keys()
            
            # Obtenir les clés au format DER puis les convertir
            private_der = vapid.private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_der = vapid.public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            private_key_b64 = base64.urlsafe_b64encode(private_der).decode('utf-8').rstrip('=')
            public_key_b64 = base64.urlsafe_b64encode(public_der).decode('utf-8').rstrip('=')
            
            print("✅ Clés VAPID générées avec py_vapid (méthode DER)")
            return private_key_b64, public_key_b64
            
        except Exception as e:
            print(f"⚠️ Erreur py_vapid : {e}")
            return generate_vapid_keys_simple()
            
    except ImportError:
        print("⚠️ py_vapid non disponible, tentative méthode simple...")
        return generate_vapid_keys_simple()

def generate_vapid_keys_simple():
    """Génère des clés VAPID avec cryptography - méthode simplifiée."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        import base64
        
        print("🔧 Génération simple des clés VAPID...")
        
        # Générer une paire de clés ECDSA P-256
        private_key = ec.generate_private_key(ec.SECP256R1())
        
        # Sérialiser en format PEM (plus compatible)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Encoder en base64 URL-safe
        private_key_b64 = base64.urlsafe_b64encode(private_pem).decode('utf-8').rstrip('=')
        public_key_b64 = base64.urlsafe_b64encode(public_pem).decode('utf-8').rstrip('=')
        
        print("✅ Clés VAPID générées avec cryptography (format PEM)")
        return private_key_b64, public_key_b64
        
    except ImportError:
        print("⚠️ cryptography non installé")
        return generate_vapid_keys_fake()
    except Exception as e:
        print(f"⚠️ Erreur génération simple : {e}")
        return generate_vapid_keys_fake()

def generate_vapid_keys_fake():
    """Génère des clés VAPID fictives pour le développement."""
    import secrets
    import base64
    
    print("🔧 Génération de clés VAPID fictives (DÉVELOPPEMENT UNIQUEMENT)")
    print("⚠️ Ces clés ne fonctionneront pas pour les vraies notifications push")
    print("   Installez les bonnes versions : pip install 'cryptography>=3.0' 'py-vapid>=1.7'")
    
    # Générer des clés factices mais de la bonne longueur
    fake_private = f"FAKE_VAPID_PRIVATE_KEY_DEV_{secrets.token_hex(16)}"
    fake_public = f"FAKE_VAPID_PUBLIC_KEY_DEV_{secrets.token_hex(16)}"
    
    private_key_b64 = base64.urlsafe_b64encode(fake_private.encode()).decode('utf-8').rstrip('=')
    public_key_b64 = base64.urlsafe_b64encode(fake_public.encode()).decode('utf-8').rstrip('=')
    
    return private_key_b64, public_key_b64

def get_user_input():
    """Demande les paramètres à l'utilisateur."""
    print("📝 Configuration des paramètres")
    print("-" * 30)
    
    config = {}
    
    # Mode de déploiement
    print("\n⚙️  Mode de déploiement :")
    print("1. Développement local (SQLite)")
    print("2. Production Docker (PostgreSQL)")
    
    choice = input("Votre choix [1]: ").strip() or "1"
    
    if choice == "2":
        config['flask_env'] = "production"
        config['flask_debug'] = "False"
        config['use_sqlite'] = False
        
        # Configuration PostgreSQL pour production
        print(f"\n🗄️  Configuration PostgreSQL (Production Docker) :")
        config['db_host'] = "db"
        print(f"✓ Host PostgreSQL : db")
        config['db_port'] = input("Port PostgreSQL [5432]: ").strip() or "5432"
        config['db_name'] = input("Nom de la base [conference_flow]: ").strip() or "conference_flow"
        config['db_user'] = input("Utilisateur PostgreSQL [conference_user]: ").strip() or "conference_user"
        config['db_password'] = generate_secure_password(16)
        print(f"✓ Mot de passe PostgreSQL généré : {config['db_password']}")
    else:
        config['flask_env'] = "development" 
        config['flask_debug'] = "True"
        config['use_sqlite'] = True
        print("\n🗄️  Configuration SQLite (Développement) :")
        print("✓ Base de données : SQLite (./instance/conferenceflow.db)")
    
    # Admin
    print("\n👤 Compte administrateur :")
    config['admin_email'] = input("Email admin [alice.admin@example.com]: ").strip() or "alice.admin@example.com"
    config['admin_first_name'] = input("Prénom admin [Alice]: ").strip() or "Alice"
    config['admin_last_name'] = input("Nom admin [Administrator]: ").strip() or "Administrator"
    
    # Générer ou demander mot de passe
    generate_pwd = input("Générer un mot de passe sécurisé ? [Y/n]: ").strip().lower()
    if generate_pwd in ['', 'y', 'yes', 'o', 'oui']:
        config['admin_password'] = generate_secure_password()
        print(f"✓ Mot de passe généré : {config['admin_password']}")
    else:
        config['admin_password'] = input("Mot de passe admin : ").strip()
    
    # Email
    print("\n📧 Configuration email :")
    config['mail_server'] = input("Serveur SMTP [smtp.example.com]: ").strip() or "smtp.example.com"
    config['mail_port'] = input("Port SMTP [465]: ").strip() or "465"

    if config['mail_port'] == '465':
        config['use_ssl'] = 'True'
        config['use_tls'] = 'False'
    else:  # Port 587
        config['use_ssl'] = 'False' 
        config['use_tls'] = 'True'

    config['mail_username'] = input("Utilisateur SMTP [your_email@example.com]: ").strip() or "your_email@example.com"
    config['mail_password'] = input("Mot de passe SMTP [your_password]: ").strip() or "your_password"

    print("\n📚 Configuration HAL (Archives ouvertes) :")
    enable_hal = input("Activer l'export HAL ? [Y/n]: ").strip().lower()
    config['enable_hal'] = enable_hal in ['', 'y', 'yes', 'o', 'oui']
    
    if config['enable_hal']:
        print("📋 Identifiants HAL pour l'export automatique :")
        config['hal_username'] = input("Nom d'utilisateur HAL [votre_login_hal]: ").strip() or "votre_login_hal"
        config['hal_password'] = input("Mot de passe HAL [votre_password_hal]: ").strip() or "votre_password_hal"
        print("ℹ️  Ces identifiants seront utilisés pour l'export automatique vers HAL")
    else:
        config['hal_username'] = 'HAL_DISABLED'
        config['hal_password'] = 'HAL_DISABLED'
    
    # Base URL
    print("\n🌐 Configuration serveur :")
    default_url = "https://your-domain.com" if config['flask_env'] == 'production' else "http://localhost:5000"
    config['base_url'] = input(f"URL de base [{default_url}]: ").strip() or default_url
    
    # NOUVEAU : Configuration des notifications push
    print("\n📱 Configuration des notifications push :")
    enable_notifications = input("Activer les notifications push smartphone ? [Y/n]: ").strip().lower()
    config['enable_notifications'] = enable_notifications in ['', 'y', 'yes', 'o', 'oui']
    
    if config['enable_notifications']:
        print("📋 Génération des clés VAPID pour les notifications...")
        private_key, public_key = generate_vapid_keys()
        
        if private_key and public_key:
            config['vapid_private_key'] = private_key
            config['vapid_public_key'] = public_key
            config['vapid_subject'] = f"mailto:{config['admin_email']}"
            print("✅ Clés VAPID générées avec succès")
        else:
            config['vapid_private_key'] = 'VAPID_KEYS_NOT_GENERATED'
            config['vapid_public_key'] = 'VAPID_KEYS_NOT_GENERATED'
            config['vapid_subject'] = f"mailto:{config['admin_email']}"
            print("⚠️  Clés VAPID non générées - notifications désactivées")
    else:
        config['vapid_private_key'] = 'NOTIFICATIONS_DISABLED'
        config['vapid_public_key'] = 'NOTIFICATIONS_DISABLED'
        config['vapid_subject'] = f"mailto:{config['admin_email']}"
    
    return config
    
def create_env_file(config):
    """Crée le fichier .env avec la configuration."""
    import os
    # Générer une clé secrète
    secret_key = secrets.token_hex(32)
    
    # URL de base de données selon le mode
    if config.get('use_sqlite', True):
        import os
        project_root = os.getcwd()
        database_url = f"sqlite:///{project_root}/instance/conferenceflow.db"
        db_section = "# Base de données SQLite (développement)\n# Pas de configuration PostgreSQL nécessaire"
    else:
        database_url = f"postgresql://{config['db_user']}:{config['db_password']}@{config['db_host']}:{config['db_port']}/{config['db_name']}"
        db_section = f"""# Configuration PostgreSQL (production)
DB_USER={config['db_user']}
DB_PASSWORD={config['db_password']}
DB_NAME={config['db_name']}
DB_HOST={config['db_host']}
DB_PORT={config['db_port']}"""

    env_content = f"""# Configuration Flask
SECRET_KEY={secret_key}
DATABASE_URL={database_url}
FLASK_ENV={config['flask_env']}
FLASK_DEBUG={config['flask_debug']}
BASE_URL={config['base_url']}

{db_section}

# Configuration Email SMTP (technique)
MAIL_USERNAME={config['mail_username']}
MAIL_PASSWORD={config['mail_password']}
MAIL_SERVER={config['mail_server']}
MAIL_PORT={config['mail_port']}
MAIL_USE_TLS={config['use_tls']}
MAIL_USE_SSL={config['use_ssl']}

# Limites de fichiers
MAX_CONTENT_LENGTH=52428800

# Configuration Admin
ADMIN_EMAIL={config['admin_email']}
ADMIN_FIRST_NAME={config['admin_first_name']}
ADMIN_LAST_NAME={config['admin_last_name']}
ADMIN_PASSWORD={config['admin_password']}

# Configuration de sécurité
SESSION_TIMEOUT_MINUTES=120
PASSWORD_MIN_LENGTH=8
MAX_LOGIN_ATTEMPTS=5

# Configuration HAL (Archives ouvertes)
HAL_API_URL=https://api.archives-ouvertes.fr
HAL_TEST_MODE={str(config['flask_env'] != 'production').lower()}
HAL_USERNAME={config['hal_username']}
HAL_PASSWORD={config['hal_password']}
    
# NOUVEAU : Configuration notifications push
VAPID_PRIVATE_KEY={config['vapid_private_key']}
VAPID_PUBLIC_KEY={config['vapid_public_key']}
VAPID_SUBJECT={config['vapid_subject']}
NOTIFICATION_SEND_REMINDERS={str(config.get('enable_notifications', True)).lower()}
NOTIFICATION_REMINDER_TIMES=15,3
NOTIFICATION_MAX_RETRIES=3

# ConferenceFlow
APP_NAME=ConferenceFlow
APP_VERSION=1.0.0

# Mode debug email
MAIL_DEBUG={config['flask_debug']}
MAIL_SUPPRESS_SEND=false
"""
        
    # Vérifier si .env existe déjà
    if os.path.exists('.env'):
        response = input("\n⚠️  Le fichier .env existe déjà. Remplacer ? [y/N]: ")
        if response.lower() not in ['y', 'yes', 'o', 'oui']:
            print("❌ Configuration annulée")
            return False
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    return True

def main():
    """Fonction principale."""
    print_header()
    
    # Demander la configuration
    config = get_user_input()
    
    # Créer le fichier .env
    print("\n📄 Création du fichier .env...")
    if not create_env_file(config):
        sys.exit(1)
    
    print("✓ Fichier .env créé avec succès")
    
    print("\n🎉 Configuration terminée !")
    
    if config.get('use_sqlite', True):
        print("\n📋 Prochaines étapes (développement) :")
        print("1. Vérifiez le fichier .env créé")
        print("2. pip install -r requirements.txt")
        
        # NOUVEAU : Info notifications
        if config.get('enable_notifications'):
            print("3. pip install pywebpush  # Pour les notifications push")
            print("4. python run.py")
        else:
            print("3. python run.py")
            
        print("4. Accédez à http://localhost:5000")
    else:
        print("\n📋 Prochaines étapes (production) :")
        print("1. Vérifiez le fichier .env créé")
        print("2. docker-compose up --build")
        
    print(f"\n👤 Compte admin configuré : {config['admin_email']}")
    if 'admin_password' in config:
        print(f"🔑 Mot de passe : {config['admin_password']}")

    # Info HAL
    if config.get('enable_hal'):
        print("📚 Export HAL activé")
        if config.get('hal_username') != 'votre_login_hal':
            print(f"   Utilisateur HAL : {config['hal_username']}")
        else:
            print("⚠️  Pensez à configurer vos vrais identifiants HAL dans le .env")
    else:
        print("📚 Export HAL désactivé")
        
    # NOUVEAU : Info notifications
    if config.get('enable_notifications'):
        print("📱 Notifications push activées")
        if config.get('vapid_private_key') != 'VAPID_KEYS_NOT_GENERATED':
            print("✅ Clés VAPID générées et configurées")
        else:
            print("⚠️  Clés VAPID à régénérer manuellement")
    else:
        print("📱 Notifications push désactivées")


if __name__ == "__main__":
    main()
