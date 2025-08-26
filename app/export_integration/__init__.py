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

# Composants HAL (existants)
from .hal_client import HALClient
from .hal_xml_generator import HALXMLGenerator
from .hal_routes import hal_bp

# Nouveaux composants export unifié
from .export_manager import ExportManager
from .doi_generator import DOIGenerator
from .doi_xml_generator import DOIXMLGenerator
from .pdf_extractor import PDFExtractor, extract_abstract_from_pdf
from .export_routes import export_bp

__all__ = [
    # Composants HAL (existants)
    'HALClient', 
    'HALXMLGenerator', 
    'hal_bp',
    
    # Nouveaux composants export
    'ExportManager',
    'DOIGenerator', 
    'DOIXMLGenerator',
    'PDFExtractor',
    'extract_abstract_from_pdf',
    'export_bp'
]

