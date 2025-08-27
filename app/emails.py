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
from flask import current_app, url_for
import logging

logger = logging.getLogger(__name__)

def send_email(subject, recipients, body, html=None):
    """Fonction de base pour envoyer un email."""
    try:
        msg = Message(subject=subject, recipients=recipients, body=body, html=html)
        mail.send(msg)
        logger.info(f"Email envoyé à {recipients} avec sujet: {subject}")
    except Exception as e:
        logger.error(f"Erreur envoi email à {recipients}: {e}")
        raise

# ===== GESTION CENTRALISÉE DES THÉMATIQUES =====

def _convert_codes_to_names(codes_string):
    """Convertit une chaîne de codes séparés par des virgules en noms complets."""
    if not codes_string:
        return 'Non spécifiées'
    
    try:
        from app.models import ThematiqueHelper
        
        # Séparer les codes et nettoyer
        codes = [code.strip().upper() for code in codes_string.split(',') if code.strip()]
        noms = []
        
        for code in codes:
            thematique = ThematiqueHelper.get_by_code(code)
            if thematique:
                noms.append(thematique['nom'])
            else:
                noms.append(code)  # Garder le code si pas trouvé
        
        return ' - '.join(noms)
        
    except Exception as e:
        logger.warning(f"Erreur conversion codes thématiques {codes_string}: {e}")
        return codes_string or 'Non spécifiées'

def prepare_email_context(base_context, communication=None, user=None, reviewer=None):
    """Prépare le contexte email avec conversion automatique des thématiques."""
    context = base_context.copy()
    
    try:
        # Conversion des thématiques de communication
        if communication and hasattr(communication, 'thematiques'):
            context['COMMUNICATION_THEMES'] = _convert_codes_to_names(communication.thematiques)
            context['COMMUNICATION_THEMES_CODES'] = communication.thematiques or ''
        
        # Conversion des spécialités de reviewer
        if reviewer and hasattr(reviewer, 'specialites_codes'):
            context['REVIEWER_SPECIALTIES'] = _convert_codes_to_names(reviewer.specialites_codes)
            context['REVIEWER_SPECIALTIES_CODES'] = reviewer.specialites_codes or ''
        
        # Conversion des spécialités d'utilisateur
        if user and hasattr(user, 'specialites_codes'):
            context['USER_SPECIALTIES'] = _convert_codes_to_names(user.specialites_codes)
            context['USER_SPECIALTIES_CODES'] = user.specialites_codes or ''
        
        # Variables d'affiliations pour reviewer
        if reviewer:
            context['REVIEWER_AFFILIATIONS'] = getattr(reviewer, 'affiliations', 'Non spécifiées')
        
        return context
        
    except Exception as e:
        logger.warning(f"Erreur préparation contexte email: {e}")
        return context

def _build_html_email(template_name, context, color_scheme='blue'):
    """Construit le HTML d'un email en utilisant les templates configurés."""
    try:
        config_loader = current_app.config_loader
        
        # Récupérer le contenu du template
        content_config = config_loader.get_email_content(template_name)
        if not content_config:
            logger.warning(f"Template {template_name} non trouvé")
            return None
        
        # Définir les couleurs selon le schéma
        colors = {
            'blue': {'primary': '#007bff', 'secondary': '#6c757d'},
            'green': {'primary': '#28a745', 'secondary': '#20c997'},
            'orange': {'primary': '#fd7e14', 'secondary': '#e83e8c'},
            'red': {'primary': '#dc3545', 'secondary': '#6f42c1'},
            'purple': {'primary': '#6f42c1', 'secondary': '#6610f2'}
        }.get(color_scheme, {'primary': '#007bff', 'secondary': '#6c757d'})
        
        # Construire le HTML
        html_parts = []
        
        # En-tête
        if content_config.get('greeting'):
            greeting = content_config['greeting']
            html_parts.append(f"<p><strong>{greeting}</strong></p>")
        
        # Introduction colorée
        if content_config.get('intro'):
            intro = content_config['intro']
            html_parts.append(f"<h3 style='color: {colors['primary']};'>{intro}</h3>")
        
        # Corps du message
        if content_config.get('body'):
            body = content_config['body']
            body_html = body.replace('\n\n', '</p><p>').replace('\n', '<br>')
            html_parts.append(f"<p>{body_html}</p>")
        
        # Section d'informations spécialisées (communication, reviewer, etc.)
        info_section = _build_info_section(context, colors['primary'])
        if info_section:
            html_parts.append(info_section)
        
        # Bouton d'action
        if context.get('call_to_action_url'):
            button_text = content_config.get('call_to_action', 'Accéder à la plateforme')
            #button_text = config_loader.format_template(button_text, **context)
            html_parts.append(f'''
            <div style="text-align: center; margin: 30px 0;">
                <a href="{context['call_to_action_url']}" 
                   style="background-color: {colors['primary']}; color: white; padding: 12px 25px; 
                          text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                    {button_text}
                </a>
            </div>
            ''')
        
        # Signature
        signature = config_loader.get_email_signature('default', **context)
        if signature:
            signature_html = signature.replace('\n', '<br>')
            html_parts.append(f"<hr><p>{signature_html}</p>")
        
        return ''.join(html_parts)
        
    except Exception as e:
        logger.error(f"Erreur construction HTML email {template_name}: {e}")
        return None

