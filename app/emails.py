from flask_mail import Message
from app import mail

def send_email(subject, recipients, body, html=None):
    msg = Message(subject=subject, recipients=recipients, body=body, html=html)
    mail.send(msg)


def send_activation_email_to_user(user, token):
    """Envoie l'email d'activation à un reviewer."""
    from flask import url_for

    activation_url = url_for('main.activate_account', token=token, _external=True)

    subject = "Activation de votre compte reviewer - SFT 2026"
    body = f"""
Bonjour {user.full_name or user.email},

Votre compte reviewer a été créé avec succès. Pour commencer, veuillez activer votre compte en cliquant sur le lien suivant :

Activez votre compte : {activation_url}

Ce lien est valable 7 jours.

Après l'activation de votre compte, vous pourrez créer votre mot de passe et compléter votre profil en vous connectant à notre plateforme.

Cordialement,
L'équipe SFT 2026
"""

    html = f'''
<p>Bonjour <strong>{user.full_name or user.email}</strong>,</p>
<p>Votre compte reviewer a été créé avec succès. Pour commencer, veuillez activer votre compte en cliquant sur le lien suivant :</p>
<p><a href="{activation_url}">Cliquer ici pour activer votre compte</a></p>
<p><em>Ce lien est valable 7 jours.</em></p>
<p>Après l'activation de votre compte, vous pourrez créer votre mot de passe et compléter votre profil en vous connectant à notre plateforme.</p>
<p>Cordialement,<br/>L'équipe SFT 2026</p>
'''

    # Utilise la fonction send_email du même fichier
    send_email(subject, [user.email], body, html)
   

# def send_activation_email_to_user(user, token):
#     """Envoie l'email d'activation à un reviewer."""
#     from flask import url_for
    
#     activation_url = url_for('main.activate_account', token=token, _external=True)
    
#     subject = "Activation de votre compte reviewer - SFT 2026"
#     body = f"""
# Bonjour {user.full_name or user.email},

# Activez votre compte : {activation_url}

# Ce lien est valable 7 jours.
# """
#     html = f'''
# <p>Bonjour <strong>{user.full_name or user.email}</strong>,</p>
# <p><a href="{activation_url}">Cliquer ici pour activer votre compte</a></p>
# <p><em>Ce lien est valable 7 jours.</em></p>
# '''
    
#     # Utilise la fonction send_email du même fichier
#     send_email(subject, [user.email], body, html)


def send_coauthor_notification_email(user, communication, token):
    """Envoie un email de notification à un nouveau co-auteur."""
    from flask import url_for
    
    activation_url = url_for('main.activate_account', token=token, _external=True)
    
    subject = f"Vous êtes co-auteur d'une communication - SFT 2026"
    
    # Corps de l'email en texte
    body = f"""
Bonjour {user.full_name or user.email},

Vous avez été ajouté(e) comme co-auteur de la communication suivante pour la conférence SFT 2026 :

Titre : {communication.title}
Type : {'Article complet' if communication.type == 'article' else 'Work in Progress'}
Auteur principal : {communication.authors[0].full_name or communication.authors[0].email}

Pour compléter votre profil et créer votre mot de passe, cliquez sur le lien suivant :
{activation_url}

Ce lien est valable 7 jours.

Une fois votre compte activé, vous pourrez :
- Consulter les détails de la communication
- Mettre à jour vos informations personnelles
- Suivre l'avancement de la soumission

Cordialement,
L'équipe SFT 2026
"""

    # Corps de l'email en HTML
    html = f"""
<h2>Nouvelle co-signature - SFT 2026</h2>

<p>Bonjour <strong>{user.full_name or user.email}</strong>,</p>

<p>Vous avez été ajouté(e) comme co-auteur de la communication suivante pour la conférence SFT 2026 :</p>

<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
    <h3 style="color: #495057; margin-top: 0;">{communication.title}</h3>
    <p><strong>Type :</strong> {'Article complet' if communication.type == 'article' else 'Work in Progress'}</p>
    <p><strong>Auteur principal :</strong> {communication.authors[0].full_name or communication.authors[0].email}</p>
</div>

<p>
    <a href="{activation_url}" style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
        Activer mon compte et consulter la communication
    </a>
</p>

<p><em>Ce lien est valable 7 jours.</em></p>

<h3>Une fois votre compte activé, vous pourrez :</h3>
<ul>
    <li>Consulter les détails de la communication</li>
    <li>Mettre à jour vos informations personnelles</li>
    <li>Suivre l'avancement de la soumission</li>
</ul>

<p>Cordialement,<br>L'équipe SFT 2026</p>
"""

    # Utiliser votre fonction existante
    send_email(subject, [user.email], body, html)


