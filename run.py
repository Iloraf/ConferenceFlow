#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

from app import create_app

if __name__ == '__main__':
    app = create_app()
    
    # Création automatique de l'admin en développement seulement
    if os.getenv('FLASK_ENV') == 'development':
        with app.app_context():
            from app import db
            from app.models import User
            
            admin_email = os.getenv('ADMIN_EMAIL')
            if admin_email and not User.query.filter_by(email=admin_email).first():
                admin = User(
                    email=admin_email,
                    first_name=os.getenv('ADMIN_FIRST_NAME', 'Admin'),
                    last_name=os.getenv('ADMIN_LAST_NAME', 'User'),
                    is_admin=True
                )
                admin.set_password(os.getenv('ADMIN_PASSWORD'))
                db.session.add(admin)
                db.session.commit()
                print(f"Admin créé automatiquement : {admin_email}")
    
    # Port depuis la variable d'environnement ou 5000 par défaut
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )

