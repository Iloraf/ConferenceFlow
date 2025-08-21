#!/usr/bin/env python3
"""Script de configuration locale pour ConferenceFlow."""

import os
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
    
    # Mode AVANT la base de données pour déterminer l'hostname
    print("\n⚙️  Mode de déploiement :")
    is_production = input("Mode production ? [y/N]: ").strip().lower()
    config['flask_env'] = "production" if is_production in ['y', 'yes', 'o', 'oui'] else "development"
    config['flask_debug'] = "False" if is_production in ['y', 'yes', 'o', 'oui'] else "True"
    
    # Déterminer l'hostname automatiquement
    if config['flask_env'] == 'production':
        default_host = "db"  # Docker Compose en production
        host_explanation = "Production (Docker Compose)"
    else:
        default_host = "localhost"  # Développement local
        host_explanation = "Développement (PostgreSQL local)"
    
    # Base de données - Configuration automatique
    print(f"\n🗄️  Configuration PostgreSQL ({host_explanation}) :")
    config['db_host'] = default_host
    print(f"✓ Host PostgreSQL : {default_host}")
    config['db_port'] = input("Port PostgreSQL [5432]: ").strip() or "5432"
    
    # Adapter les noms par défaut selon l'environnement
    if config['flask_env'] == 'production':
        default_db_name = "conference_flow"
        default_db_user = "conference_user"
    else:
        default_db_name = "conferenceflow_dev"
        default_db_user = "postgres"
    
    config['db_name'] = input(f"Nom de la base [{default_db_name}]: ").strip() or default_db_name
    config['db_user'] = input(f"Utilisateur PostgreSQL [{default_db_user}]: ").strip() or default_db_user
    
    # Génération automatique du mot de passe PostgreSQL
    config['db_password'] = generate_secure_password(16)
    print(f"✓ Mot de passe PostgreSQL généré : {config['db_password']}")
    
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
    config['mail_username'] = input("Utilisateur SMTP [your_email@example.com]: ").strip() or "your_email@example.com"
    config['mail_password'] = input("Mot de passe SMTP [your_password]: ").strip() or "your_password"
    
    # Base URL
    print("\n🌐 Configuration serveur :")
    default_url = "https://your-domain.com" if config['flask_env'] == 'production' else "http://localhost:5000"
    config['base_url'] = input(f"URL de base [{default_url}]: ").strip() or default_url
    
    return config

def create_env_file(config):
    """Crée le fichier .env avec la configuration."""
    # Générer une clé secrète
    secret_key = secrets.token_hex(32)


    database_url = f"postgresql://{config['db_user']}:{config['db_password']}@{config['db_host']}:{config['db_port']}/{config['db_name']}"
    
    
    env_content = f"""# Configuration Flask
SECRET_KEY={secret_key}
DATABASE_URL={database_url}
FLASK_ENV={config['flask_env']}
FLASK_DEBUG={config['flask_debug']}
BASE_URL={config['base_url']}

# Configuration Email
MAIL_USERNAME={config['mail_username']}
MAIL_PASSWORD={config['mail_password']}
MAIL_SERVER={config['mail_server']}
MAIL_PORT={config['mail_port']}
MAIL_USE_TLS=True

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
    print("\n📋 Prochaines étapes :")
    print("1. Vérifiez le fichier .env créé")
    print("2. Pour développement local : pip install -r requirements.txt && python run.py")
    print("3. Pour Docker : docker-compose up --build")
    print(f"\n👤 Compte admin configuré : {config['admin_email']}")
    if 'admin_password' in config:
        print(f"🔑 Mot de passe : {config['admin_password']}")

if __name__ == "__main__":
    main()
