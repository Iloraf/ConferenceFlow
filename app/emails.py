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

from flask_mail import Message
from app import mail

def send_email(subject, recipients, body, html=None):
    msg = Message(subject=subject, recipients=recipients, body=body, html=html)
    mail.send(msg)

# À ajouter dans app/emails.py

def get_specialites_names(specialites_codes):
    """Convertit les codes de spécialités en noms complets."""
    if not specialites_codes:
        return 'Non spécifiées'
    
    try:
        from flask import current_app
        from app.config_loader import ThematiqueLoader
        
        # Récupérer toutes les thématiques
        themes = ThematiqueLoader.load_themes()
        
        # Créer un dictionnaire code -> nom
        themes_dict = {theme['code']: theme['nom'] for theme in themes}
        
        # Séparer les codes et les convertir
        codes = [code.strip().upper() for code in specialites_codes.split(',')]
        noms = []
        
        for code in codes:
            if code in themes_dict:
                noms.append(themes_dict[code])
            else:
                noms.append(code)  # Garder le code si pas trouvé
        
        return ' - '.join(noms)
        
    except Exception as e:
        # En cas d'erreur, retourner les codes originaux
        return specialites_codes or 'Non spécifiées'


# Modifier la fonction send_activation_email_to_user

def send_activation_email_to_user(user, token):
    """Envoie l'email d'activation à un reviewer."""
    from flask import url_for, current_app
    
    # Récupérer le config loader
    config_loader = current_app.config_loader
    
    # Convertir les spécialités en noms complets
    specialites_noms = get_specialites_names(user.specialites_codes)
    
    # Préparer le contexte pour le template
    context = {
        'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
        'USER_EMAIL': user.email,
        'USER_ROLE': 'Reviewer',
        'REVIEWER_SPECIALTIES': specialites_noms,  # Utiliser les noms au lieu des codes
        'REVIEWER_AFFILIATIONS': ', '.join([aff.sigle for aff in user.affiliations]) if user.affiliations else 'Aucune',
        'call_to_action_url': url_for('main.activate_account', token=token, _external=True)
    }
    
    # Récupérer le sujet depuis la configuration
    subject = config_loader.get_email_subject('activation', **context)
    
    # Récupérer le contenu depuis la configuration
    content_config = config_loader.get_email_content('activation', **context)
    
    # Récupérer la signature
    signature = config_loader.get_email_signature('default', **context)
    
    # Construire le corps de l'email en texte
    body_parts = []
    if content_config.get('greeting'):
        body_parts.append(content_config['greeting'])
    if content_config.get('intro'):
        body_parts.append(f"\n\n{content_config['intro']}")
    if content_config.get('body'):
        body_parts.append(f"\n\n{content_config['body']}")
    
    # Ajouter les informations spécifiques au reviewer
    body_parts.append(f"\n\nVos informations :")
    body_parts.append(f"- Email : {context['USER_EMAIL']}")
    body_parts.append(f"- Spécialités : {context['REVIEWER_SPECIALTIES']}")  # Noms complets
    body_parts.append(f"- Affiliations : {context['REVIEWER_AFFILIATIONS']}")
    
    body_parts.append(f"\n\nPour activer votre compte :\n{context['call_to_action_url']}")
    body_parts.append(f"\nCe lien est valable 7 jours.")
    
    if signature:
        body_parts.append(f"\n\n{signature}")
    
    body = ''.join(body_parts)
    
    # Construire le HTML
    html_parts = []
    if content_config.get('greeting'):
        html_parts.append(f"<p><strong>{content_config['greeting']}</strong></p>")
    if content_config.get('intro'):
        html_parts.append(f"<h3 style='color: #007bff;'>{content_config['intro']}</h3>")
    if content_config.get('body'):
        body_html = content_config['body'].replace('\n\n', '</p><p>').replace('\n', '<br>')
        html_parts.append(f"<p>{body_html}</p>")
    
    # Informations reviewer
    html_parts.append(f"""
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <h4 style="margin-top: 0;">Vos informations :</h4>
        <ul>
            <li><strong>Email :</strong> {context['USER_EMAIL']}</li>
            <li><strong>Spécialités :</strong> {context['REVIEWER_SPECIALTIES']}</li>
            <li><strong>Affiliations :</strong> {context['REVIEWER_AFFILIATIONS']}</li>
        </ul>
    </div>
    """)
    
    # Bouton d'activation
    button_text = content_config.get('call_to_action', 'Activer mon compte')
    html_parts.append(f'''
    <div style="text-align: center; margin: 30px 0;">
        <a href="{context['call_to_action_url']}" 
           style="background-color: #007bff; color: white; padding: 12px 25px; 
                  text-decoration: none; border-radius: 5px; display: inline-block;">
            {button_text}
        </a>
    </div>
    <p><em>Ce lien est valable 7 jours.</em></p>
    ''')
    
    if signature:
        signature_html = signature.replace('\n', '<br>')
        html_parts.append(f"<hr><p>{signature_html}</p>")
    
    html = ''.join(html_parts)
    
    # Envoyer l'email
    send_email(subject, [user.email], body, html)



