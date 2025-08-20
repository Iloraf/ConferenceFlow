"""
Module d'intégration HAL pour Conference Flow
Gère le dépôt automatique des communications SFT 2026
"""

from .hal_client import HALClient
from .hal_xml_generator import HALXMLGenerator
from .hal_routes import hal_bp

__all__ = ['HALClient', 'HALXMLGenerator', 'hal_bp']
