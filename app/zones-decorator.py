"""
Décorateurs pour protéger les zones d'accès dans Conference Flow
"""
from functools import wraps
from flask import render_template, current_app
from .zones_manager import zones_manager


def zone_required(zone_name):
    """
    Décorateur pour vérifier qu'une zone est ouverte avant d'accéder à une route.
    
    Usage:
    @zone_required('registration')
    def register():
        # Route accessible seulement si la zone 'registration' est ouverte
        pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                if zones_manager.is_zone_open(zone_name):
                    # Zone ouverte, accès autorisé
                    return f(*args, **kwargs)
                else:
                    # Zone fermée, afficher le message
                    zone_info = zones_manager.get_zone_info(zone_name)
                    return render_template('zone_closed.html', 
                                         zone_name=zone_name,
                                         zone_info=zone_info), 503
            except Exception as e:
                current_app.logger.error(f"Erreur vérification zone {zone_name}: {e}")
                # En cas d'erreur, on bloque l'accès par sécurité
                return render_template('zone_closed.html', 
                                     zone_name=zone_name,
                                     zone_info={'message': 'Cette zone est temporairement indisponible.'}), 503
        
        return decorated_function
    return decorator


def check_zone_access(zone_name):
    """
    Fonction utilitaire pour vérifier l'accès à une zone.
    
    Usage dans les templates:
    {% if check_zone_access('submission') %}
        <!-- Contenu accessible -->
    {% else %}
        <!-- Zone fermée -->
    {% endif %}
    """
    try:
        return zones_manager.is_zone_open(zone_name)
    except Exception:
        return False


def get_zone_status(zone_name):
    """
    Fonction utilitaire pour récupérer le statut complet d'une zone.
    
    Usage dans les templates:
    {% set zone_status = get_zone_status('registration') %}
    {% if zone_status.is_open %}
        <!-- Zone ouverte -->
    {% else %}
        <p>{{ zone_status.message }}</p>
    {% endif %}
    """
    try:
        zone_info = zones_manager.get_zone_info(zone_name)
        zone_info['is_open'] = zones_manager.is_zone_open(zone_name)
        return zone_info
    except Exception:
        return {
            'is_open': False,
            'message': 'Cette zone est temporairement indisponible.',
            'display_name': zone_name
        }