def send_coauthor_notification_email(user, communication, token):
    """Envoie un email de notification à un nouveau co-auteur."""
    from flask import url_for, current_app
    
    # Récupérer le config loader
    config_loader = current_app.config_loader
    
    # Préparer le contexte pour le template
    context = {
        'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
        'USER_EMAIL': user.email,
        'USER_ROLE': 'Co-auteur',
        'COMMUNICATION_TITLE': communication.title,
        'COMMUNICATION_TYPE': 'Article complet' if communication.type == 'article' else 'Work in Progress',
        'COMMUNICATION_ID': communication.id,
        'MAIN_AUTHOR_NAME': communication.authors[0].full_name or communication.authors[0].email
    }
    
    # Choisir le bon template selon si on a un token ou pas
    if token:
        # Nouvel utilisateur avec activation
        template_key = 'activation'
        subject_key = 'coauthor_invitation'
        context['call_to_action_url'] = url_for('main.activate_account', token=token, _external=True)
    else:
        # Utilisateur existant
        template_key = 'coauthor_notification'
        subject_key = 'coauthor_notification'
        context['call_to_action_url'] = url_for('main.mes_communications', _external=True)
    
    # Récupérer le sujet depuis la configuration
    subject = config_loader.get_email_subject(subject_key, **context)
    
    # Récupérer le contenu depuis la configuration
    content_config = config_loader.get_email_content(template_key, **context)
    
    # Récupérer la signature
    signature = config_loader.get_email_signature('default', **context)
    
    # Construire le corps de l'email en texte
    body_parts = []
    if content_config.get('greeting'):
        body_parts.append(content_config['greeting'])
    if content_config.get('intro'):
        body_parts.append(f"\n\n{content_config['intro']}")
    if content_config.get('body'):
        body_parts.append(f"\n\n{content_config['body']}")
    if context.get('call_to_action_url'):
        if token:
            body_parts.append(f"\n\nPour activer votre compte et consulter la communication :\n{context['call_to_action_url']}")
            body_parts.append(f"\nCe lien est valable 7 jours.")
        else:
            body_parts.append(f"\n\nConsulter vos communications :\n{context['call_to_action_url']}")
    if signature:
        body_parts.append(f"\n\n{signature}")
    
    body = ''.join(body_parts)
    
    # Construire le HTML
    html_parts = []
    if content_config.get('greeting'):
        html_parts.append(f"<p><strong>{content_config['greeting']}</strong></p>")
    if content_config.get('intro'):
        html_parts.append(f"<h3 style='color: #007bff;'>{content_config['intro']}</h3>")
    if content_config.get('body'):
        # Remplacer les retours à la ligne par des paragraphes
        body_html = content_config['body'].replace('\n\n', '</p><p>').replace('\n', '<br>')
        html_parts.append(f"<p>{body_html}</p>")
    
    # Ajouter le bouton d'action si présent
    if context.get('call_to_action_url'):
        button_text = content_config.get('call_to_action', 'Accéder à la plateforme')
        html_parts.append(f'''
        <div style="text-align: center; margin: 30px 0;">
            <a href="{context['call_to_action_url']}" 
               style="background-color: #007bff; color: white; padding: 12px 25px; 
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                {button_text}
            </a>
        </div>
        ''')
        
        if token:
            html_parts.append('<p><em>Ce lien est valable 7 jours.</em></p>')
    
    if signature:
        signature_html = signature.replace('\n', '<br>')
        html_parts.append(f"<hr><p>{signature_html}</p>")
    
    html = ''.join(html_parts)
    
    # Envoyer l'email
    send_email(subject, [user.email], body, html)


def send_existing_coauthor_notification_email(user, communication):
    """Envoie un email de notification à un co-auteur existant."""
    from flask import url_for, current_app
    
    # Récupérer le config loader
    config_loader = current_app.config_loader
    
    # Préparer le contexte pour le template
    context = {
        'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
        'USER_EMAIL': user.email,
        'USER_ROLE': 'Co-auteur',
        'COMMUNICATION_TITLE': communication.title,
        'COMMUNICATION_TYPE': 'Article complet' if communication.type == 'article' else 'Work in Progress',
        'COMMUNICATION_ID': communication.id,
        'MAIN_AUTHOR_NAME': communication.authors[0].full_name or communication.authors[0].email,
        'call_to_action_url': url_for('main.mes_communications', _external=True)
    }
    
    # Récupérer le sujet depuis la configuration
    subject = config_loader.get_email_subject('coauthor_notification', **context)
    
    # Récupérer le contenu depuis la configuration
    content_config = config_loader.get_email_content('coauthor_notification', **context)
    
    # Récupérer la signature
    signature = config_loader.get_email_signature('default', **context)
    
    # Construire le corps de l'email en texte
    body_parts = []
    if content_config.get('greeting'):
        body_parts.append(content_config['greeting'])
    if content_config.get('intro'):
        body_parts.append(f"\n\n{content_config['intro']}")
    if content_config.get('body'):
        body_parts.append(f"\n\n{content_config['body']}")
    if context.get('call_to_action_url'):
        body_parts.append(f"\n\nConsulter vos communications :\n{context['call_to_action_url']}")
    if signature:
        body_parts.append(f"\n\n{signature}")
    
    body = ''.join(body_parts)
    
    # Construire le HTML
    html_parts = []
    if content_config.get('greeting'):
        html_parts.append(f"<p><strong>{content_config['greeting']}</strong></p>")
    if content_config.get('intro'):
        html_parts.append(f"<h3 style='color: #007bff;'>{content_config['intro']}</h3>")
    if content_config.get('body'):
        # Remplacer les retours à la ligne par des paragraphes
        body_html = content_config['body'].replace('\n\n', '</p><p>').replace('\n', '<br>')
        html_parts.append(f"<p>{body_html}</p>")
    
    # Ajouter le bouton d'action
    if context.get('call_to_action_url'):
        button_text = content_config.get('call_to_action', 'Consulter mes communications')
        html_parts.append(f'''
        <div style="text-align: center; margin: 30px 0;">
            <a href="{context['call_to_action_url']}" 
               style="background-color: #007bff; color: white; padding: 12px 25px; 
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                {button_text}
            </a>
        </div>
        ''')
    
    if signature:
        signature_html = signature.replace('\n', '<br>')
        html_parts.append(f"<hr><p>{signature_html}</p>")
    
    html = ''.join(html_parts)
    
    # Envoyer l'email
    send_email(subject, [user.email], body, html)