def _build_info_section(context, primary_color):
    """Construit une section d'informations contextuelles pour l'email."""
    info_parts = []
    
    # Informations communication
    if context.get('COMMUNICATION_TITLE'):
        info_parts.append(f"<li><strong>Communication :</strong> {context['COMMUNICATION_TITLE']}</li>")
    if context.get('COMMUNICATION_ID'):
        info_parts.append(f"<li><strong>ID :</strong> {context['COMMUNICATION_ID']}</li>")
    if context.get('COMMUNICATION_THEMES'):
        info_parts.append(f"<li><strong>Thématiques :</strong> {context['COMMUNICATION_THEMES']}</li>")
    
    # Informations reviewer
    #######################################################################################################
    # if context.get('REVIEWER_SPECIALTIES'):                                                             #
    #     info_parts.append(f"<li><strong>Spécialités :</strong> {context['REVIEWER_SPECIALTIES']}</li>") #
    #######################################################################################################
    if context.get('REVIEWER_AFFILIATIONS'):
        info_parts.append(f"<li><strong>Affiliations :</strong> {context['REVIEWER_AFFILIATIONS']}</li>")
    
    # Informations utilisateur
    if context.get('USER_EMAIL'):
        info_parts.append(f"<li><strong>Email :</strong> {context['USER_EMAIL']}</li>")
    ###################################################################################################
    # if context.get('USER_SPECIALTIES'):                                                             #
    #     info_parts.append(f"<li><strong>Spécialités :</strong> {context['USER_SPECIALTIES']}</li>") #
    ###################################################################################################
    
    if info_parts:
        return f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; 
                    border-left: 4px solid {primary_color};">
            <h4 style="margin-top: 0; color: {primary_color};">Détails :</h4>
            <ul>
                {''.join(info_parts)}
            </ul>
        </div>
        """
    
    return ""

def _build_text_email(template_name, context):
    """Construit la version texte d'un email."""
    try:
        config_loader = current_app.config_loader
        
        content_config = config_loader.get_email_content(template_name)
        if not content_config:
            return None
        
        text_parts = []
        
        if content_config.get('greeting'):
            greeting = content_config['greeting']
            text_parts.append(greeting)
        
        if content_config.get('intro'):
            intro = content_config['intro'] 
            text_parts.append(f"\n\n{intro}")
        
        if content_config.get('body'):
            body = content_config['body']
            text_parts.append(f"\n\n{body}")
        
        # Informations contextuelles en texte
        if context.get('COMMUNICATION_TITLE'):
            text_parts.append(f"\n\nCommunication : {context['COMMUNICATION_TITLE']}")
        if context.get('COMMUNICATION_THEMES'):
            text_parts.append(f"Thématiques : {context['COMMUNICATION_THEMES']}")
        
        if context.get('call_to_action_url'):
            text_parts.append(f"\n\nAccéder à la plateforme : {context['call_to_action_url']}")
        
        signature = config_loader.get_email_signature('default', **context)
        if signature:
            text_parts.append(f"\n\n{signature}")
        
        return ''.join(text_parts)
        
    except Exception as e:
        logger.error(f"Erreur construction texte email {template_name}: {e}")
        return None

