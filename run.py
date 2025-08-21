#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

from app import create_app

if __name__ == '__main__':
    app = create_app()
    
    # Port depuis la variable d'environnement ou 5000 par défaut
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