def send_review_reminder_email(reviewer, assignments):
    """Envoie un email de rappel à un reviewer avec ses reviews en attente."""
    from flask import url_for, current_app
    
    # Récupérer le config loader
    config_loader = current_app.config_loader
    
    # Compter les reviews en attente et en retard
    total_assignments = len(assignments)
    overdue_count = sum(1 for assignment in assignments if assignment.is_overdue)
    
    # Préparer le contexte
    context = {
        'REVIEWER_NAME': reviewer.full_name or reviewer.email,
        'REVIEWER_SPECIALTIES': reviewer.specialites_codes or 'Non spécifiées',
        'PENDING_REVIEWS_COUNT': total_assignments,
        'OVERDUE_COUNT': overdue_count,
        'OVERDUE_MESSAGE': f"⚠️ {overdue_count} review(s) sont en retard." if overdue_count > 0 else ""
    }
    
    # Récupérer le sujet et le contenu
    subject = config_loader.get_email_subject('review_reminder', **context)
    content_config = config_loader.get_email_content('review_reminder', **context)
    signature = config_loader.get_email_signature('scientific', **context)
    
    # Construire la liste des reviews pour le texte
    reviews_text_list = []
    reviews_html_list = []
    
    for assignment in assignments:
        comm = assignment.communication
        status_text = "⚠️ EN RETARD" if assignment.is_overdue else "En attente"
        due_text = f"Échéance: {assignment.due_date.strftime('%d/%m/%Y')}" if assignment.due_date else "Pas d'échéance"
        
        # Version texte
        reviews_text_list.append(f"""
- Communication #{comm.id}: "{comm.title[:80]}..."
  Statut: {status_text}
  {due_text}
  Lien: {url_for('main.submit_review', comm_id=comm.id, _external=True)}
""")
        
        # Version HTML
        reviews_html_list.append(f"""
<div style="margin: 15px 0; padding: 15px; border-left: 4px solid {'#dc3545' if assignment.is_overdue else '#007bff'}; background-color: #f8f9fa;">
    <h4 style="margin-top: 0; color: #333;">Communication #{comm.id}</h4>
    <p><strong>Titre:</strong> {comm.title}</p>
    <p><strong>Statut:</strong> <span style="color: {'#dc3545' if assignment.is_overdue else '#28a745'};">{status_text}</span></p>
    <p><strong>{due_text}</strong></p>
    <a href="{url_for('main.submit_review', comm_id=comm.id, _external=True)}" 
       style="background-color: #28a745; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;">
        Effectuer la review
    </a>
</div>
""")
    
    # Ajouter les listes au contexte
    context['REVIEWS_LIST_TEXT'] = ''.join(reviews_text_list)
    context['REVIEWS_LIST_HTML'] = ''.join(reviews_html_list)
    context['call_to_action_url'] = url_for('main.reviewer_dashboard', _external=True)
    
    # Construire l'email
    body_parts = [
        content_config.get('greeting', ''),
        f"\n\n{content_config.get('intro', '')}",
        f"\n\n{content_config.get('body', '')}",
        f"\n\n{context['REVIEWS_LIST_TEXT']}",
        f"\nDashboard reviewer: {context['call_to_action_url']}",
        f"\n\n{signature}"
    ]
    
    body = ''.join(body_parts)
    
    # HTML
    html_parts = [
        f"<p><strong>{content_config.get('greeting', '')}</strong></p>",
        f"<h3 style='color: #007bff;'>{content_config.get('intro', '')}</h3>",
        f"<p>{content_config.get('body', '').replace(chr(10), '<br>')}</p>",
        context['REVIEWS_LIST_HTML'],
        f'''<div style="text-align: center; margin: 30px 0;">
            <a href="{context['call_to_action_url']}" 
               style="background-color: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px;">
                Accéder à mon dashboard reviewer
            </a>
        </div>''',
        f"<hr><p>{signature.replace(chr(10), '<br>')}</p>"
    ]
    
    html = ''.join(html_parts)
    
    # Envoyer l'email
    send_email(subject, [reviewer.email], body, html)


