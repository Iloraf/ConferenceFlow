# app/statistics.py - Système centralisé de statistiques

from .models import Communication, User, Review, ReviewAssignment, CommunicationStatus
from sqlalchemy import func
from datetime import datetime, timedelta

class StatisticsManager:
    """Gestionnaire centralisé des statistiques pour toutes les vues."""
    
    # Couleurs harmonisées pour toute l'application
    COLORS = {
        'primary': '#007bff',      # Bleu principal
        'success': '#28a745',      # Vert pour accepté/terminé
        'warning': '#ffc107',      # Jaune pour en attente/révision
        'danger': '#dc3545',       # Rouge pour rejeté/urgent
        'info': '#17a2b8',        # Cyan pour information
        'secondary': '#6c757d',    # Gris pour neutre
        'purple': '#6f42c1',      # Violet pour WIP
        'orange': '#fd7e14',      # Orange pour review
        'teal': '#20c997',        # Sarcelle pour poster
        'indigo': '#6610f2',      # Indigo pour autre
    }
    
    # Mapping statut -> couleur
    STATUS_COLORS = {
        'résumé_soumis': COLORS['info'],
        'article_soumis': COLORS['warning'], 
        'en_review': COLORS['orange'],
        'révision_demandée': COLORS['warning'],
        'accepté': COLORS['success'],
        'rejeté': COLORS['danger'],
        'wip_soumis': COLORS['purple'],
        'poster_soumis': COLORS['teal'],
    }
    
    # Icônes harmonisées
    ICONS = {
        'users': 'fas fa-users',
        'communications': 'fas fa-file-alt',
        'articles': 'fas fa-newspaper',
        'wips': 'fas fa-cogs',
        'reviews': 'fas fa-search',
        'acceptes': 'fas fa-check-circle',
        'rejetes': 'fas fa-times-circle',
        'en_attente': 'fas fa-clock',
        'terminees': 'fas fa-check',
        'reviewers': 'fas fa-user-edit',
        'assignments': 'fas fa-tasks',
        'en_retard': 'fas fa-exclamation-triangle',
    }
    
    @classmethod
    def get_global_stats(cls):
        """Statistiques globales pour tous les dashboards."""
        
        # Communications par type et statut
        articles = Communication.query.filter_by(type='article').all()
        wips = Communication.query.filter_by(type='wip').all()
        
        # Utilisateurs
        total_users = User.query.count()
        reviewers = User.query.filter_by(is_reviewer=True, is_activated=True).count()
        admins = User.query.filter_by(is_admin=True).count()
        
        # Reviews
        total_reviews = Review.query.count()
        completed_reviews = Review.query.filter_by(completed=True).count()
        pending_reviews = Review.query.filter_by(completed=False).count()
        
        # Assignments - CORRECTIONS ICI
        assignments = ReviewAssignment.query.all()
        overdue_assignments = [a for a in assignments if a.is_overdue]  # SANS parenthèses
        
        return {
            'communications': {
                'total': len(articles) + len(wips),
                'articles': {
                    'total': len(articles),
                    'résumé_soumis': len([a for a in articles if a.status == CommunicationStatus.RESUME_SOUMIS]),
                    'article_soumis': len([a for a in articles if a.status == CommunicationStatus.ARTICLE_SOUMIS]),
                    'en_review': len([a for a in articles if a.status == CommunicationStatus.EN_REVIEW]),
                    'révision_demandée': len([a for a in articles if a.status == CommunicationStatus.REVISION_DEMANDEE]),
                    'acceptés': len([a for a in articles if a.status == CommunicationStatus.ACCEPTE]),
                    'rejetés': len([a for a in articles if a.status == CommunicationStatus.REJETE]),
                    'poster_soumis': len([a for a in articles if a.status == CommunicationStatus.POSTER_SOUMIS]),
                },
                'wips': {
                    'total': len(wips),
                    'wip_soumis': len([w for w in wips if w.status == CommunicationStatus.WIP_SOUMIS]),
                    'poster_soumis': len([w for w in wips if w.status == CommunicationStatus.POSTER_SOUMIS]),
                }
            },
            'users': {
                'total': total_users,
                'reviewers': reviewers,
                'admins': admins,
                'authors': total_users - admins,  # Approximation
            },
            'reviews': {
                'total': total_reviews,
                'completed': completed_reviews,
                'pending': pending_reviews,
                'en_cours': len([a for a in articles if a.status == CommunicationStatus.EN_REVIEW]),
                'completion_rate': (completed_reviews / total_reviews * 100) if total_reviews > 0 else 0,
            },
            'assignments': {
                'total': len(assignments),
                # CORRECTIONS - Utilisation correcte des attributs du modèle ReviewAssignment
                'en_attente': len([a for a in assignments if a.status == 'assigned']),
                'en_cours': len([a for a in assignments if a.status == 'in_progress']),
                'terminées': len([a for a in assignments if a.status == 'completed']),
                'refusées': len([a for a in assignments if a.status == 'declined']),
                'en_retard': len(overdue_assignments),
            },
            'acceptance_rate': cls._calculate_acceptance_rate(articles),
            'colors': cls.COLORS,
            'status_colors': cls.STATUS_COLORS,
            'icons': cls.ICONS,
        }
    
    @classmethod
    def get_dashboard_stats(cls):
        """Statistiques spécifiques au dashboard principal."""
        global_stats = cls.get_global_stats()
        
        # Récentes communications
        recent_communications = Communication.query.order_by(
            Communication.created_at.desc()
        ).limit(5).all()
        
        # Communications nécessitant attention
        needs_attention = Communication.query.filter(
            Communication.status.in_([
                CommunicationStatus.ARTICLE_SOUMIS,
                CommunicationStatus.EN_REVIEW
            ])
        ).limit(5).all()
        
        # Évolution des soumissions (30 derniers jours)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        daily_submissions = cls._get_daily_submissions(thirty_days_ago)
        
        return {
            **global_stats,
            'recent_communications': recent_communications,
            'needs_attention': needs_attention,
            'daily_submissions': daily_submissions,
        }
    
    @classmethod
    def get_communications_dashboard_stats(cls):
        """Statistiques pour le tableau de bord des communications."""
        return cls.get_global_stats()
    
    @classmethod
    def get_reviews_dashboard_stats(cls):
        """Statistiques pour le dashboard des reviews."""
        global_stats = cls.get_global_stats()
        
        # Statistiques spécifiques aux reviews
        articles_needing_reviewers = Communication.query.filter_by(
            type='article',
            status=CommunicationStatus.ARTICLE_SOUMIS
        ).all()
        
        # Articles avec moins de 2 reviewers - CORRECTION ICI
        articles_insufficient_reviewers = []
        for article in Communication.query.filter_by(
            type='article', 
            status=CommunicationStatus.EN_REVIEW
        ).all():
            # Correction: compter les assignments non refusées au lieu d'utiliser reviews.declined
            active_assignments = ReviewAssignment.query.filter(
                ReviewAssignment.communication_id == article.id,
                ReviewAssignment.status != 'declined'
            ).count()
            
            if active_assignments < 2:
                articles_insufficient_reviewers.append(article)
        
        return {
            **global_stats,
            'articles_needing_reviewers': len(articles_needing_reviewers),
            'articles_insufficient_reviewers': len(articles_insufficient_reviewers),
        }
    
    @classmethod
    def get_thematiques_stats(cls):
        """Statistiques pour la gestion des thématiques."""
        from .config_loader import ThematiqueLoader
        
        # Charger les thématiques
        thematiques = ThematiqueLoader.load_themes()
        
        # Statistiques par thématique
        thematique_stats = {}
        for theme in thematiques:
            code = theme['code']
            # Communications par thématique
            comms_count = Communication.query.filter(
                Communication.thematiques_codes.like(f'%{code}%')
            ).count()
            
            # Reviewers spécialisés
            reviewers_count = User.query.filter(
                User.is_reviewer == True,
                User.specialites_codes.like(f'%{code}%')
            ).count()
            
            thematique_stats[code] = {
                'nom': theme['nom'],
                'couleur': theme['couleur'],
                'communications': comms_count,
                'reviewers': reviewers_count,
            }
        
        global_stats = cls.get_global_stats()
        
        return {
            **global_stats,
            'thematiques': thematique_stats,
            'total_thematiques': len(thematiques),
            'total_specialistes': sum(stats['reviewers'] for stats in thematique_stats.values()),
        }
    
    @classmethod
    def get_users_stats(cls):
        """Statistiques pour la gestion des utilisateurs."""
        global_stats = cls.get_global_stats()
        
        # Statistiques supplémentaires pour les utilisateurs
        users_with_affiliations = User.query.filter(
            User.affiliations.any()
        ).count()
        
        users_without_affiliations = global_stats['users']['total'] - users_with_affiliations
        
        return {
            **global_stats,
            'users_with_affiliations': users_with_affiliations,
            'users_without_affiliations': users_without_affiliations,
        }
    
    @classmethod
    def get_assignment_detailed_stats(cls):
        """Statistiques détaillées pour les assignments de reviews."""
        assignments = ReviewAssignment.query.all()
        
        # Statistiques par statut
        stats_by_status = {
            'assigned': len([a for a in assignments if a.status == 'assigned']),
            'in_progress': len([a for a in assignments if a.status == 'in_progress']),
            'completed': len([a for a in assignments if a.status == 'completed']),
            'declined': len([a for a in assignments if a.status == 'declined']),
        }
        
        # Assignments en retard
        overdue_assignments = [a for a in assignments if a.is_overdue]
        
        # Temps moyen de completion
        completed_assignments = [a for a in assignments if a.status == 'completed' and a.completed_at and a.assigned_at]
        avg_completion_time = None
        
        if completed_assignments:
            total_time = sum([(a.completed_at - a.assigned_at).days for a in completed_assignments])
            avg_completion_time = round(total_time / len(completed_assignments), 1)
        
        return {
            'total_assignments': len(assignments),
            'by_status': stats_by_status,
            'overdue_count': len(overdue_assignments),
            'overdue_assignments': overdue_assignments,
            'avg_completion_days': avg_completion_time,
            'completion_rate': round((stats_by_status['completed'] / len(assignments) * 100), 1) if assignments else 0,
        }
    
    @classmethod
    def _calculate_acceptance_rate(cls, articles):
        """Calcule le taux d'acceptation des articles."""
        if not articles:
            return 0
        
        decided_articles = [a for a in articles if a.status in [
            CommunicationStatus.ACCEPTE, 
            CommunicationStatus.REJETE
        ]]
        
        if not decided_articles:
            return 0
        
        accepted = len([a for a in decided_articles if a.status == CommunicationStatus.ACCEPTE])
        return round((accepted / len(decided_articles)) * 100, 1)
    
    @classmethod
    def _get_daily_submissions(cls, start_date):
        """Récupère les soumissions par jour depuis une date."""
        try:
            daily_data = Communication.query.filter(
                Communication.created_at >= start_date
            ).with_entities(
                func.date(Communication.created_at).label('date'),
                func.count(Communication.id).label('count')
            ).group_by(
                func.date(Communication.created_at)
            ).order_by('date').all()
            
            return {
                'dates': [d.date.strftime('%Y-%m-%d') for d in daily_data],
                'counts': [d.count for d in daily_data]
            }
        except Exception as e:
            # En cas d'erreur SQL, retourner des données vides
            return {'dates': [], 'counts': []}
    
    @classmethod
    def get_colored_badge_html(cls, status, text=None):
        """Génère un badge HTML coloré pour un statut."""
        color = cls.STATUS_COLORS.get(status, cls.COLORS['secondary'])
        display_text = text or status.replace('_', ' ').title()
        
        return f'<span class="badge" style="background-color: {color}; color: white;">{display_text}</span>'
    
    @classmethod
    def get_stat_card_data(cls, key, value, icon_key=None, color_key='primary'):
        """Génère les données pour une carte de statistique."""
        return {
            'value': value,
            'icon': cls.ICONS.get(icon_key or key, 'fas fa-chart-bar'),
            'color': cls.COLORS.get(color_key, cls.COLORS['primary']),
            'label': key.replace('_', ' ').title(),
        }
    
    @classmethod
    def get_reviewer_workload_stats(cls):
        """Statistiques de charge de travail des reviewers."""
        reviewers = User.query.filter_by(is_reviewer=True, is_activated=True).all()
        workload_stats = []
        
        for reviewer in reviewers:
            # Assignments actives (assigned ou in_progress)
            active_assignments = ReviewAssignment.query.filter(
                ReviewAssignment.reviewer_id == reviewer.id,
                ReviewAssignment.status.in_(['assigned', 'in_progress'])
            ).count()
            
            # Assignments terminées
            completed_assignments = ReviewAssignment.query.filter(
                ReviewAssignment.reviewer_id == reviewer.id,
                ReviewAssignment.status == 'completed'
            ).count()
            
            # Assignments en retard
            overdue_assignments = ReviewAssignment.query.filter(
                ReviewAssignment.reviewer_id == reviewer.id,
                ReviewAssignment.status.in_(['assigned', 'in_progress'])
            ).all()
            
            overdue_count = len([a for a in overdue_assignments if a.is_overdue])
            
            workload_stats.append({
                'reviewer': reviewer,
                'active': active_assignments,
                'completed': completed_assignments,
                'overdue': overdue_count,
                'total': active_assignments + completed_assignments,
            })
        
        # Trier par charge de travail active
        workload_stats.sort(key=lambda x: x['active'], reverse=True)
        
        return {
            'reviewers': workload_stats,
            'total_reviewers': len(reviewers),
            'avg_active_per_reviewer': sum(r['active'] for r in workload_stats) / len(workload_stats) if workload_stats else 0,
            'max_workload': max([r['active'] for r in workload_stats]) if workload_stats else 0,
        }