def send_existing_coauthor_notification_email(user, communication):
    """Envoie un email de notification à un co-auteur existant."""
    
    subject = f"Vous êtes co-auteur d'une nouvelle communication - SFT 2026"
    
    # Corps de l'email en texte
    body = f"""
Bonjour {user.full_name or user.email},

Vous avez été ajouté(e) comme co-auteur de la communication suivante pour la conférence SFT 2026 :

Titre : {communication.title}
Type : {'Article complet' if communication.type == 'article' else 'Work in Progress'}
Auteur principal : {communication.authors[0].full_name or communication.authors[0].email}

Vous pouvez dès maintenant consulter cette communication en vous connectant à votre compte sur la plateforme SFT 2026.

Cordialement,
L'équipe SFT 2026
"""

    # Corps de l'email en HTML
    html = f"""
<h2>Nouvelle co-signature - SFT 2026</h2>

<p>Bonjour <strong>{user.full_name or user.email}</strong>,</p>

<p>Vous avez été ajouté(e) comme co-auteur de la communication suivante pour la conférence SFT 2026 :</p>

<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
    <h3 style="color: #495057; margin-top: 0;">{communication.title}</h3>
    <p><strong>Type :</strong> {'Article complet' if communication.type == 'article' else 'Work in Progress'}</p>
    <p><strong>Auteur principal :</strong> {communication.authors[0].full_name or communication.authors[0].email}</p>
</div>

<p>Vous pouvez dès maintenant consulter cette communication en vous connectant à votre compte sur la plateforme SFT 2026.</p>

<p>Cordialement,<br>L'équipe SFT 2026</p>
"""

    send_email(subject, [user.email], body, html)


def send_review_reminder_email(reviewer, assignments):
    """Envoie un email de rappel à un reviewer avec ses reviews en attente."""
    from flask import url_for
    
    # Compter les reviews en attente et en retard
    total_assignments = len(assignments)
    overdue_count = 0
    
    for assignment in assignments:
        if assignment.is_overdue:
            overdue_count += 1
    
    subject = f"Rappel - {total_assignments} review(s) en attente - SFT 2026"
    
    # Construction de la liste des communications
    assignments_list = ""
    for assignment in assignments:
        comm = assignment.communication
        status_text = "⚠️ EN RETARD" if assignment.is_overdue else "En attente"
        due_text = f"Échéance: {assignment.due_date.strftime('%d/%m/%Y')}" if assignment.due_date else "Pas d'échéance"
        
        assignments_list += f"""
- Communication #{comm.id}: "{comm.title[:80]}..."
  Statut: {status_text}
  {due_text}
  Lien: {url_for('main.submit_review', comm_id=comm.id, _external=True)}
"""
    
    # Corps de l'email
    body = f"""
Bonjour {reviewer.full_name or reviewer.email},

Vous avez {total_assignments} review(s) en attente pour la conférence SFT 2026.
{f"⚠️ {overdue_count} review(s) sont en retard." if overdue_count > 0 else ""}

Vos reviews en attente :
{assignments_list}

Pour accéder à votre tableau de bord reviewer :
{url_for('main.reviewer_dashboard', _external=True)}

Merci de bien vouloir compléter vos reviews dans les meilleurs délais.

Cordialement,
L'équipe SFT 2026
"""

    # Version HTML
    assignments_html = ""
    for assignment in assignments:
        comm = assignment.communication
        status_class = "color: red;" if assignment.is_overdue else "color: orange;"
        status_text = "⚠️ EN RETARD" if assignment.is_overdue else "En attente"
        due_text = f"Échéance: {assignment.due_date.strftime('%d/%m/%Y')}" if assignment.due_date else "Pas d'échéance"
        
        assignments_html += f"""
<div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; background-color: #f8f9fa;">
    <h4 style="color: #495057; margin-top: 0;">Communication #{comm.id}</h4>
    <p><strong>Titre:</strong> {comm.title}</p>
    <p><strong>Statut:</strong> <span style="{status_class}">{status_text}</span></p>
    <p><strong>{due_text}</strong></p>
    <p style="margin-top: 15px;">
        <a href="{url_for('main.submit_review', comm_id=comm.id, _external=True)}" 
           style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block;">
           Faire la review
        </a>
    </p>
</div>
"""

    html = f"""
<h2>Rappel - Reviews en attente - SFT 2026</h2>

<p>Bonjour <strong>{reviewer.full_name or reviewer.email}</strong>,</p>

<p>Vous avez <strong>{total_assignments} review(s) en attente</strong> pour la conférence SFT 2026.</p>
{f"<p style='color: red; font-weight: bold;'>⚠️ {overdue_count} review(s) sont en retard.</p>" if overdue_count > 0 else ""}

<h3>Vos reviews en attente :</h3>
{assignments_html}

<div style="text-align: center; margin: 30px 0;">
    <a href="{url_for('main.reviewer_dashboard', _external=True)}" 
       style="background-color: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; display: inline-block;">
        Accéder à mon tableau de bord
    </a>
</div>

<p>Merci de bien vouloir compléter vos reviews dans les meilleurs délais.</p>

<p>Cordialement,<br>L'équipe SFT 2026</p>
"""

    # Envoyer l'email
    send_email(subject, [reviewer.email], body, html)




