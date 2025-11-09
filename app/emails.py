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
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def send_email(subject, recipients, body, html=None):
    """Fonction de base pour envoyer un email."""
    try:
        msg = Message(
            subject=subject, 
            recipients=recipients, 
            body=body, 
            html=html,
            reply_to=current_app.config.get('MAIL_REPLY_TO')
        )
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
        if communication:
            if hasattr(communication, 'thematiques_codes') and communication.thematiques_codes:
                # Cas 1: codes stockés en string (ex: "COND,MULTI")
                context['COMMUNICATION_THEMES'] = _convert_codes_to_names(communication.thematiques_codes)
                context['COMMUNICATION_THEMES_CODES'] = communication.thematiques_codes
            elif hasattr(communication, 'thematiques') and communication.thematiques:
                # Cas 2: objets thématiques (ex: liste d'objets)
                if isinstance(communication.thematiques, list):
                    # Liste d'objets thématiques
                    theme_names = []
                    theme_codes = []
                    for theme in communication.thematiques:
                        if isinstance(theme, dict):
                            theme_names.append(theme.get('nom', theme.get('code', 'Inconnu')))
                            theme_codes.append(theme.get('code', ''))
                        else:
                            # Objet avec attributs
                            theme_names.append(getattr(theme, 'nom', getattr(theme, 'code', 'Inconnu')))
                            theme_codes.append(getattr(theme, 'code', ''))
                    
                    context['COMMUNICATION_THEMES'] = ' • '.join(theme_names)
                    context['COMMUNICATION_THEMES_CODES'] = ','.join(theme_codes)
                else:
                    # String brute - utiliser la fonction de conversion
                    context['COMMUNICATION_THEMES'] = _convert_codes_to_names(str(communication.thematiques))
                    context['COMMUNICATION_THEMES_CODES'] = str(communication.thematiques)
            else:
                context['COMMUNICATION_THEMES'] = 'Non spécifiées'
                context['COMMUNICATION_THEMES_CODES'] = ''
        
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
        # En cas d'erreur, au moins retourner le contexte de base
        context['COMMUNICATION_THEMES'] = 'Non spécifiées'
        context['COMMUNICATION_THEMES_CODES'] = ''
        return context