def send_qr_code_reminder_email(user, user_communications):
    """Envoie un email de rappel sur l'utilité du QR code."""
    from flask import url_for, current_app
    
    # Récupérer le config loader
    config_loader = current_app.config_loader
    
    # Préparer le contexte
    context = {
        'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
        'USER_EMAIL': user.email,
        'COMMUNICATIONS_COUNT': len(user_communications),
        'call_to_action_url': url_for('main.mes_communications', _external=True)
    }
    
    # Récupérer le sujet depuis la configuration
    subject = config_loader.get_email_subject('qr_code_ready', **context)
    
    # Utiliser un contenu spécifique pour le QR code (ou créer un template custom)
    # Pour l'instant, on garde la logique existante
    
    # Construire la liste des communications
    comm_list = ""
    for comm in user_communications:
        comm_list += f"""
- "{comm.title}" (#{comm.id})
  Type: {'Article' if comm.type == 'article' else 'Work in Progress'}
  Statut: {comm.status.value}
"""
    
    # Corps de l'email en texte
    body = f"""
Bonjour {context['USER_FIRST_NAME']},

Nous espérons que la préparation de votre poster pour le congrès se passe bien !

RAPPEL IMPORTANT : QR Code pour votre poster

N'oubliez pas d'ajouter un QR code sur votre poster ! Ce QR code permettra aux participants de :
✓ Accéder directement à votre résumé depuis leur smartphone
✓ Télécharger votre article complet s'il est disponible
✓ Consulter tous vos documents associés

Comment récupérer votre QR code :
1. Connectez-vous sur la plateforme
2. Allez dans "Mes communications" : {context['call_to_action_url']}
3. Cliquez sur "Télécharger QR Code" pour chacune de vos communications

Vos communications :
{comm_list}

Pourquoi utiliser le QR code ?
- Facilite l'accès aux documents pour les participants
- Évite les échanges d'emails après le congrès
- Modernise la présentation de votre poster
- Permet un suivi des consultations

Pour toute question, n'hésitez pas à nous contacter.

{config_loader.get_email_signature('default', **context)}
"""

    # Version HTML
    comm_html = ""
    for comm in user_communications:
        comm_html += f"""
<tr>
    <td style="padding: 10px; border: 1px solid #ddd;">{comm.title}</td>
    <td style="padding: 10px; border: 1px solid #ddd;">{'Article' if comm.type == 'article' else 'Work in Progress'}</td>
    <td style="padding: 10px; border: 1px solid #ddd;">{comm.status.value}</td>
</tr>
"""

    html = f"""
<h2>QR Code pour vos posters</h2>

<p>Bonjour <strong>{context['USER_FIRST_NAME']}</strong>,</p>

<p>Nous espérons que la préparation de votre poster pour le congrès se passe bien !</p>

<div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
    <h3 style="color: #856404; margin-top: 0;">RAPPEL IMPORTANT : QR Code pour votre poster</h3>
    <p style="margin-bottom: 0;">N'oubliez pas d'ajouter un QR code sur votre poster !</p>
</div>

<h3>Ce QR code permettra aux participants de :</h3>
<ul>
    <li>Accéder directement à votre résumé depuis leur smartphone</li>
    <li>Télécharger votre article complet s'il est disponible</li>
    <li>Consulter tous vos documents associés</li>
</ul>

<h3>Comment récupérer votre QR code :</h3>
<ol>
    <li>Connectez-vous sur la plateforme</li>
    <li>Allez dans <a href="{context['call_to_action_url']}">Mes communications</a></li>
    <li>Cliquez sur "Télécharger QR Code" pour chacune de vos communications</li>
</ol>

<h3>Vos communications :</h3>
<table style="border-collapse: collapse; width: 100%; margin: 20px 0;">
    <tr style="background-color: #f8f9fa;">
        <th style="padding: 10px; border: 1px solid #ddd;">Titre</th>
        <th style="padding: 10px; border: 1px solid #ddd;">Type</th>
        <th style="padding: 10px; border: 1px solid #ddd;">Statut</th>
    </tr>
    {comm_html}
</table>

<div style="text-align: center; margin: 30px 0;">
    <a href="{context['call_to_action_url']}" 
       style="background-color: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
        Accéder à mes communications
    </a>
</div>

<p>{config_loader.get_email_signature('default', **context).replace(chr(10), '<br>')}</p>
"""

    # Envoyer l'email
    send_email(subject, [user.email], body, html)


def send_decision_notification_email(communication, decision, comments=None):
    """Envoie une notification de décision à tous les auteurs."""
    from flask import current_app
    
    if not communication.authors:
        raise ValueError("Aucun auteur à notifier")
    
    # Récupérer le config loader
    config_loader = current_app.config_loader
    
    # Récupérer tous les emails des auteurs
    author_emails = [author.email for author in communication.authors if author.email]
    
    if not author_emails:
        raise ValueError("Aucun email d'auteur valide")
    
    # Préparer le contexte
    context = {
        'AUTHOR_NAME': communication.authors[0].full_name or communication.authors[0].email,
        'COMMUNICATION_TITLE': communication.title,
        'COMMUNICATION_ID': communication.id,
        'COMMUNICATION_TYPE': communication.type.upper(),
        'DECISION_STATUS': decision.upper(),
        'DECISION_DATE': 'aujourd\'hui',  # ou une vraie date
        'DECISION_DETAILS': comments or ''
    }
    
    # Mapping des décisions vers les clés de template
    decision_mapping = {
        'accepter': 'decision_accept',
        'rejeter': 'decision_reject', 
        'reviser': 'decision_revise'
    }
    
    template_key = decision_mapping.get(decision, 'decision_notification')
    
    # Récupérer le sujet depuis la configuration
    subject = config_loader.get_email_subject(template_key, **context)
    
    # Récupérer le contenu depuis la configuration
    content_config = config_loader.get_email_content('decision_notification', **context)
    
    # Récupérer la signature
    signature = config_loader.get_email_signature('scientific', **context)
    
    # Corps de l'email
    body_parts = []
    if content_config.get('greeting'):
        body_parts.append(content_config['greeting'])
    if content_config.get('intro'):
        body_parts.append(f"\n\n{content_config['intro']}")
    if content_config.get('body'):
        body_parts.append(f"\n\n{content_config['body']}")
    if comments:
        body_parts.append(f"\n\nCommentaires de l'équipe scientifique :\n{comments}")
    if signature:
        body_parts.append(f"\n\n{signature}")
    
    body = ''.join(body_parts)
    
    # Couleurs selon la décision
    decision_colors = {
        'accepter': '#28a745',
        'rejeter': '#dc3545',
        'reviser': '#ffc107'
    }
    
    color = decision_colors.get(decision, '#007bff')
    
    # Version HTML
    comments_html = ""
    if comments:
        comments_html = f"""
<div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">
    <h4>Commentaires de l'équipe scientifique :</h4>
    <p>{comments.replace(chr(10), "<br>")}</p>
</div>
"""

    html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: {color}; color: white; padding: 20px; text-align: center;">
        <h1 style="margin: 0;">{content_config.get('intro', 'Décision concernant votre communication')}</h1>
    </div>
    
    <div style="padding: 20px; background-color: #f8f9fa;">
        <p><strong>{content_config.get('greeting', '')}</strong></p>
        
        <p>{content_config.get('body', '').replace(chr(10), '<br>')}</p>
        
        {comments_html}
        
        <p style="margin-top: 20px;">{signature.replace(chr(10), '<br>')}</p>
    </div>