# ===== FONCTION GÉNÉRIQUE POUR ENVOYER DES EMAILS =====

def send_any_email_with_themes(template_name, recipient_email, base_context, 
                               communication=None, user=None, reviewer=None, color_scheme='blue'):
    """Fonction générique pour envoyer un email avec gestion automatique des thématiques."""
    try:
        config_loader = current_app.config_loader
        
        # Préparer le contexte avec conversion des thématiques
        context = prepare_email_context(base_context, communication, user, reviewer)
        
        # Récupérer le sujet
        subject = config_loader.get_email_subject(template_name, **context)
        if not subject:
            logger.error(f"Sujet non trouvé pour template {template_name}")
            return
        
        # Construire le contenu
        html_body = _build_html_email(template_name, context, color_scheme)
        text_body = _build_text_email(template_name, context)
        
        if not text_body:
            logger.error(f"Impossible de construire l'email {template_name}")
            return
        
        # Envoyer l'email
        send_email(subject, [recipient_email], text_body, html_body)
        logger.info(f"Email {template_name} envoyé à {recipient_email}")
        
    except Exception as e:
        logger.error(f"Erreur envoi email générique {template_name} à {recipient_email}: {e}")
        raise

# ===== FONCTIONS SPÉCIALISÉES =====

def send_submission_confirmation_email(user, communication, submission_type='résumé'):
    """Envoie un email de confirmation après le dépôt d'un fichier."""
    try:
        # Mapper les types vers les templates
        template_mapping = {
            'résumé': 'resume_submission_confirmed',
            'article': 'article_submission_confirmed', 
            'wip': 'wip_submission_confirmed',
            'poster': 'poster_submission_confirmed',
            'revision': 'revision_confirmed'
        }
        
        template_name = template_mapping.get(submission_type.lower(), 'submission_confirmed')
        
        # Mapper les types vers les couleurs
        color_mapping = {
            'résumé': 'blue',
            'article': 'green', 
            'wip': 'orange',
            'poster': 'purple',
            'revision': 'red'
        }
        
        color_scheme = color_mapping.get(submission_type.lower(), 'blue')
        
        # Préparer le contexte de base
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'COMMUNICATION_TYPE': submission_type.title(),
            'SUBMISSION_TYPE': submission_type.upper(),
            'SUBMISSION_DATE': communication.last_modified.strftime('%d/%m/%Y à %H:%M') if communication.last_modified else 'Date inconnue',
            'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True)
        }
        
        # Envoyer l'email avec gestion automatique des thématiques
        send_any_email_with_themes(
            template_name=template_name,
            recipient_email=user.email,
            base_context=base_context,
            communication=communication,
            user=user,
            color_scheme=color_scheme
        )
        
        logger.info(f"Email de confirmation {submission_type} envoyé à {user.email} pour communication {communication.id}")
        
    except Exception as e:
        logger.error(f"Erreur envoi confirmation {submission_type} à {user.email}: {e}")
        # Ne pas faire échouer la soumission à cause d'un problème d'email
        pass

