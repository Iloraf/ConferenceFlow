# ConferenceFlow

## 📋 Description

ConferenceFlow est un système de gestion complet pour congrès scientifiques. Cette application web permet la gestion intégrale d'une conférence académique, de la soumission des communications au processus de relecture, en passant par les inscriptions et la génération automatique de supports de communication.

## 🎯 Objectifs

ConferenceFlow vise à simplifier l'organisation de congrès scientifiques en automatisant les processus répétitifs et en offrant une interface intuitive pour tous les acteurs : auteurs, reviewers, et organisateurs.

## ✨ Fonctionnalités principales

### 👥 Gestion des utilisateurs
- Inscription et authentification sécurisée
- Profils utilisateurs avec affiliations multiples
- Système de rôles : utilisateur, reviewer, administrateur
- Gestion des spécialités thématiques pour les reviewers
- Import/export d'utilisateurs en masse

### 📄 Soumissions de communications
- **Articles complets** : travaux aboutis avec résultats finalisés
- **Work in Progress** : travaux en cours avec résultats préliminaires  
- **Posters** : présentation visuelle avec génération de QR codes
- Workflow de soumission multi-étapes personnalisable
- Gestion des versions de fichiers avec historique
- Support multi-auteurs avec notifications automatiques
- Thématiques configurables selon le domaine scientifique

### 🔍 Système de relecture (Peer Review)
- Assignation automatique de reviewers basée sur les spécialités
- Détection intelligente de conflits d'intérêts (affiliation, co-auteurs)
- Interface reviewer avec dashboard personnalisé
- Possibilité de refuser une assignation avec justification
- Notifications groupées pour éviter le spam d'emails
- Suivi des échéances et alertes de retard
- Système de scoring et recommandations standardisé

### 👨‍💼 Administration
- Dashboard admin avec statistiques en temps réel
- Gestion centralisée des utilisateurs et affiliations
- Import/export CSV pour données en masse
- Assignation manuelle et automatique de reviewers
- Gestion fine des notifications par email
- Suivi complet du processus de relecture
- Génération de rapports détaillés

### 📧 Communications automatiques
- Templates d'emails personnalisables
- Notifications automatiques pour toutes les étapes
- Rappels programmables aux reviewers
- Emails groupés pour les assignations multiples
- Notifications de refus avec workflow de réassignation

### 🌐 Interface web moderne
- Design responsive (mobile/tablette/desktop)
- Interface intuitive pour tous types d'utilisateurs
- Dashboard personnalisé selon le rôle
- Gestion des fichiers avec upload sécurisé
- Génération automatique de QR codes pour posters

## 🏛️ Exemple d'utilisation

ConferenceFlow a été développé initialement pour le **34ème Congrès Français de Thermique (SFT 2026)** :
- **Thème :** "Thermique & Décarbonation de l'industrie"
- **Dates :** 2-5 juin 2026  
- **Lieu :** Domaine de l'Asnée, Villers-lès-Nancy
- **15 thématiques scientifiques** spécialisées en thermique
- **200+ communications attendues**

## 🛠️ Technologies

- **Backend :** Python Flask
- **Base de données :** SQLAlchemy (SQLite/PostgreSQL)
- **Frontend :** Bootstrap 5, HTML5, CSS3, JavaScript
- **Email :** Flask-Mail avec templates HTML
- **Authentification :** Flask-Login
- **Gestion fichiers :** Upload sécurisé avec validation
- **QR Codes :** Génération automatique
- **PDF :** WeasyPrint pour l'export

## 📋 Prérequis

- Python 3.8+
- Docker & Docker Compose
- Serveur SMTP pour les emails

## 🚀 Installation avec Docker

### 1. Cloner le projet
```bash
git clone https://github.com/your-username/conferenceflow.git
cd conferenceflow
```

### 2. Configuration
Créer un fichier `.env` à la racine :
```bash
cp .env.example .env
```

Modifier les variables dans `.env` :
```env
# Base de données
DATABASE_URL=sqlite:///conference.db

# Email configuration
MAIL_SERVER=smtp.your-university.fr
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@university.fr
MAIL_PASSWORD=your-password

# Sécurité
SECRET_KEY=your-very-secret-key-here
FLASK_ENV=production

# Configuration du congrès
CONFERENCE_NAME="Votre Congrès 2024"
CONFERENCE_THEME="Votre thématique"
CONFERENCE_DATES="1-4 juin 2024"
CONFERENCE_LOCATION="Votre ville"
```

### 3. Lancement avec Docker
```bash
# Construction et démarrage
docker-compose up -d --build

# Vérifier que les services sont démarrés
docker-compose ps
```

### 4. Initialisation de la base de données
```bash
# Créer les tables
docker-compose exec web flask db upgrade

# Créer un administrateur
docker-compose exec web flask create-admin
```

### 5. Accès à l'application
- **Interface web :** http://localhost:5000
- **Admin :** Utiliser les identifiants créés à l'étape 4

## 📖 Utilisation

