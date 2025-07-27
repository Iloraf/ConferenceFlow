#!/usr/bin/env python3
"""Script d'installation automatique pour SFT 2026."""

import os
import sys
import subprocess
import secrets
from pathlib import Path

def print_step(step, message):
    print(f"\n{'='*50}")
    print(f"ÉTAPE {step}: {message}")
    print('='*50)

def create_directories():
    """Crée la structure des dossiers."""
    directories = [
        'app/static/uploads/articles',
        'app/static/uploads/wip', 
        'app/static/uploads/reviews', 
        'app/static/uploads/qr_codes',
        'app/static/icons',
        'instance',
        'logs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ {directory}")

def create_env_file():
    """Crée le fichier .env."""
    secret_key = secrets.token_hex(32)
    
    env_content = f"""SECRET_KEY={secret_key}
DATABASE_URL=sqlite:///sft_2026.db
FLASK_ENV=development
FLASK_DEBUG=True
MAIL_USERNAME=your_email@univ-lorraine.fr
MAIL_PASSWORD=your_password
MAIL_SERVER=smtp.univ-lorraine.fr
MAIL_PORT=465
MAIL_USE_TLS=True
MAX_CONTENT_LENGTH=10485760
BASE_URL=http://localhost:5000
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✓ Fichier .env créé")
    print("⚠️  Configurez les paramètres email")

def install_dependencies():
    """Installe les dépendances."""
    try:
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
        ], check=True)
        print("✓ Dépendances installées")
        return True
    except subprocess.CalledProcessError:
        print("❌ Erreur installation")
        return False

def init_database():
    """Initialise la base de données."""
    try:
        env = os.environ.copy()
        env['FLASK_APP'] = 'run.py'
        
        subprocess.run([sys.executable, '-m', 'flask', 'db', 'init'], 
                      env=env, check=True)
        subprocess.run([sys.executable, '-m', 'flask', 'db', 'migrate', '-m', 'Initial'], 
                      env=env, check=True)
        subprocess.run([sys.executable, '-m', 'flask', 'db', 'upgrade'], 
                      env=env, check=True)
        
        print("✓ Base de données initialisée")
        return True
    except subprocess.CalledProcessError:
        print("❌ Erreur base de données")
        return False

def create_admin():
    """Crée un utilisateur admin."""
    script = """
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    admin = User.query.filter_by(email='olivier.farges@univ-lorraine.fr').first()
    if not admin:
        admin = User(
            email='olivier.farges@univ-lorraine.fr',
            first_name='Olivier',
            last_name='Farges',
            is_admin=True
        )
        admin.set_password('Kknm6810!')
        db.session.add(admin)
        db.session.commit()
        print('✓ Admin créé')
    else:
        print('ℹ️ Admin existe déjà')
"""
    
    try:
        exec(script)
    except Exception as e:
        print(f"❌ Erreur admin: {e}")

def import_affiliations():
    """Importe les affiliations depuis le fichier CSV."""
    script = """
from app import create_app, db
from app.models import Affiliation
import csv
import os
from datetime import datetime

app = create_app()
csv_path = 'static/uploads/data/labos.csv'

with app.app_context():
    if not os.path.exists(csv_path):
        print(f'❌ Fichier {csv_path} non trouvé')
        return
    
    created_count = 0
    updated_count = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file, delimiter=';')
            
            for line_num, row in enumerate(csv_reader, 2):
                sigle = row.get('sigle', '').strip().upper()
                nom_complet = row.get('nom_complet', '').strip()
                adresse = row.get('adresse', '').strip()
                citation = row.get('citation', '').strip()
                identifiant_hal = row.get('identifiant_hal', '').strip()
                
                if not sigle or not nom_complet:
                    continue
                
                existing = Affiliation.query.filter_by(sigle=sigle).first()
                
                if existing:
                    # Mettre à jour seulement si différent
                    updated = False
                    if existing.nom_complet != nom_complet:
                        existing.nom_complet = nom_complet
                        updated = True
                    if existing.adresse != (adresse or None):
                        existing.adresse = adresse or None
                        updated = True
                    if existing.citation != (citation or None):
                        existing.citation = citation or None
                        updated = True
                    if existing.identifiant_hal != (identifiant_hal or None):
                        existing.identifiant_hal = identifiant_hal or None
                        updated = True
                    
                    if updated:
                        existing.updated_at = datetime.utcnow()
                        updated_count += 1
                else:
                    affiliation = Affiliation(
                        sigle=sigle,
                        nom_complet=nom_complet,
                        adresse=adresse or None,
                        citation=citation or None,
                        identifiant_hal=identifiant_hal or None,
                        is_active=True
                    )
                    db.session.add(affiliation)
                    created_count += 1
        
        db.session.commit()
        print(f'✅ Affiliations: {created_count} créées, {updated_count} mises à jour')
        
    except Exception as e:
        db.session.rollback()
        print(f'❌ Erreur import affiliations: {e}')
"""
    
    try:
        exec(script)
    except Exception as e:
        print(f"❌ Erreur import affiliations: {e}")


        
def main():
    print("🚀 Installation SFT 2026")
    
    print_step(1, "Création des dossiers")
    create_directories()
    
    print_step(2, "Configuration")
    #create_env_file()
    
    print_step(3, "Installation des dépendances")
    if not install_dependencies():
        sys.exit(1)
    
    print_step(4, "Base de données")
    if not init_database():
        sys.exit(1)

        
    print_step(5, "Utilisateur admin")
    create_admin()

    
#    print_step(6, "Import des affiliations") 
#    import_affiliations()                     

    
    print("\n🎉 Installation terminée !")
    print("\n📋 Prochaines étapes :")
    print("1. Configurez .env (email)")
    print("2. Lancez: python run.py")
    print("3. Accédez: http://localhost:5000")
    print("4. Admin créé")

if __name__ == "__main__":
    main()