</div>
"""

    # Envoyer l'email à tous les auteurs
    send_email(subject, author_emails, body, html)


def send_biot_fourier_audition_notification(communication):
    """Envoie une notification d'audition Biot-Fourier à l'auteur principal."""
    from flask import current_app
    
    if not communication.authors:
        raise ValueError("Aucun auteur à notifier")
    
    # Récupérer le config loader
    config_loader = current_app.config_loader
    
    # Récupérer l'auteur principal (premier auteur)
    main_author = communication.authors[0]
    
    if not main_author.email:
        raise ValueError("Pas d'email pour l'auteur principal")
    
    # Préparer le contexte
    context = {
        'AUTHOR_NAME': main_author.full_name or main_author.email,
        'COMMUNICATION_TITLE': communication.title,
        'COMMUNICATION_ID': communication.id,
        'COMMUNICATION_TYPE': communication.type.upper()
    }
    
    # Récupérer le sujet depuis la configuration
    subject = config_loader.get_email_subject('biot_fourier_nomination', **context)
    
    # Récupérer la signature
    signature = config_loader.get_email_signature('scientific', **context)
    
    # Corps de l'email en texte (gardé pour compatibilité)
    body = f"""
Bonjour {context['AUTHOR_NAME']},

Félicitations !

Votre communication a été sélectionnée pour l'audition du Prix Biot-Fourier.

Titre de la communication : {context['COMMUNICATION_TITLE']}
ID : {context['COMMUNICATION_ID']}
Type : {context['COMMUNICATION_TYPE']}

Le Prix Biot-Fourier récompense chaque année la meilleure communication présentée par un jeune chercheur (moins de 35 ans) lors du Congrès.

PROCHAINES ÉTAPES :
- Vous devrez présenter votre travail lors d'une audition devant le jury
- Durée de présentation : 15 minutes + 10 minutes de questions
- Date et lieu : à confirmer (pendant le congrès)

INFORMATIONS IMPORTANTES :
- Seul l'auteur principal peut concourir (vous)
- Vous devez avoir moins de 35 ans au moment du congrès
- La présentation doit être faite par vous-même

Nous vous contacterons prochainement avec les détails pratiques de l'audition.

Encore toutes nos félicitations pour cette sélection !

{signature}
"""

    # Version HTML
    html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: linear-gradient(135deg, #ffc107, #ff8c00); color: white; padding: 30px; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">Félicitations !</h1>
        <h2 style="margin: 10px 0 0 0; font-weight: normal;">Sélection Prix Biot-Fourier</h2>
    </div>
    
    <div style="padding: 30px; background-color: #f8f9fa;">
        <p style="font-size: 18px; color: #28a745; font-weight: bold;">
            Votre communication a été sélectionnée pour l'audition du Prix Biot-Fourier !
        </p>
        
        <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
            <h3 style="color: #007bff; margin-top: 0;">Votre communication sélectionnée</h3>
            <p><strong>Titre :</strong> {context['COMMUNICATION_TITLE']}</p>
            <p><strong>ID :</strong> {context['COMMUNICATION_ID']}</p>
            <p><strong>Type :</strong> {context['COMMUNICATION_TYPE']}</p>
            <p><strong>Auteur principal :</strong> {context['AUTHOR_NAME']}</p>
        </div>
        
        <div style="background-color: #e7f3ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #004085; margin-top: 0;">À propos du Prix Biot-Fourier</h3>
            <p>Le Prix Biot-Fourier récompense chaque année la meilleure communication présentée par un <strong>jeune chercheur (moins de 35 ans)</strong> lors du Congrès.</p>
        </div>
        
        <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #ffeaa7;">
            <h3 style="color: #856404; margin-top: 0;">Prochaines étapes</h3>
            <ul style="margin-bottom: 0;">
                <li>Présentation devant le jury pendant le congrès</li>
                <li><strong>Durée :</strong> 15 minutes + 10 minutes de questions</li>
                <li><strong>Date et lieu :</strong> à confirmer</li>
                <li>Seul l'auteur principal peut concourir</li>
            </ul>
        </div>
        
        <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #f5c6cb;">
            <h3 style="color: #721c24; margin-top: 0;">Conditions importantes</h3>
            <ul style="margin-bottom: 0;">
                <li>Vous devez avoir <strong>moins de 35 ans</strong> au moment du congrès</li>
                <li>La présentation doit être faite <strong>par vous-même</strong></li>
                <li>Confirmation de participation requise</li>
            </ul>
        </div>
        
        <p style="text-align: center; margin: 30px 0;">
            <strong>Nous vous contacterons prochainement avec les détails pratiques de l'audition.</strong>
        </p>
        
        <div style="text-align: center; background-color: #28a745; color: white; padding: 15px; border-radius: 8px;">
            <strong>Encore toutes nos félicitations pour cette sélection !</strong>
        </div>
        
        <p style="margin-top: 30px;">{signature.replace(chr(10), '<br>')}</p>
    </div>
</div>
"""

    # Envoyer uniquement à l'auteur principal
    send_email(subject, [main_author.email], body, html)


