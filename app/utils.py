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

import secrets
import string

def generate_secure_password(length=12):
    """
    Génère un mot de passe sécurisé.
    
    Args:
        length (int): Longueur du mot de passe (défaut: 12)
    
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
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)




def send_activation_email_to_user(user, token):
    """Envoie l'email d'activation à un reviewer."""
    from flask import url_for, current_app
    
    # Générer l'URL d'activation
    activation_url = url_for('main.activate_account', token=token, _external=True)
    
    subject = "Activation de votre compte reviewer - SFT 2026"
    
    # Corps de l'email en texte
    body = f"""
Bonjour {user.full_name or user.email},

Votre compte reviewer a été créé pour la conférence SFT 2026.

Pour activer votre compte et définir votre mot de passe, cliquez sur le lien suivant :
{activation_url}

Ce lien est valable 7 jours.

Vos informations :
- Email : {user.email}
- Spécialités : {user.specialites_codes or 'Aucune'}
- Affiliations : {', '.join([aff.sigle for aff in user.affiliations]) if user.affiliations else 'Aucune'}

Cordialement,
L'équipe SFT 2026
"""
   # Corps de l'email en HTML
    html = f"""
<h2>Activation de votre compte reviewer - SFT 2026</h2>

<p>Bonjour <strong>{user.full_name or user.email}</strong>,</p>

<p>Votre compte reviewer a été créé pour la conférence SFT 2026.</p>

<p>
    <a href="{activation_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
        Activer mon compte
    </a>
</p>

<p><em>Ce lien est valable 7 jours.</em></p>

<h3>Vos informations :</h3>
<ul>
    <li><strong>Email :</strong> {user.email}</li>
    <li><strong>Spécialités :</strong> {user.specialites_codes or 'Aucune'}</li>
    <li><strong>Affiliations :</strong> {', '.join([aff.sigle for aff in user.affiliations]) if user.affiliations else 'Aucune'}</li>
</ul>

<p>Cordialement,<br>L'équipe SFT 2026</p>
"""

    # Utiliser votre fonction existante
    send_email(subject, [user.email], body, html)
