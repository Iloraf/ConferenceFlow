# ConferenceFlow

Application web de gestion de conférences scientifiques développée avec Flask et PostgreSQL.

## Fonctionnalités

- Gestion des soumissions (résumés, articles, work-in-progress)
- Système de review par les pairs
- Interface d'administration complète
- Génération automatique de codes QR pour les posters
- Export des données vers HAL (archives ouvertes)
- Gestion des affiliations et des co-auteurs
- Interface responsive et moderne

## Architecture

- **Backend** : Flask 2.3+, SQLAlchemy, Flask-Migrate
- **Frontend** : Bootstrap 5, JavaScript ES6
- **Base de données** : PostgreSQL
- **Déploiement** : Docker, Docker Compose

## Installation

Voir le fichier [INSTALL.md](INSTALL.md) pour les instructions d'installation.

## Configuration

L'application se configure via un fichier `.env` généré par le script `configure.py`.

### Variables principales

```
SECRET_KEY=              # Clé secrète Flask
DATABASE_URL=           # URL PostgreSQL
ADMIN_EMAIL=            # Email du compte admin
ADMIN_PASSWORD=         # Mot de passe admin
MAIL_SERVER=            # Serveur SMTP
MAIL_USERNAME=          # Utilisateur email
MAIL_PASSWORD=          # Mot de passe email
```

### Configuration avancée

La configuration détaillée de la conférence se fait via le fichier `app/static/content/conference.yml` qui contient :

- Informations générales (nom, dates, lieu)
- Configuration des contacts
- Paramètres d'inscription
- Configuration HAL
- Thématiques de recherche

## Structure du projet

```
app/
├── models.py              # Modèles de données
├── routes.py              # Routes principales
├── admin.py               # Interface d'administration
├── auth.py                # Authentification
├── config_loader.py       # Chargement de la configuration
├── static/
│   ├── content/           # Fichiers de configuration
│   ├── uploads/           # Fichiers uploadés
│   └── css/               # Styles CSS
└── templates/             # Templates Jinja2
```

## API et intégrations

- **HAL** : Export automatique vers les archives ouvertes
- **Email** : Notifications automatiques via SMTP
- **QR Codes** : Génération pour les posters
- **PDF** : Export du programme

## Développement

```bash
# Mode développement local
pip install -r requirements.txt
python run.py

# Tests
python -m pytest

# Migrations
flask db migrate -m "Description"
flask db upgrade
```

## Déploiement

L'application est conçue pour être déployée avec Docker :

```bash
docker-compose up --build
```

Les données sont persistées dans des volumes Docker.

## Sécurité

- Sessions sécurisées avec clés aléatoires
- Validation des fichiers uploadés
- Protection CSRF
- Hashage des mots de passe avec bcrypt
- Variables d'environnement pour les secrets

## License

Projet open source développé pour la gestion de conférences scientifiques.