def send_activation_email_to_user(user, token):
    """Envoie l'email d'activation à un reviewer."""
    try:
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'ACTIVATION_TOKEN': token,
            'call_to_action_url': url_for('main.activate_account', token=token, _external=True)
        }
        
        send_any_email_with_themes(
            template_name='activation',
            recipient_email=user.email,
            base_context=base_context,
            user=user,
            color_scheme='blue'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi activation à {user.email}: {e}")
        raise

def send_coauthor_notification_email(user, communication, token):
    """Envoie un email de notification à un nouveau co-auteur."""
    try:
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'MAIN_AUTHOR': communication.user.full_name or communication.user.email,
            'ACTIVATION_TOKEN': token if token else '',
            'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True) if not token else url_for('main.activate_account', token=token, _external=True)
        }
        
        template_name = 'coauthor_notification' if not token else 'coauthor_invitation'
        
        send_any_email_with_themes(
            template_name=template_name,
            recipient_email=user.email,
            base_context=base_context,
            communication=communication,
            user=user,
            color_scheme='green'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi notification co-auteur à {user.email}: {e}")
        raise

def send_review_reminder_email(reviewer, assignments):
    """Envoie un email de rappel à un reviewer avec ses reviews en attente."""
    try:
        # Compter les reviews en attente et en retard
        total_assignments = len(assignments)
        overdue_count = sum(1 for assignment in assignments if hasattr(assignment, 'is_overdue') and assignment.is_overdue)
        
        # Construire la liste des communications
        comm_list = []
        for assignment in assignments:
            comm = assignment.communication
            status = "⚠️ En retard" if (hasattr(assignment, 'is_overdue') and assignment.is_overdue) else "En attente"
            comm_list.append(f"• {comm.title} (ID: {comm.id}) - {status}")
        
        base_context = {
            'REVIEWER_NAME': reviewer.full_name or reviewer.email,
            'USER_FIRST_NAME': reviewer.first_name or reviewer.email.split('@')[0],
            'PENDING_REVIEWS_COUNT': total_assignments,
            'OVERDUE_COUNT': overdue_count,
            'OVERDUE_MESSAGE': f"⚠️ {overdue_count} review(s) sont en retard." if overdue_count > 0 else "",
            'COMMUNICATIONS_LIST': '\n'.join(comm_list),
            'call_to_action_url': url_for('main.reviewer_dashboard', _external=True)
        }
        
        send_any_email_with_themes(
            template_name='review_reminder',
            recipient_email=reviewer.email,
            base_context=base_context,
            user=reviewer,
            reviewer=reviewer,
            color_scheme='orange'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi rappel review à {reviewer.email}: {e}")
        raise

def send_decision_email(communication, decision_type, additional_info=""):
    """Envoie un email de décision à l'auteur principal d'une communication."""
    try:
        # Mapper les types de décision vers les templates
        decision_templates = {
            'accept': 'decision_accept',
            'reject': 'decision_reject', 
            'revise': 'decision_revise'
        }
        
        # Couleurs par type de décision
        decision_colors = {
            'accept': 'green',
            'reject': 'red',
            'revise': 'orange'
        }
        
        template_name = decision_templates.get(decision_type, 'decision_notification')
        color_scheme = decision_colors.get(decision_type, 'blue')
        
        user = communication.user
        
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'USER_LAST_NAME': user.last_name or '',
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'DECISION_TYPE': decision_type.upper(),
            'DECISION_INFO': additional_info,
            'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True)
        }
        
        send_any_email_with_themes(
            template_name=template_name,
            recipient_email=user.email,
            base_context=base_context,
            communication=communication,
            user=user,
            color_scheme=color_scheme
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi décision {decision_type} pour communication {communication.id}: {e}")
        raise

def send_biot_fourier_audition_notification(user, communication):
    """Envoie une notification pour une audition Biot-Fourier."""
    try:
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True)
        }
        
        send_any_email_with_themes(
            template_name='biot_fourier_nomination',
            recipient_email=user.email,
            base_context=base_context,
            communication=communication,
            user=user,
            color_scheme='purple'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi notification Biot-Fourier à {user.email}: {e}")
        raise

def send_qr_code_reminder_email(user, communication, qr_code_url):
    """Envoie un email avec le QR code d'un poster."""
    try:
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'QR_CODE_URL': qr_code_url,
            'call_to_action_url': qr_code_url
        }
        
        send_any_email_with_themes(
            template_name='qr_code_ready',
            recipient_email=user.email,
            base_context=base_context,
            communication=communication,
            user=user,
            color_scheme='blue'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi QR code à {user.email}: {e}")
        raise

def send_hal_collection_request(admin_email, communications_count):
    """Envoie une demande de création de collection HAL."""
    try:

        
        from flask import current_app

        base_context = {
            'ADMIN_EMAIL': admin_email,
            'COMMUNICATIONS_COUNT': communications_count,
            'CONFERENCE_NAME': current_app.conference_config.get('name', 'Conference Flow'),
            'CONFERENCE_SHORT_NAME': current_app.conference_config.get('short_name', 'CF'),
            'CONFERENCE_DATES': current_app.conference_config.get('dates', '2026'),
            'call_to_action_url': url_for('admin.admin_dashboard', _external=True)
        }
        
        send_any_email_with_themes(
            template_name='hal_collection_request',
            recipient_email=admin_email,
            base_context=base_context,
            color_scheme='blue'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi demande collection HAL: {e}")
        raise

def send_reviewer_welcome_email(reviewer):
    """Envoie un email de bienvenue à un nouveau reviewer."""
    try:
        base_context = {
            'USER_FIRST_NAME': reviewer.first_name or reviewer.email.split('@')[0],
            'USER_EMAIL': reviewer.email,
            'call_to_action_url': url_for('reviewer.dashboard', _external=True)
        }
        
        send_any_email_with_themes(
            template_name='reviewer_welcome',
            recipient_email=reviewer.email,
            base_context=base_context,
            user=reviewer,
            reviewer=reviewer,
            color_scheme='green'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi bienvenue reviewer à {reviewer.email}: {e}")
        raise

def send_admin_weekly_summary(admin_email, stats):
    """Envoie un résumé hebdomadaire aux administrateurs."""
    try:
        base_context = {
            'ADMIN_EMAIL': admin_email,
            'STATS_SUBMISSIONS': stats.get('submissions', 0),
            'STATS_REVIEWS': stats.get('reviews', 0),
            'STATS_PENDING': stats.get('pending_reviews', 0),
            'STATS_OVERDUE': stats.get('overdue_reviews', 0),
            'call_to_action_url': url_for('admin.admin_dashboard', _external=True)
        }
        
        send_any_email_with_themes(
            template_name='admin_weekly_summary',
            recipient_email=admin_email,
            base_context=base_context,
            color_scheme='blue'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi résumé hebdomadaire: {e}")
        raise

def send_admin_alert_email(admin_email, alert_type, alert_message):
    """Envoie une alerte aux administrateurs."""
    try:
        base_context = {
            'ADMIN_EMAIL': admin_email,
            'ALERT_TYPE': alert_type.upper(),
            'ALERT_MESSAGE': alert_message,
            'call_to_action_url': url_for('admin.admin_dashboard', _external=True)
        }
        
        send_any_email_with_themes(
            template_name='admin_alert',
            recipient_email=admin_email,
            base_context=base_context,
            color_scheme='red'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi alerte admin: {e}")
        raise


def send_existing_coauthor_notification_email(user, communication):
    """Envoie un email de notification à un co-auteur existant (déjà activé)."""
    try:
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'MAIN_AUTHOR': communication.user.full_name or communication.user.email,
            'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True)
        }
        
        # Utiliser le template de notification (sans token d'activation)
        send_any_email_with_themes(
            template_name='coauthor_notification',
            recipient_email=user.email,
            base_context=base_context,
            communication=communication,
            user=user,
            color_scheme='green'
        )
        
        logger.info(f"Notification co-auteur existant envoyée à {user.email} pour communication {communication.id}")
        
    except Exception as e:
        logger.error(f"Erreur notification co-auteur existant à {user.email}: {e}")
        raise

def send_reviewer_assignment_email(reviewer, communication, assignment):
    """Envoie un email de notification d'assignation à un reviewer."""
    try:
        # Utiliser le template reviewer_assignment qui existe déjà
        base_context = {
            'REVIEWER_NAME': reviewer.full_name or reviewer.email,
            'USER_FIRST_NAME': reviewer.first_name or reviewer.email.split('@')[0],
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'call_to_action_url': url_for('main.reviewer_dashboard', _external=True)
        }
        
        # Ne passer que les paramètres acceptés par send_any_email_with_themes
        send_any_email_with_themes(
            template_name='reviewer_assignment',
            recipient_email=reviewer.email,
            base_context=base_context,
            communication=communication,
            user=reviewer,
            reviewer=reviewer,
            color_scheme='blue'
        )
        
        logger.info(f"Email d'assignation envoyé à {reviewer.email} pour communication {communication.id}")
        
    except Exception as e:
        logger.error(f"Erreur envoi email assignation reviewer {reviewer.email}: {e}")
        raise