# === FONCTIONS UTILITAIRES POUR L'ADMIN ===

def get_admin_email_templates():
    """Retourne les templates d'emails pour l'interface admin."""
    from flask import current_app
    
    config_loader = current_app.config_loader
    return config_loader.get_admin_email_templates()


# === FONCTIONS SUPPLÉMENTAIRES ===

def send_review_decline_notification(assignment, decline_reason, other_reason=None):
    """Envoie une notification aux admins quand une review est refusée."""
    from flask import url_for, current_app
    from .models import User
    
    # Récupérer le config loader
    config_loader = current_app.config_loader
    
    # Récupérer tous les admins
    admins = User.query.filter_by(is_admin=True).all()
    admin_emails = [admin.email for admin in admins if admin.email]
    
    if not admin_emails:
        current_app.logger.warning("Aucun admin trouvé pour notification de refus de review")
        return
    
    reviewer = assignment.reviewer
    communication = assignment.communication
    
    # Construire la raison du refus
    reason_text = {
        'conflict': 'Conflit d\'intérêt',
        'workload': 'Surcharge de travail',
        'expertise': 'Expertise insuffisante',
        'unavailable': 'Indisponible',
        'other': f'Autre raison : {other_reason}' if other_reason else 'Autre raison'
    }.get(decline_reason, 'Raison non spécifiée')
    
    # Préparer le contexte
    context = {
        'REVIEWER_NAME': reviewer.full_name or reviewer.email,
        'COMMUNICATION_TITLE': communication.title,
        'COMMUNICATION_ID': communication.id,
        'DECLINE_REASON': reason_text
    }
    
    # URL pour réassigner
    reassign_url = url_for('admin.suggest_reviewers', comm_id=communication.id, _external=True)
    
    subject = config_loader.get_email_subject('admin_alert', **context)
    if 'Review refusée' not in subject:
        subject = f"Review refusée - {communication.title[:50]}..."
    
    # Corps de l'email en texte
    body = f"""
NOTIFICATION : Review refusée

Une review a été refusée par un reviewer et nécessite une réassignation.

DÉTAILS DE LA COMMUNICATION :
- Titre : {communication.title}
- ID : {communication.id}
- Type : {communication.type}
- Statut : {communication.status.value}
- Auteurs : {', '.join([author.full_name or author.email for author in communication.authors])}
- Thématiques : {communication.thematiques_codes or 'Non spécifiées'}

REVIEWER QUI A REFUSÉ :
- Nom : {reviewer.full_name or reviewer.email}
- Email : {reviewer.email}
- Spécialités : {reviewer.specialites_codes or 'Non spécifiées'}

REFUS :
- Date : {assignment.declined_at.strftime('%d/%m/%Y à %H:%M') if hasattr(assignment, 'declined_at') and assignment.declined_at else 'Non définie'}
- Raison : {reason_text}

ACTION REQUISE :
Veuillez réassigner cette review à un autre reviewer disponible.

Lien direct pour réassigner : {reassign_url}

Dashboard admin : {url_for('admin.admin_dashboard', _external=True)}

{config_loader.get_email_signature('system', **context)}
"""

    # Corps de l'email en HTML
    html = f"""
<h2 style="color: #dc3545;">Review refusée - Action requise</h2>

<p>Une review a été refusée par un reviewer et nécessite une <strong>réassignation immédiate</strong>.</p>

<div style="border: 1px solid #dc3545; border-radius: 5px; padding: 15px; margin: 20px 0; background-color: #f8d7da;">
    <h3 style="color: #721c24; margin-top: 0;">Communication concernée</h3>
    <ul>
        <li><strong>Titre :</strong> {communication.title}</li>
        <li><strong>ID :</strong> {communication.id}</li>
        <li><strong>Type :</strong> {communication.type}</li>
        <li><strong>Statut :</strong> {communication.status.value}</li>
        <li><strong>Auteurs :</strong> {', '.join([author.full_name or author.email for author in communication.authors])}</li>
        <li><strong>Thématiques :</strong> {communication.thematiques_codes or 'Non spécifiées'}</li>
    </ul>
</div>

<div style="border: 1px solid #ffc107; border-radius: 5px; padding: 15px; margin: 20px 0; background-color: #fff3cd;">
    <h3 style="color: #856404; margin-top: 0;">Reviewer qui a refusé</h3>
    <ul>
        <li><strong>Nom :</strong> {reviewer.full_name or reviewer.email}</li>
        <li><strong>Email :</strong> {reviewer.email}</li>
        <li><strong>Spécialités :</strong> {reviewer.specialites_codes or 'Non spécifiées'}</li>
    </ul>
</div>

<div style="border: 1px solid #17a2b8; border-radius: 5px; padding: 15px; margin: 20px 0; background-color: #d1ecf1;">
    <h3 style="color: #0c5460; margin-top: 0;">Détails du refus</h3>
    <ul>
        <li><strong>Date :</strong> {assignment.declined_at.strftime('%d/%m/%Y à %H:%M') if hasattr(assignment, 'declined_at') and assignment.declined_at else 'Non définie'}</li>
        <li><strong>Raison :</strong> {reason_text}</li>
    </ul>
</div>

<div style="text-align: center; margin: 30px 0;">
    <a href="{reassign_url}" style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
        Réassigner cette review
    </a>
</div>

<div style="text-align: center; margin: 20px 0;">
    <a href="{url_for('admin.admin_dashboard', _external=True)}" style="background-color: #6c757d; color: white; padding: 8px 20px; text-decoration: none; border-radius: 3px;">
        Dashboard admin
    </a>
</div>

<hr>
<p style="color: #666; font-size: 12px; text-align: center;">
    {config_loader.get_email_signature('system', **context).replace(chr(10), '<br>')}
</p>
"""

    # Envoyer l'email
    try:
        send_email(subject, admin_emails, body, html)
        current_app.logger.info(f"Notification de refus de review envoyée aux admins pour la communication {communication.id}")
    except Exception as e:
        current_app.logger.error(f"Erreur envoi notification refus review: {e}")
        raise e


