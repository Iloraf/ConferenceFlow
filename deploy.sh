#!/bin/bash

# Configuration
REPO_URL="https://gitlab.univ-lorraine.fr/votre-username/votre-projet.git"
APP_DIR="/opt/mon-app"
BRANCH="main"  # ou master selon votre branche principale

# Installation de Docker si nécessaire
if ! command -v docker &> /dev/null; then
    echo "Installation de Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "Redémarrez votre session ou relancez le script"
    exit 1
fi

# Installation de Docker Compose si nécessaire
if ! command -v docker-compose &> /dev/null; then
    echo "Installation de Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Installation de git si nécessaire
if ! command -v git &> /dev/null; then
    sudo apt update
    sudo apt install -y git
fi

# Clonage ou mise à jour du dépôt
if [ -d "$APP_DIR" ]; then
    echo "Mise à jour du code..."
    cd $APP_DIR
    git pull origin $BRANCH
else
    echo "Clonage du dépôt..."
    sudo git clone $REPO_URL $APP_DIR
    sudo chown -R $USER:$USER $APP_DIR
    cd $APP_DIR
fi

# Arrêt de l'ancienne version
docker-compose down 2>/dev/null || true

# Déploiement
echo "Déploiement de l'application..."
docker-compose up --build -d

echo "✅ Application déployée !"
echo "URL: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "Commandes utiles:"
echo "  Logs: docker-compose logs -f"
echo "  Redémarrer: docker-compose restart"
echo "  Arrêter: docker-compose down"
