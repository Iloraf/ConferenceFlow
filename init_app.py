#!/usr/bin/env python3
"""Script d'initialisation de l'application pour Docker."""

import os
import sys
import subprocess
from pathlib import Path

def print_step(step, message):
    print(f"[INIT] ÉTAPE {step}: {message}")

def install_dependencies():
    """Installe les dépendances Python."""
    print("📦 Installation des dépendances...")
    try:
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '--no-cache-dir', '-r', 'requirements.txt'
        ], check=True)
        print("✓ Dépendances installées")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'installation des dépendances: {e}")
        return False
    except FileNotFoundError:
        print("❌ Fichier requirements.txt non trouvé")
        return False

def print_step(step, message):
    print(f"[INIT] ÉTAPE {step}: {message}")

def create_directories():
    """Crée la structure des dossiers nécessaires."""
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
    
    print("✓ Dossiers créés")

def validate_environment():
    """Valide la présence des variables d'environnement essentielles."""
    required_vars = [
        'SECRET_KEY',
        'DATABASE_URL', 
        'ADMIN_EMAIL',
        'ADMIN_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Variables d'environnement manquantes: {', '.join(missing_vars)}")
        return False
    
    print("✓ Variables d'environnement validées")
    return True

def init_database():
    """Initialise la base de données."""
    try:
        from app import create_app, db
        
        app = create_app()
        with app.app_context():
            # Vérifier si la base existe déjà
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if existing_tables:
                print(f"ℹ️  Base de données déjà initialisée ({len(existing_tables)} tables)")
            else:
                # Créer toutes les tables
                db.create_all()
                print("✓ Tables de base de données créées")
            
            # Appliquer les migrations si elles existent
            import os
            if os.path.exists('migrations'):
                try:
                    from flask_migrate import upgrade
                    upgrade()
                    print("✓ Migrations appliquées")
                except Exception as e:
                    print(f"ℹ️  Erreur migrations: {e}")
            else:
                print("ℹ️  Pas de dossier migrations - tables créées directement")
        
        print("✓ Base de données prête")
        return True
        
    except Exception as e:
        print(f"❌ Erreur initialisation base de données: {e}")
        return False

def create_admin():
    """Crée l'utilisateur administrateur."""
    try:
        from app import create_app, db
        from app.models import User
        
        admin_email = os.getenv('ADMIN_EMAIL')
        admin_first_name = os.getenv('ADMIN_FIRST_NAME', 'Admin')
        admin_last_name = os.getenv('ADMIN_LAST_NAME', 'User')
        admin_password = os.getenv('ADMIN_PASSWORD')
        
        app = create_app()
        with app.app_context():
            # Vérifier si l'admin existe déjà
            existing_admin = User.query.filter_by(email=admin_email).first()
            
            if existing_admin:
                print(f"ℹ️  Admin existe déjà: {admin_email}")
                return True
            
            # Créer l'admin
            admin = User(
                email=admin_email,
                first_name=admin_first_name,
                last_name=admin_last_name,
                is_admin=True
            )
            admin.set_password(admin_password)
            
            db.session.add(admin)
            db.session.commit()
            
            print(f"✓ Admin créé: {admin_email}")
            return True
            
    except Exception as e:
        print(f"❌ Erreur création admin: {e}")
        return False

def import_default_data():
    """Importe les données par défaut si disponibles."""
    try:
        # Pour l'instant, pas d'import automatique
        # Les affiliations peuvent être importées plus tard via l'interface admin
        print("ℹ️  Aucune donnée par défaut à importer")
        return True
        
    except Exception as e:
        print(f"⚠️  Erreur import données par défaut: {e}")
        return True  # Ne pas faire échouer l'init pour ça

def main():
    """Fonction principale d'initialisation."""
    print("[INIT] 🚀 Initialisation de ConferenceFlow")
    print("[INIT] " + "=" * 50)
    
    # Étape 1: Installation des dépendances
    print_step(1, "Installation des dépendances")
    if not install_dependencies():
        sys.exit(1)
    
    # Étape 2: Validation de l'environnement
    print_step(2, "Validation de l'environnement")
    if not validate_environment():
        sys.exit(1)
    
    # Étape 3: Création des dossiers
    print_step(3, "Création des dossiers")
    create_directories()
    
    # Étape 4: Initialisation base de données
    print_step(4, "Initialisation de la base de données")
    if not init_database():
        sys.exit(1)
    
    # Étape 5: Création de l'admin
    print_step(5, "Création de l'utilisateur admin")
    if not create_admin():
        sys.exit(1)
    
    # Étape 6: Import des données par défaut
    print_step(6, "Import des données par défaut")
    import_default_data()
    
    print("[INIT] ✅ Initialisation terminée avec succès")
    print(f"[INIT] 👤 Admin: {os.getenv('ADMIN_EMAIL')}")

if __name__ == "__main__":
    main()