def send_grouped_review_notifications():
    """Envoie un email groupé à chaque reviewer avec toutes ses reviews assignées."""
    from flask import current_app
    from .models import User, ReviewAssignment
    from datetime import datetime
    
    # Récupérer tous les reviewers ayant des assignations en attente
    reviewers_with_assignments = {}
    
    pending_assignments = ReviewAssignment.query.filter_by(
        status='assigned',
        notification_sent_at=None  # Pas encore notifiés
    ).all()
    
    # Grouper par reviewer
    for assignment in pending_assignments:
        reviewer_id = assignment.reviewer_id
        if reviewer_id not in reviewers_with_assignments:
            reviewers_with_assignments[reviewer_id] = {
                'reviewer': assignment.reviewer,
                'assignments': []
            }
        reviewers_with_assignments[reviewer_id]['assignments'].append(assignment)
    
    if not reviewers_with_assignments:
        current_app.logger.info("Aucune assignation en attente à notifier")
        return {'sent': 0, 'errors': []}
    
    sent_count = 0
    errors = []
    
    # Envoyer un email à chaque reviewer
    for reviewer_id, data in reviewers_with_assignments.items():
        try:
            reviewer = data['reviewer']
            assignments = data['assignments']
            
            send_grouped_review_notification_to_reviewer(reviewer, assignments)
            
            # Marquer les assignations comme notifiées
            for assignment in assignments:
                assignment.notification_sent_at = datetime.utcnow()
            
            sent_count += 1
            current_app.logger.info(f"Email groupé envoyé à {reviewer.email} pour {len(assignments)} reviews")
            
        except Exception as e:
            error_msg = f"Erreur envoi email à {reviewer.email}: {str(e)}"
            errors.append(error_msg)
            current_app.logger.error(error_msg)
    
    return {
        'sent': sent_count,
        'total_assignments': sum(len(data['assignments']) for data in reviewers_with_assignments.values()),
        'errors': errors
    }


def send_grouped_review_notification_to_reviewer(reviewer, assignments):
    """Envoie l'email groupé à un reviewer spécifique."""
    from flask import url_for, current_app
    
    # Récupérer le config loader
    config_loader = current_app.config_loader
    
    # Préparer le contexte
    context = {
        'REVIEWER_NAME': reviewer.full_name or reviewer.email,
        'REVIEWER_SPECIALTIES': reviewer.specialites_codes or 'Non spécifiées',
        'REVIEWS_COUNT': len(assignments)
    }
    
    subject = config_loader.get_email_subject('review_assigned', **context)
    
    # Générer les liens pour chaque review
    reviews_html = ""
    reviews_text = ""
    
    for i, assignment in enumerate(assignments, 1):
        communication = assignment.communication
        authors_list = ', '.join([author.full_name or author.email for author in communication.authors])
        
        # Lien pour voir/faire la review
        review_url = url_for('main.submit_review', comm_id=communication.id, _external=True)
        
        # Lien pour refuser cette review spécifique
        decline_url = url_for('main.decline_review_assignment', assignment_id=assignment.id, _external=True)
        
        # Échéance
        due_date_str = assignment.due_date.strftime('%d/%m/%Y') if assignment.due_date else 'Non définie'
        
        # HTML pour cette review
        reviews_html += f"""
        <div style="border: 1px solid #dee2e6; border-radius: 5px; padding: 15px; margin: 15px 0; background-color: #f8f9fa;">
            <h4 style="color: #007bff; margin-top: 0;">Review #{i}</h4>
            <p><strong>Titre :</strong> {communication.title}</p>
            <p><strong>Auteurs :</strong> {authors_list}</p>
            <p><strong>Type :</strong> {communication.type.title()}</p>
            <p><strong>Thématiques :</strong> {communication.thematiques_codes or 'Non spécifiées'}</p>
            <p><strong>Échéance :</strong> {due_date_str}</p>
            
            <div style="margin-top: 15px;">
                <a href="{review_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-right: 10px;">
                    Faire la review
                </a>
                <a href="{decline_url}" style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    Refuser cette review
                </a>
            </div>
        </div>
        """
        
        # Version texte
        reviews_text += f"""
Review #{i}:
- Titre: {communication.title}
- Auteurs: {authors_list}
- Type: {communication.type.title()}
- Thématiques: {communication.thematiques_codes or 'Non spécifiées'}
- Échéance: {due_date_str}
- Lien review: {review_url}
- Lien refus: {decline_url}

"""
    
    # Corps de l'email en texte
    body = f"""
Bonjour {reviewer.full_name or reviewer.email},

Vous avez été assigné(e) à {len(assignments)} review(s) pour le congrès.

{reviews_text}

Dashboard reviewer: {url_for('main.reviewer_dashboard', _external=True)}

Important:
- Consultez chaque communication attentivement
- Respectez les échéances indiquées
- En cas d'impossibilité, utilisez le lien "Refuser cette review"
- Pour toute question, contactez l'équipe organisatrice

{config_loader.get_email_signature('scientific', **context)}
"""

    # Corps de l'email en HTML
    html = f"""
<h2 style="color: #007bff;">Vos assignations de reviews</h2>

<p>Bonjour <strong>{reviewer.full_name or reviewer.email}</strong>,</p>

<p>Vous avez été assigné(e) à <strong>{len(assignments)} review(s)</strong> pour le congrès.</p>

<div style="background-color: #e7f3ff; border-left: 4px solid #007bff; padding: 15px; margin: 20px 0;">
    <h3 style="margin-top: 0; color: #0056b3;">Informations importantes</h3>
    <ul>
        <li>Consultez chaque communication attentivement</li>
        <li>Respectez les échéances indiquées</li>
        <li>En cas d'impossibilité, utilisez le bouton "Refuser cette review"</li>
        <li>Vos spécialités: <strong>{reviewer.specialites_codes or 'Non spécifiées'}</strong></li>
    </ul>
</div>

<h3 style="color: #28a745;">Vos reviews à effectuer:</h3>

{reviews_html}

<div style="text-align: center; margin: 30px 0;">
    <a href="{url_for('main.reviewer_dashboard', _external=True)}" style="background-color: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px;">
        Accéder à mon dashboard reviewer
    </a>
</div>

<hr>
<p style="color: #666; font-size: 12px;">
    {config_loader.get_email_signature('scientific', **context).replace(chr(10), '<br>')}
</p>
"""

    # Envoyer l'email
    send_email(subject, [reviewer.email], body, html)


 # AJOUT dans app/emails.py

