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
        use_ssl = 'True'
        use_tls = 'False'
    else:  # Port 587
        use_ssl = 'False' 
        use_tls = 'True'
    
    config['mail_username'] = input("Utilisateur SMTP [your_email@example.com]: ").strip() or "your_email@example.com"
    config['mail_password'] = input("Mot de passe SMTP [your_password]: ").strip() or "your_password"
    
    # Base URL
    print("\n🌐 Configuration serveur :")
    default_url = "https://your-domain.com" if config['flask_env'] == 'production' else "http://localhost:5000"
    config['base_url'] = input(f"URL de base [{default_url}]: ").strip() or default_url
    
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
MAIL_USE_TLS={use_tls}
MAIL_USE_SSL={use_ssl}

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

# Configuration HAL
HAL_API_URL=https://api.archives-ouvertes.fr
HAL_TEST_MODE=true

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
        print("3. python run.py")
        print("4. Accédez à http://localhost:5000")
    else:
        print("\n📋 Prochaines étapes (production) :")
        print("1. Vérifiez le fichier .env créé")
        print("2. docker-compose up --build")
        
    print(f"\n👤 Compte admin configuré : {config['admin_email']}")
    if 'admin_password' in config:
        print(f"🔑 Mot de passe : {config['admin_password']}")

if __name__ == "__main__":
    main()