def send_qr_code_reminder_email(user, user_communications):
    """Envoie un email de rappel sur l'utilité du QR code."""
    from flask import url_for
    
    subject = "QR Code pour vos posters - SFT 2026"
    
    # Construire la liste des communications
    comm_list = ""
    for comm in user_communications:
        comm_url = url_for('main.mes_communications', _external=True)
        comm_list += f"""
- "{comm.title}" (#{comm.id})
  Type: {'Article' if comm.type == 'article' else 'Work in Progress'}
  Statut: {comm.status.value}
"""
    
    # Corps de l'email en texte
    body = f"""
Bonjour {user.full_name or user.email},

Nous espérons que la préparation de votre poster pour le congrès SFT 2026 se passe bien !

RAPPEL IMPORTANT : QR Code pour votre poster

N'oubliez pas d'ajouter un QR code sur votre poster ! Ce QR code permettra aux participants de :
✓ Accéder directement à votre résumé depuis leur smartphone
✓ Télécharger votre article complet s'il est disponible
✓ Consulter tous vos documents associés

Comment récupérer votre QR code :
1. Connectez-vous sur la plateforme SFT 2026
2. Allez dans "Mes communications" : {url_for('main.mes_communications', _external=True)}
3. Cliquez sur "Télécharger QR Code" pour chacune de vos communications

Vos communications :
{comm_list}

Pourquoi utiliser le QR code ?
- Facilite l'accès aux documents pour les participants
- Évite les échanges d'emails après le congrès
- Modernise la présentation de votre poster
- Permet un suivi des consultations

Pour toute question : congres-sft2026@univ-lorraine.fr

Cordialement,
L'équipe SFT 2026
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
<h2>QR Code pour vos posters - SFT 2026</h2>

<p>Bonjour <strong>{user.full_name or user.email}</strong>,</p>

<p>Nous espérons que la préparation de votre poster pour le congrès SFT 2026 se passe bien !</p>

<div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
    <h3 style="color: #856404; margin-top: 0;">📱 RAPPEL IMPORTANT : QR Code pour votre poster</h3>
    <p style="margin-bottom: 0;">N'oubliez pas d'ajouter un QR code sur votre poster !</p>
</div>

<h3>✅ Ce QR code permettra aux participants de :</h3>
<ul>
    <li>Accéder directement à votre résumé depuis leur smartphone</li>
    <li>Télécharger votre article complet s'il est disponible</li>
    <li>Consulter tous vos documents associés</li>
</ul>

<h3>🔧 Comment récupérer votre QR code :</h3>
<ol>
    <li>Connectez-vous sur la plateforme SFT 2026</li>
    <li>Allez dans <a href="{url_for('main.mes_communications', _external=True)}">Mes communications</a></li>
    <li>Cliquez sur "Télécharger QR Code" pour chacune de vos communications</li>
</ol>

<h3>📄 Vos communications :</h3>
<table style="border-collapse: collapse; width: 100%; margin: 20px 0;">
    <tr style="background-color: #f8f9fa;">
        <th style="padding: 10px; border: 1px solid #ddd;">Titre</th>
        <th style="padding: 10px; border: 1px solid #ddd;">Type</th>
        <th style="padding: 10px; border: 1px solid #ddd;">Statut</th>
    </tr>
    {comm_html}
</table>

<div style="background-color: #e7f3ff; border: 1px solid #bee5eb; padding: 15px; border-radius: 5px; margin: 20px 0;">
    <h4 style="color: #004085; margin-top: 0;">💡 Pourquoi utiliser le QR code ?</h4>
    <ul style="margin-bottom: 0;">
        <li>Facilite l'accès aux documents pour les participants</li>
        <li>Évite les échanges d'emails après le congrès</li>
        <li>Modernise la présentation de votre poster</li>
        <li>Permet un suivi des consultations</li>
    </ul>
</div>

<p style="text-align: center; margin: 30px 0;">
    <a href="{url_for('main.mes_communications', _external=True)}" 
       style="background-color: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
        Accéder à mes communications
    </a>
</p>

<p>Pour toute question : <a href="mailto:congres-sft2026@univ-lorraine.fr">congres-sft2026@univ-lorraine.fr</a></p>

<p>Cordialement,<br>L'équipe SFT 2026</p>
"""

    # Envoyer l'email
    send_email(subject, [user.email], body, html)


