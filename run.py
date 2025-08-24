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

