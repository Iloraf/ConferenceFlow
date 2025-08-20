# Installation ConferenceFlow

## Prérequis

- Docker et Docker Compose
- Git
- Python 3.8+ (pour le script de configuration)

## Installation

### 1. Récupérer le code

```bash
git clone <repo-url>
cd conferenceflow
```

### 2. Configuration

```bash
python configure.py
```

Le script demande :
- Compte admin (email, nom, prénom)
- Configuration email (serveur SMTP, port, identifiants)
- URL de base de l'application
- Mode développement ou production

Un fichier `.env` est généré avec la configuration.

### 3. Démarrage

```bash
docker-compose up --build
```

L'application démarre automatiquement sur http://localhost:5000

Le script d'initialisation :
- Installe les dépendances
- Crée la base PostgreSQL
- Initialise les tables
- Crée le compte administrateur

### 4. Première connexion

- URL : http://localhost:5000
- Compte admin : celui configuré à l'étape 2
- Mot de passe : affiché lors de la configuration

## Configuration post-installation

1. Se connecter en admin
2. Aller dans Admin > Gestion du contenu
3. Uploader les fichiers de configuration si nécessaire

## Commandes utiles

```bash
# Voir les logs
docker-compose logs -f

# Redémarrer
docker-compose restart

# Arrêter
docker-compose down

# Reset complet (supprime la base)
docker-compose down -v
```

## Notes

- Les données sont persistées dans un volume Docker
- La configuration email peut être modifiée dans le fichier `.env`