def send_decision_notification_email(communication, decision, comments=None):
    """Envoie une notification de décision à tous les auteurs."""
    if not communication.authors:
        raise ValueError("Aucun auteur à notifier")
    
    # Récupérer tous les emails des auteurs
    author_emails = [author.email for author in communication.authors if author.email]
    
    if not author_emails:
        raise ValueError("Aucun email d'auteur valide")
    
    # Textes selon la décision
    decision_texts = {
        'accepter': {
            'subject': 'Communication acceptée',
            'title': 'Félicitations ! Votre communication a été acceptée',
            'message': 'Nous avons le plaisir de vous informer que votre communication a été acceptée pour le congrès SFT 2026.',
            'color': '#28a745'
        },
        'rejeter': {
            'subject': 'Communication non retenue',
            'title': 'Communication non retenue',
            'message': 'Nous regrettons de vous informer que votre communication n\'a pas été retenue pour le congrès SFT 2026.',
            'color': '#dc3545'
        },
        'reviser': {
            'subject': 'Révisions demandées pour votre communication',
            'title': 'Révisions demandées',
            'message': 'Votre communication nécessite des révisions avant acceptation finale.',
            'color': '#ffc107'
        }
    }
    
    decision_info = decision_texts[decision]
    subject = f"SFT 2026 - {decision_info['subject']} - {communication.title}"
    
    # Corps de l'email
    body = f"""
Bonjour,

{decision_info['message']}

Titre de la communication : {communication.title}
ID : {communication.id}
Type : {communication.type.upper()}

{f"Commentaires de l'équipe scientifique :{chr(10)}{comments}" if comments else ""}

Cordialement,
L'équipe SFT 2026
"""

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
    <div style="background-color: {decision_info['color']}; color: white; padding: 20px; text-align: center;">
        <h1 style="margin: 0;">{decision_info['title']}</h1>
    </div>
    
    <div style="padding: 20px; background-color: #f8f9fa;">
        <p>{decision_info['message']}</p>
        
        <div style="background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
            <h3 style="color: #007bff; margin-top: 0;">Détails de la communication</h3>
            <p><strong>Titre :</strong> {communication.title}</p>
            <p><strong>ID :</strong> {communication.id}</p>
            <p><strong>Type :</strong> {communication.type.upper()}</p>
        </div>
        
        {comments_html}
        
        <p style="margin-top: 20px;">Cordialement,<br>L'équipe SFT 2026</p>
    </div>
</div>
"""

    # Envoyer l'email à tous les auteurs
    send_email(subject, author_emails, body, html)


def send_biot_fourier_audition_notification(communication):
    """Envoie une notification d'audition Biot-Fourier à l'auteur principal."""
    if not communication.authors:
        raise ValueError("Aucun auteur à notifier")
    
    # Récupérer l'auteur principal (premier auteur)
    main_author = communication.authors[0]
    
    if not main_author.email:
        raise ValueError("Pas d'email pour l'auteur principal")
    
    subject = f"Sélection pour l'audition Prix Biot-Fourier - SFT 2026"
    
    # Corps de l'email en texte
    body = f"""