def send_reviewer_welcome_email(user, token):
    """Envoie l'email de bienvenue à un reviewer."""
    try:
        from datetime import datetime, timedelta
        
        # Dates par défaut pour l'information
        assignment_date = (datetime.utcnow() + timedelta(days=7)).strftime('%d/%m/%Y')
        review_deadline = (datetime.utcnow() + timedelta(days=30)).strftime('%d/%m/%Y')
        
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'REVIEWER_NAME': user.full_name or f"{user.first_name} {user.last_name}".strip() or user.email.split('@')[0],
            'REVIEWER_SPECIALTIES': getattr(user, 'specialites_codes', 'Non spécifiées'),
            'REVIEWER_AFFILIATIONS': 'Non spécifiées',  # À adapter selon votre modèle
            'ACTIVATION_TOKEN': token,
            'ASSIGNMENT_DATE': assignment_date,  # ← LIGNE AJOUTÉE
            'REVIEW_DEADLINE': review_deadline,  # ← LIGNE AJOUTÉE
            'call_to_action_url': url_for('main.activate_account', token=token, _external=True)
        }
        
        send_any_email_with_themes(
            template_name='reviewer_welcome',  # Template spécifique reviewers
            recipient_email=user.email,
            base_context=base_context,
            user=user,
            color_scheme='blue'
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi bienvenue reviewer à {user.email}: {e}")
        raise

    
def _build_info_section_with_icons(context, primary_color):
    """Construit une section d'informations contextuelles avec émojis universels."""
    info_parts = []
    
    # Informations communication avec émojis
    if context.get('COMMUNICATION_TITLE'):
        info_parts.append(f'<li><strong>Communication :</strong> {context["COMMUNICATION_TITLE"]}</li>')
    if context.get('COMMUNICATION_ID'):
        info_parts.append(f'<li><strong>ID :</strong> {context["COMMUNICATION_ID"]}</li>')
    if context.get('COMMUNICATION_THEMES'):
        info_parts.append(f'<li><strong>Thématiques :</strong> <span class="themes">{context["COMMUNICATION_THEMES"]}</span></li>')
    
    # Informations reviewer avec émojis
    if context.get('REVIEWER_AFFILIATIONS'):
        info_parts.append(f'<li><strong>Affiliations :</strong> {context["REVIEWER_AFFILIATIONS"]}</li>')
    
    # Informations utilisateur avec émojis
    if context.get('USER_EMAIL'):
        info_parts.append(f'<li><strong>Email :</strong> {context["USER_EMAIL"]}</li>')
    
    # Informations de fichier (si présentes)
    if context.get('FILE_VERSION'):
        info_parts.append(f'<li><strong>Version :</strong> {context["FILE_VERSION"]}</li>')
    
    if context.get('SUBMISSION_DATE'):
        info_parts.append(f'<li><strong>Date :</strong> {context["SUBMISSION_DATE"]}</li>')
    
    if info_parts:
        return f'''
        <div class="info-box">
            <h4 style="margin-top: 0; color: {primary_color};">Détails :</h4>
            <ul style="list-style: none; padding-left: 0;">
                {''.join(info_parts)}
            </ul>
        </div>
        '''
    
    return ""


def _build_html_email(template_name, context, color_scheme='blue'):
    """Construit le HTML d'un email en utilisant les templates configurés."""
    try:
        config_loader = current_app.config_loader
        
        content_config = config_loader.get_email_content(template_name, **context)
        if not content_config:
            logger.warning(f"Template {template_name} non trouvé")
            return None
        
        colors = {
            'blue': {'primary': '#007bff', 'secondary': '#6c757d'},
            'green': {'primary': '#28a745', 'secondary': '#20c997'},
            'orange': {'primary': '#fd7e14', 'secondary': '#e83e8c'},
            'red': {'primary': '#dc3545', 'secondary': '#6f42c1'},
            'purple': {'primary': '#6f42c1', 'secondary': '#6610f2'}
        }.get(color_scheme, {'primary': '#007bff', 'secondary': '#6c757d'})
        
        html_parts = []
        
        # En-tête avec styles CSS uniquement
        html_parts.append(f'''
        <style>
            .email-container {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }}
        </style>
        <div class="email-container">
        ''')
        
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
        
        # Bouton d'action avec émoji
        if context.get('call_to_action_url'):
            button_text = content_config.get('call_to_action', 'Accéder à la plateforme')
            button_text = config_loader._replace_variables(button_text, context)
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
        
        html_parts.append('</div>')
        
        return ''.join(html_parts)
        
    except Exception as e:
        logger.error(f"Erreur construction HTML email {template_name}: {e}")
        return None


def _build_text_email(template_name, context):
    """Construit la version texte d'un email."""
    try:
        config_loader = current_app.config_loader
        
        content_config = config_loader.get_email_content(template_name, **context)
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
        
        if context.get('call_to_action_url'):
            button_text = content_config.get('call_to_action', 'Accéder à la plateforme')
            button_text = config_loader._replace_variables(button_text, context)
            text_parts.append(f"\n\n{button_text} : {context['call_to_action_url']}")
        
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

# Dans app/emails.py
# Remplacer la fonction send_submission_confirmation_email existante :

def send_submission_confirmation_email(communication, submission_type='résumé', submission_file=None):
    """Envoie un email de confirmation après le dépôt d'un fichier."""
    try:
        main_author = communication.corresponding_author
        if not main_author:
            logger.error(f"Aucun auteur trouvé pour la communication {communication.id}")
            return
        
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
        
        from datetime import datetime
        submission_date = datetime.utcnow().strftime('%d/%m/%Y à %H:%M')
        if hasattr(communication, 'updated_at') and communication.updated_at:
            submission_date = communication.updated_at.strftime('%d/%m/%Y à %H:%M')
        
        file_version = "1"
        if submission_file and hasattr(submission_file, 'version'):
            file_version = str(submission_file.version)
        
        # Préparer le contexte de base
        base_context = {
            'USER_FIRST_NAME': main_author.first_name or main_author.email.split('@')[0],
            'USER_LAST_NAME': main_author.last_name or '',
            'USER_EMAIL': main_author.email,
            'AUTHOR_NAME': main_author.full_name or main_author.email,  # Variable supplémentaire pour les templates
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'COMMUNICATION_TYPE': submission_type.title(),
            'SUBMISSION_TYPE': submission_type.upper(),
            'SUBMISSION_DATE': submission_date,
            'FILE_VERSION': file_version,
            'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True)
        }
        
        # Envoyer l'email avec gestion automatique des thématiques
        send_any_email_with_themes(
            template_name=template_name,
            recipient_email=main_author.email,
            base_context=base_context,
            communication=communication,
            user=main_author,
            color_scheme=color_scheme
        )
        
        logger.info(f"Email de confirmation {submission_type} envoyé à {main_author.email} pour communication {communication.id}")
        
    except Exception as e:
        logger.error(f"Erreur envoi confirmation {submission_type} pour communication {communication.id}: {e}")
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
        main_author = communication.authors[0] if communication.authors else None
        if main_author:
            main_author_name = main_author.full_name if main_author.full_name else main_author.email
        else:
            main_author_name = "Auteur inconnu"
        
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'AUTHOR_NAME': user.full_name or user.email,
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'COMMUNICATION_TYPE': communication.type.title() if communication.type else 'Communication',
            'MAIN_AUTHOR_NAME': main_author_name,
            'MAIN_AUTHOR_EMAIL': main_author.email if main_author else '',  # ← CETTE LIGNE MANQUE
            'INVITATION_DEADLINE': (datetime.utcnow() + timedelta(days=14)).strftime('%d/%m/%Y'),  # ← CETTE LIGNE MANQUE
            'ACTIVATION_TOKEN': token if token else '',
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
        
        logger.info(f"Email co-auteur envoyé à {user.email} pour communication {communication.id}")
        
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
            status = "En retard" if (hasattr(assignment, 'is_overdue') and assignment.is_overdue) else "En attente"
            comm_list.append(f"• {comm.title} (ID: {comm.id}) - {status}")
        
        base_context = {
            'REVIEWER_NAME': reviewer.full_name or reviewer.email,
            'USER_FIRST_NAME': reviewer.first_name or reviewer.email.split('@')[0],
            'PENDING_REVIEWS_COUNT': total_assignments,
            'OVERDUE_COUNT': overdue_count,
            'OVERDUE_MESSAGE': f"{overdue_count} review(s) sont en retard." if overdue_count > 0 else "",
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
def send_decision_email(communication, decision_type, additional_info=''):
    """Envoie un email de notification de décision à l'auteur principal."""
    try:
        main_author = communication.authors[0] if communication.authors else None
        if not main_author:
            logger.error(f"Aucun auteur trouvé pour la communication {communication.id}")
            return
        
        # Mapper les types de décision vers les templates
        decision_templates = {
            'accept': 'decision_accept',
            'accepter': 'decision_accept',  # Support des deux formats
            'reject': 'decision_reject', 
            'rejeter': 'decision_reject',  # Support des deux formats
            'revise': 'decision_revise',
            'reviser': 'decision_revise'  # Support des deux formats
        }
        
        # Couleurs par type de décision
        decision_colors = {
            'accept': 'green',
            'accepter': 'green',
            'reject': 'red',
            'rejeter': 'red',
            'revise': 'orange',
            'reviser': 'orange'
        }
        
        template_name = decision_templates.get(decision_type.lower(), 'decision_notification')
        color_scheme = decision_colors.get(decision_type.lower(), 'blue')
        
        base_context = {
            'USER_FIRST_NAME': main_author.first_name or main_author.email.split('@')[0],
            'USER_LAST_NAME': main_author.last_name or '',
            'AUTHOR_NAME': main_author.full_name or main_author.email,
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'DECISION_TYPE': decision_type.upper(),
            'DECISION_INFO': additional_info,
            'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True)
        }
        
        send_any_email_with_themes(
            template_name=template_name,
            recipient_email=main_author.email,
            base_context=base_context,
            communication=communication,
            user=main_author,
            color_scheme=color_scheme
        )
        
        logger.info(f"Email de décision {decision_type} envoyé à {main_author.email} pour communication {communication.id}")
        
    except Exception as e:
        logger.error(f"Erreur envoi décision {decision_type} pour communication {communication.id}: {e}")
        raise

def send_biot_fourier_audition_notification(communication):
    """Envoie une notification pour une audition Biot-Fourier."""
    try:
        main_author = communication.authors[0] if communication.authors else None
        if not main_author:
            logger.error(f"Aucun auteur trouvé pour la communication {communication.id}")
            return
        
        base_context = {
            'USER_FIRST_NAME': main_author.first_name or main_author.email.split('@')[0],
            'AUTHOR_NAME': main_author.full_name or main_author.email,
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'COMMUNICATION_TYPE': communication.type.title() if communication.type else 'Communication',
            'call_to_action_url': url_for('main.update_submission', comm_id=communication.id, _external=True)
        }
        
        send_any_email_with_themes(
            template_name='biot_fourier_nomination',
            recipient_email=main_author.email,
            base_context=base_context,
            communication=communication,
            user=main_author,
            color_scheme='purple'
        )
        
        logger.info(f"Email Biot-Fourier envoyé à {main_author.email} pour communication {communication.id}")
        
    except Exception as e:
        logger.error(f"Erreur envoi notification Biot-Fourier pour communication {communication.id}: {e}")
        raise


def send_qr_code_reminder_email(user, communication, qr_code_url):
    """Envoie un email avec le QR code d'un poster."""
    try:
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'AUTHOR_NAME': user.full_name or user.email,
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

#######################################################################################
# def send_reviewer_welcome_email(reviewer):                                          #
#     """Envoie un email de bienvenue à un nouveau reviewer."""                       #
#     try:                                                                            #
#         base_context = {                                                            #
#             'USER_FIRST_NAME': reviewer.first_name or reviewer.email.split('@')[0], #
#             'AUTHOR_NAME': user.full_name or user.email,                            #
#             'USER_EMAIL': reviewer.email,                                           #
#             'call_to_action_url': url_for('reviewer.dashboard', _external=True)     #
#         }                                                                           #
#                                                                                     #
#         send_any_email_with_themes(                                                 #
#             template_name='reviewer_welcome',                                       #
#             recipient_email=reviewer.email,                                         #
#             base_context=base_context,                                              #
#             user=reviewer,                                                          #
#             reviewer=reviewer,                                                      #
#             color_scheme='green'                                                    #
#         )                                                                           #
#                                                                                     #
#     except Exception as e:                                                          #
#         logger.error(f"Erreur envoi bienvenue reviewer à {reviewer.email}: {e}")    #
#         raise                                                                       #
#######################################################################################

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

def send_reviewer_assignment_email(reviewer, communication, assignment=None):
    """Envoie un email de notification d'assignation à un reviewer."""
    try:
        # Utiliser le template review_assigned qui existe déjà
        base_context = {
            'REVIEWER_NAME': reviewer.full_name or reviewer.email,
            'USER_FIRST_NAME': reviewer.first_name or reviewer.email.split('@')[0],
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_ID': communication.id,
            'COMMUNICATION_TYPE': communication.type.title(),
            'call_to_action_url': url_for('main.reviewer_dashboard', _external=True)
        }
        
        # Ajouter les infos de l'assignation si disponible
        if assignment:
            if assignment.due_date:
                base_context['REVIEW_DEADLINE'] = assignment.due_date.strftime('%d/%m/%Y')
            base_context['ASSIGNMENT_ID'] = assignment.id
        
        # Utiliser le template review_assigned qui existe dans emails.yml
        send_any_email_with_themes(
            template_name='review_assigned',
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
        main_author = communication.authors[0] if communication.authors else None
        if main_author:
            main_author_name = main_author.full_name if main_author.full_name else main_author.email
        else:
            main_author_name = "Auteur inconnu"
        
        base_context = {
            'USER_FIRST_NAME': user.first_name or user.email.split('@')[0],
            'AUTHOR_NAME': user.full_name or user.email,
            'USER_LAST_NAME': user.last_name or '',
            'USER_EMAIL': user.email,
            'COMMUNICATION_TITLE': communication.title,
            'COMMUNICATION_TYPE': communication.type.title() if communication.type else 'Communication',
            'COMMUNICATION_ID': communication.id,
            'MAIN_AUTHOR_NAME': main_author_name,  
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

def get_admin_email_templates():
    """Retourne les templates d'emails pour l'interface admin depuis emails.yml"""
    try:
        from flask import current_app
        config_loader = current_app.config_loader
        return config_loader.get_admin_email_templates()
    except Exception as e:
        current_app.logger.error(f"Erreur récupération templates admin: {e}")
        return {}



def send_grouped_review_notifications():
    """
    Envoie des notifications groupées aux reviewers pour leurs assignations en attente.
    Chaque reviewer reçoit UN email avec toutes ses reviews à effectuer.
    """
    from app.models import ReviewAssignment, User
    from flask import current_app
    from datetime import datetime
    
    try:
        # Récupérer les assignations en attente (pas encore notifiées)
        pending_assignments = ReviewAssignment.query.filter_by(
            status='assigned',
            notification_sent_at=None
        ).all()
        
        if not pending_assignments:
            return {
                'sent': 0,
                'total_assignments': 0,
                'errors': [],
                'message': 'Aucune assignation en attente'
            }
        
        # Grouper par reviewer
        reviewers_assignments = {}
        for assignment in pending_assignments:
            reviewer_id = assignment.reviewer_id
            if reviewer_id not in reviewers_assignments:
                reviewers_assignments[reviewer_id] = []
            reviewers_assignments[reviewer_id].append(assignment)
        
        sent_count = 0
        errors = []
        total_assignments = len(pending_assignments)
        
        # Envoyer un email groupé à chaque reviewer
        for reviewer_id, assignments in reviewers_assignments.items():
            try:
                reviewer = User.query.get(reviewer_id)
                if not reviewer or not reviewer.email:
                    errors.append(f"Reviewer {reviewer_id}: email introuvable")
                    continue
                
                # Préparer le contexte pour l'email groupé
                base_context = {
                    'REVIEWER_NAME': reviewer.full_name or reviewer.email,
                    'USER_FIRST_NAME': reviewer.first_name or reviewer.email.split('@')[0],
                    'REVIEWS_COUNT': len(assignments),
                    'REVIEWER_SPECIALTIES': reviewer.specialites_codes or 'Non spécifiées',
                    'call_to_action_url': url_for('main.reviewer_dashboard', _external=True)
                }
                
                # Envoyer l'email avec le template review_assigned pour les notifications groupées
                send_any_email_with_themes(
                    template_name='review_assigned',
                    recipient_email=reviewer.email,
                    base_context=base_context,
                    user=reviewer,
                    reviewer=reviewer,
                    color_scheme='blue'
                )
                
                # Marquer toutes les assignations de ce reviewer comme notifiées
                for assignment in assignments:
                    assignment.notification_sent_at = datetime.utcnow()
                
                sent_count += 1
                current_app.logger.info(f"Notification groupée envoyée à {reviewer.email} pour {len(assignments)} review(s)")
                
            except Exception as e:
                error_msg = f"Reviewer {reviewer.email if reviewer else reviewer_id}: {str(e)}"
                errors.append(error_msg)
                current_app.logger.error(f"Erreur notification groupée: {error_msg}")
        
        return {
            'sent': sent_count,
            'total_assignments': total_assignments,
            'errors': errors,
            'message': f'{sent_count} notification(s) envoyée(s) pour {total_assignments} assignation(s)'
        }
        
    except Exception as e:
        current_app.logger.error(f"Erreur globale notifications groupées: {e}")
        return {
            'sent': 0,
            'total_assignments': 0,
            'errors': [f"Erreur globale: {str(e)}"],
            'message': 'Échec de l\'envoi des notifications'
        }