def send_hal_collection_request(recipient_email, email_data, custom_message=""):
    """Envoie une demande de création de collection HAL."""
    
    subject = f"Demande de création de collection HAL - {email_data['conference_name']}"
    
    # Corps du message basé sur votre exemple
    body_parts = [
        "Bonjour,",
        "",
        f"Je suis {email_data['contact_name']}, {email_data['contact_title']}, membre de l'équipe d'organisation du Congrès de la Société Française de Thermique 2026 qui se déroulera à {email_data['conference_location']} le {email_data['conference_dates']}.",
        "",
        "Dans le cadre de ce congrès, nous souhaitons déposer l'ensemble des communications acceptées (articles complets, work in progress et posters) dans une collection dédiée sur HAL.",
        "",
        "**Informations sur la collection demandée :**",
        f"* **Nom de la collection :** {email_data['conference_name']} - 34ème Congrès de la Société Française de Thermique",
        f"* **Identifiant souhaité :** {email_data['collection_id']}",
        "* **Type de documents :** Articles de conférences, communications, posters",
        f"* **Nombre estimé de documents :** ~{email_data['estimated_docs']} publications",
        "* **Domaine scientifique :** Sciences de l'ingénieur (thermique, énergétique)",
        "",
        "**Contexte organisationnel :**",
        "* **Organisateur principal :** Société Française de Thermique",
        f"* **Institution d'accueil :** {email_data.get('organizing_lab_name', 'Université de Lorraine')}",
        f"* **Contact organisateur :** {email_data['contact_email']}",
        f"* **Mon login HAL :** {email_data['hal_login']}",
        "",
        "**Objectifs :**",
        "* Centraliser toutes les publications du congrès",
        "* Faciliter la diffusion des travaux de recherche",
        "* Automatiser le dépôt via l'API SWORD",
        "* Assurer une visibilité maximale aux contributions",
        "",
        "**Planning :**",
        f"* **Soumissions :** Novembre 2025 - {email_data['submission_deadline']}",
        f"* **Congrès :** {email_data['conference_dates']}",
        f"* **Dépôts HAL prévus :** À partir de {email_data['deposit_start']}",
        ""
    ]
    
    # Ajouter un message personnalisé si fourni
    if custom_message.strip():
        body_parts.extend([
            "**Message supplémentaire :**",
            custom_message.strip(),
            ""
        ])
    
    body_parts.extend([
        "Pourriez-vous me confirmer la création de cette collection et m'indiquer les éventuelles étapes supplémentaires à suivre ?",
        "",
        "Je reste à votre disposition pour tout complément d'information.",
        "",
        "Cordialement,",
        f"{email_data['contact_name']}",
        f"{email_data['contact_title']}",
        f"Email : {email_data['contact_email']}"
    ])
    
    body = '\n'.join(body_parts)
    
    # Version HTML
    html_parts = []
    for line in body_parts:
        if line.startswith('**') and line.endswith('**'):
            # Titre en gras
            title = line.replace('**', '')
            html_parts.append(f"<p><strong>{title}</strong></p>")
        elif line.startswith('* **') and '**' in line:
            # Élément de liste avec partie en gras
            parts = line.split('**')
            if len(parts) >= 3:
                html_parts.append(f"<li><strong>{parts[1]}</strong>{parts[2]}</li>")
            else:
                html_parts.append(f"<li>{line[2:]}</li>")
        elif line.startswith('* '):
            # Élément de liste simple
            html_parts.append(f"<li>{line[2:]}</li>")
        elif line == "":
            # Ligne vide
            html_parts.append("<br>")
        else:
            # Paragraphe normal
            html_parts.append(f"<p>{line}</p>")
    
    html = ''.join(html_parts)
    html = f"<div style='font-family: Arial, sans-serif; line-height: 1.6;'>{html}</div>"
    
    # Envoyer l'email
    send_email(subject, [recipient_email], body, html)   