Bonjour {main_author.full_name or main_author.email},

Félicitations !

Votre communication a été sélectionnée pour l'audition du Prix Biot-Fourier 2026.

Titre de la communication : {communication.title}
ID : {communication.id}
Type : {communication.type.upper()}

Le Prix Biot-Fourier récompense chaque année la meilleure communication présentée par un jeune chercheur (moins de 35 ans) lors du Congrès de la SFT.

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

Cordialement,
Le comité scientifique SFT 2026
"""

    # Version HTML
    html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: linear-gradient(135deg, #ffc107, #ff8c00); color: white; padding: 30px; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">🏆 Félicitations !</h1>
        <h2 style="margin: 10px 0 0 0; font-weight: normal;">Sélection Prix Biot-Fourier</h2>
    </div>
    
    <div style="padding: 30px; background-color: #f8f9fa;">
        <p style="font-size: 18px; color: #28a745; font-weight: bold;">
            Votre communication a été sélectionnée pour l'audition du Prix Biot-Fourier 2026 !
        </p>
        
        <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
            <h3 style="color: #007bff; margin-top: 0;">Votre communication sélectionnée</h3>
            <p><strong>Titre :</strong> {communication.title}</p>
            <p><strong>ID :</strong> {communication.id}</p>
            <p><strong>Type :</strong> {communication.type.upper()}</p>
            <p><strong>Auteur principal :</strong> {main_author.full_name or main_author.email}</p>
        </div>
        
        <div style="background-color: #e7f3ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #004085; margin-top: 0;">À propos du Prix Biot-Fourier</h3>
            <p>Le Prix Biot-Fourier récompense chaque année la meilleure communication présentée par un <strong>jeune chercheur (moins de 35 ans)</strong> lors du Congrès de la SFT.</p>
        </div>
        
        <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #ffeaa7;">
            <h3 style="color: #856404; margin-top: 0;">📋 Prochaines étapes</h3>
            <ul style="margin-bottom: 0;">
                <li>Présentation devant le jury pendant le congrès</li>
                <li><strong>Durée :</strong> 15 minutes + 10 minutes de questions</li>
                <li><strong>Date et lieu :</strong> à confirmer</li>
                <li>Seul l'auteur principal peut concourir</li>
            </ul>
        </div>
        
        <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #f5c6cb;">
            <h3 style="color: #721c24; margin-top: 0;">⚠️ Conditions importantes</h3>
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
            <strong>🎉 Encore toutes nos félicitations pour cette sélection ! 🎉</strong>
        </div>
        
        <p style="margin-top: 30px;">Cordialement,<br><strong>Le comité scientifique SFT 2026</strong></p>
    </div>
</div>
"""

    # Envoyer uniquement à l'auteur principal
    send_email(subject, [main_author.email], body, html)



# À ajouter dans utils.py

def send_review_decline_notification(assignment, decline_reason, other_reason=None):
    """Envoie une notification aux admins quand une review est refusée."""
    from flask import url_for, current_app
    from .models import User
    
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
    
    # URL pour réassigner
    reassign_url = url_for('admin.suggest_reviewers', comm_id=communication.id, _external=True)
    
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

---
Système de gestion SFT 2026
"""

    # Corps de l'email en HTML
    html = f"""
<h2 style="color: #dc3545;">🚨 Review refusée - Action requise</h2>

<p>Une review a été refusée par un reviewer et nécessite une <strong>réassignation immédiate</strong>.</p>

<div style="border: 1px solid #dc3545; border-radius: 5px; padding: 15px; margin: 20px 0; background-color: #f8d7da;">
    <h3 style="color: #721c24; margin-top: 0;">📄 Communication concernée</h3>
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
    <h3 style="color: #856404; margin-top: 0;">👤 Reviewer qui a refusé</h3>
    <ul>
        <li><strong>Nom :</strong> {reviewer.full_name or reviewer.email}</li>
        <li><strong>Email :</strong> {reviewer.email}</li>
        <li><strong>Spécialités :</strong> {reviewer.specialites_codes or 'Non spécifiées'}</li>
    </ul>
</div>