### Premier démarrage
1. **Connexion admin :** Utilisez le compte administrateur créé
2. **Configuration :** Ajustez les thématiques dans l'interface admin
3. **Import utilisateurs :** Importez vos reviewers via CSV (optionnel)
4. **Test :** Créez quelques utilisateurs test pour valider le workflow

### Workflow type
1. **Phase de soumission :** 
   - Les auteurs s'inscrivent et soumettent leurs communications
   - Validation automatique des formats de fichiers
   
2. **Phase de relecture :**
   - Assignment automatique ou manuelle des reviewers
   - Envoi groupé des notifications
   - Les reviewers effectuent leurs évaluations
   
3. **Phase de décision :**
   - L'admin consulte les évaluations
   - Notifications d'acceptation/refus aux auteurs
   
4. **Phase finale :**
   - Soumission des versions finales
   - Génération des QR codes pour posters

### Personnalisation
- **Thématiques :** Modifiables dans `models.py` (variable `DEFAULT_THEMATIQUES`)
- **Templates emails :** Dans le dossier `templates/emails/`
- **Interface :** CSS personnalisable dans `static/css/`

## 🔧 Administration

### Commandes utiles
```bash
# Voir les logs
docker-compose logs -f web

# Backup de la base de données
docker-compose exec web flask backup-db

# Reset complet (ATTENTION : efface toutes les données)
docker-compose down -v
docker-compose up -d --build
```

### Gestion des utilisateurs
- **Interface web :** Section "Gestion des utilisateurs" dans l'admin
- **Import CSV :** Formats fournis dans la documentation
- **Rôles :** Attribution automatique ou manuelle des droits

### Monitoring
- **Dashboard admin :** Statistiques en temps réel
- **Logs système :** `docker-compose logs`
- **Base de données :** Interface d'administration intégrée

## 🤝 Adaptation à votre congrès

ConferenceFlow est conçu pour être adaptable. Points à personnaliser :

### Configuration minimale
1. **Variables d'environnement** (`.env`)
2. **Thématiques scientifiques** (`models.py`)
3. **Templates d'emails** (`templates/emails/`)
4. **Logo et charte graphique** (`static/`)

### Configuration avancée
1. **Workflow de soumission** (modifier les statuts dans `models.py`)
2. **Critères de review** (formulaires dans `forms.py`)
3. **Types de communications** (ajouter de nouveaux types)
4. **Intégrations externes** (HAL, ORCID, etc.)

## 📝 Licence

Ce projet est sous licence **GNU General Public License v3.0**.

Vous êtes libre de :
- Utiliser le logiciel à des fins commerciales
- Modifier le code source
- Distribuer le logiciel
- Placer une garantie sur le logiciel

Sous les conditions suivantes :
- Divulguer le code source
- Conserver la licence et les notices de copyright
- Indiquer les modifications apportées
- Utiliser la même licence pour les œuvres dérivées

Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 👨‍💻 Auteur

**Olivier Farges**  
📧 olivier.farges@univ-lorraine.fr  
🏫 Université de Lorraine  
🔬 Laboratoire LEMTA - Laboratoire d'Énergétique et de Mécanique Théorique et Appliquée

## 🤝 Contributions

Les contributions sont les bienvenues ! Merci de :

1. **Fork** le projet
2. **Créer** une branche pour votre fonctionnalité (`git checkout -b feature/nouvelle-fonctionnalite`)
3. **Commiter** vos changements (`git commit -am 'Ajout nouvelle fonctionnalité'`)
4. **Pousser** vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. **Ouvrir** une Pull Request

### Standards de contribution
- Code documenté et commenté
- Tests pour les nouvelles fonctionnalités
- Respect des conventions Python (PEP 8)
- Messages de commit descriptifs

## 🐛 Signaler un bug

Pour signaler un bug, veuillez ouvrir une issue en incluant :
- Description détaillée du problème
- Étapes pour reproduire
- Environnement (OS, version Docker, etc.)
- Logs d'erreur si applicable

## 📚 Documentation

- **Documentation utilisateur :** [docs/user-guide.md](docs/user-guide.md)
- **Documentation développeur :** [docs/developer-guide.md](docs/developer-guide.md)
- **API Documentation :** [docs/api.md](docs/api.md)
- **FAQ :** [docs/faq.md](docs/faq.md)

## 🗺️ Roadmap

### Version 2.0 (à venir)
- [ ] Interface multi-langues (i18n)
- [ ] API REST complète
- [ ] Intégration ORCID automatique
- [ ] Export automatique vers HAL
- [ ] App mobile companion

### Version 2.1
- [ ] Système de sessions parallèles
- [ ] Planificateur automatique de présentations
- [ ] Streaming intégré
- [ ] Analytics avancés

## 🙏 Remerciements

- **Société Française de Thermique (SFT)** pour le soutien au développement
- **Université de Lorraine** pour l'hébergement et les ressources
- **Laboratoire LEMTA** pour le cadre de développement
- La communauté **Flask** pour l'excellente documentation

---

**ConferenceFlow** - Simplifiez l'organisation de vos congrès scientifiques 🚀