<div style="border: 1px solid #17a2b8; border-radius: 5px; padding: 15px; margin: 20px 0; background-color: #d1ecf1;">
    <h3 style="color: #0c5460; margin-top: 0;">❌ Détails du refus</h3>
    <ul>
        <li><strong>Date :</strong> {assignment.declined_at.strftime('%d/%m/%Y à %H:%M') if hasattr(assignment, 'declined_at') and assignment.declined_at else 'Non définie'}</li>
        <li><strong>Raison :</strong> {reason_text}</li>
    </ul>
</div>

<div style="text-align: center; margin: 30px 0;">
    <a href="{reassign_url}" style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
        🔄 Réassigner cette review
    </a>
</div>

<div style="text-align: center; margin: 20px 0;">
    <a href="{url_for('admin.admin_dashboard', _external=True)}" style="background-color: #6c757d; color: white; padding: 8px 20px; text-decoration: none; border-radius: 3px;">
        📊 Dashboard admin
    </a>
</div>

<hr>
<p style="color: #666; font-size: 12px; text-align: center;">
    Système de gestion SFT 2026<br>
    Notification automatique - Ne pas répondre à cet email
</p>
"""

    # Envoyer l'email
    try:
        send_email(subject, admin_emails, body, html)
        current_app.logger.info(f"Notification de refus de review envoyée aux admins pour la communication {communication.id}")
    except Exception as e:
        current_app.logger.error(f"Erreur envoi notification refus review: {e}")
        raise e


# À ajouter dans emails.py

def send_grouped_review_notifications():
    """Envoie un email groupé à chaque reviewer avec toutes ses reviews assignées."""
    from flask import url_for, current_app
    from .models import User, ReviewAssignment
    
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
    from flask import url_for
    from datetime import datetime
    
    subject = f"SFT 2026 - {len(assignments)} review(s) à effectuer"
    
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
            <h4 style="color: #007bff; margin-top: 0;">📄 Review #{i}</h4>
            <p><strong>Titre :</strong> {communication.title}</p>
            <p><strong>Auteurs :</strong> {authors_list}</p>
            <p><strong>Type :</strong> {communication.type.title()}</p>
            <p><strong>Thématiques :</strong> {communication.thematiques_codes or 'Non spécifiées'}</p>
            <p><strong>Échéance :</strong> {due_date_str}</p>
            
            <div style="margin-top: 15px;">
                <a href="{review_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-right: 10px;">
                    📝 Faire la review
                </a>
                <a href="{decline_url}" style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    ❌ Refuser cette review
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

Vous avez été assigné(e) à {len(assignments)} review(s) pour le congrès SFT 2026.

{reviews_text}

Dashboard reviewer: {url_for('main.reviewer_dashboard', _external=True)}

Important:
- Consultez chaque communication attentivement
- Respectez les échéances indiquées
- En cas d'impossibilité, utilisez le lien "Refuser cette review"
- Pour toute question, contactez l'équipe organisatrice

Cordialement,
L'équipe SFT 2026
"""

    # Corps de l'email en HTML
    html = f"""
<h2 style="color: #007bff;">📋 Vos assignations de reviews SFT 2026</h2>

<p>Bonjour <strong>{reviewer.full_name or reviewer.email}</strong>,</p>

<p>Vous avez été assigné(e) à <strong>{len(assignments)} review(s)</strong> pour le congrès SFT 2026.</p>

<div style="background-color: #e7f3ff; border-left: 4px solid #007bff; padding: 15px; margin: 20px 0;">
    <h3 style="margin-top: 0; color: #0056b3;">ℹ️ Informations importantes</h3>
    <ul>
        <li>Consultez chaque communication attentivement</li>
        <li>Respectez les échéances indiquées</li>
        <li>En cas d'impossibilité, utilisez le bouton "Refuser cette review"</li>
        <li>Vos spécialités: <strong>{reviewer.specialites_codes or 'Non spécifiées'}</strong></li>
    </ul>
</div>

<h3 style="color: #28a745;">📝 Vos reviews à effectuer:</h3>

{reviews_html}

<div style="text-align: center; margin: 30px 0;">
    <a href="{url_for('main.reviewer_dashboard', _external=True)}" style="background-color: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px;">
        🏠 Accéder à mon dashboard reviewer
    </a>
</div>

<hr>
<p style="color: #666; font-size: 12px;">
    Congrès SFT 2026 - Villers-lès-Nancy<br>
    Pour toute question: contact@sft2026-nancy.fr
</p>
"""

    # Envoyer l'email
    send_email(subject, [reviewer.email], body, html)
