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

from datetime import datetime
from typing import Dict, List
from flask import current_app
from app.models import Communication, User
import logging

class HALConfigError(Exception):
    """Exception levée en cas d'erreur de configuration HAL"""
    pass

class HALXMLGenerator:
    """Générateur de XML HAL à partir des données Conference Flow"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # SÉCURISÉ : Charger collection_id depuis conference.yml (OBLIGATOIRE)
        self.collection_id = self._load_collection_id()
        
        # SÉCURISÉ : Charger la configuration depuis conference.yml (OBLIGATOIRE)
        self.TYPE_MAPPING = self._load_hal_config()
    
    def _load_collection_id(self) -> str:
        """
        Charge l'ID de collection HAL depuis conference.yml
        LÈVE UNE EXCEPTION si la configuration est manquante ou incorrecte
        """
        try:
            config = current_app.conference_config
            hal_config = config.get('integrations', {}).get('hal', {})
            
            if not hal_config:
                raise HALConfigError("Configuration HAL manquante dans conference.yml")
            
            collection_id = hal_config.get('collection_id')
            
            if not collection_id:
                raise HALConfigError("collection_id manquant dans conference.yml > integrations > hal")
            
            if not isinstance(collection_id, str) or len(collection_id.strip()) == 0:
                raise HALConfigError("collection_id invalide dans conference.yml")
            
            collection_id = collection_id.strip()
            self.logger.info(f"Collection HAL chargée: {collection_id}")
            return collection_id
            
        except AttributeError:
            raise HALConfigError("Configuration Conference Flow non disponible (current_app.conference_config)")
        except Exception as e:
            raise HALConfigError(f"Erreur lors du chargement collection_id: {e}")
    
    def _load_hal_config(self) -> Dict:
        """
        Charge la configuration HAL depuis conference.yml
        LÈVE UNE EXCEPTION si la configuration est manquante ou incorrecte
        """
        try:
            config = current_app.conference_config
            hal_config = config.get('integrations', {}).get('hal', {})
            
            if not hal_config:
                raise HALConfigError("Configuration HAL manquante dans conference.yml")
            
            conference_info = config.get('conference', {})
            conference_name = conference_info.get('name')
            
            if not conference_name:
                raise HALConfigError("Nom de conférence manquant dans conference.yml > conference > full_name")
            
            # Types de documents depuis conference.yml
            document_types = hal_config.get('document_types', {})
            
            if not document_types:
                raise HALConfigError("Types de documents HAL manquants dans conference.yml > integrations > hal > document_types")
            
            # Vérifier que les types requis sont présents
            required_types = ['article', 'wip', 'poster']
            for doc_type in required_types:
                if doc_type not in document_types:
                    raise HALConfigError(f"Type de document '{doc_type}' manquant dans la configuration HAL")
                
                type_config = document_types[doc_type]
                
                # Vérifier les champs obligatoires
                if not type_config.get('hal_typology'):
                    raise HALConfigError(f"hal_typology manquant pour le type '{doc_type}'")
                if not type_config.get('hal_audience'):
                    raise HALConfigError(f"hal_audience manquant pour le type '{doc_type}'")
            
            type_mapping = {}
            
            # Article
            article_config = document_types['article']
            type_mapping['article'] = {
                'hal_typology': article_config['hal_typology'],
                'hal_audience': article_config['hal_audience'],
                'conference_title': f"Actes du {conference_name}",
                'session_title': conference_name
            }
            
            # WIP
            wip_config = document_types['wip']
            type_mapping['wip'] = {
                'hal_typology': wip_config['hal_typology'],
                'hal_audience': wip_config['hal_audience'],
                'conference_title': f"Work in Progress - {conference_name}",
                'session_title': f"{conference_name} - Session Work in Progress"
            }
            
            # Poster
            poster_config = document_types['poster']
            type_mapping['poster'] = {
                'hal_typology': poster_config['hal_typology'],
                'hal_audience': poster_config['hal_audience'],
                'conference_title': f"Posters - {conference_name}",
                'session_title': f"{conference_name} - Session Posters"
            }
            
            self.logger.info(f"Configuration HAL chargée avec succès pour {conference_name}")
            return type_mapping
            
        except HALConfigError:
            raise  # Re-lancer les erreurs de config HAL
        except Exception as e:
            raise HALConfigError(f"Erreur inattendue lors du chargement de la config HAL: {e}")
    
    def _load_conference_metadata(self) -> Dict:
        """
        Charge les métadonnées de conférence depuis conference.yml
        LÈVE UNE EXCEPTION si les données essentielles sont manquantes
        """
        try:
            config = current_app.conference_config
            hal_config = config.get('integrations', {}).get('hal', {})
            conference_metadata = hal_config.get('conference_metadata', {})
            
            # Si pas de métadonnées HAL spécifiques, construire depuis la config générale
            if not conference_metadata:
                conference_info = config.get('conference', {})
                dates_info = config.get('dates', {}).get('conference', {})
                location_info = config.get('conference', {}).get('location', {})
                
                # Vérifications des données essentielles
                if not conference_info.get('full_name'):
                    raise HALConfigError("Nom de conférence manquant (conference.full_name)")
                
                if not dates_info.get('start') or not dates_info.get('end'):
                    raise HALConfigError("Dates de conférence manquantes (dates.conference.start/end)")
                
                if not location_info.get('city'):
                    raise HALConfigError("Lieu de conférence manquant (conference.location.city)")
                
                conference_metadata = {
                    'title_fr': f"Actes du {conference_info['full_name']}",
                    'title_en': f"Proceedings of the {conference_info['full_name']}",
                    'publisher': conference_info.get('organizer', 'Société Française de Thermique'),
                    'location': location_info['city'],
                    'country': 'FR',
                    'dates': {
                        'start': dates_info['start'],
                        'end': dates_info['end']
                    }
                }
            
            return conference_metadata
            
        except HALConfigError:
            raise  # Re-lancer les erreurs de config HAL
        except Exception as e:
            raise HALConfigError(f"Erreur lors du chargement des métadonnées de conférence: {e}")

    def generate_for_communication(self, communication: Communication) -> str:
        """
        Génère le XML HAL pour une communication Conference Flow
        
        Args:
            communication: Instance Communication de Conference Flow
            
        Returns:
            str: XML HAL formaté
            
        Raises:
            HALConfigError: Si la configuration HAL est incorrecte
        """
        
        # Récupérer le type de document
        doc_type = communication.submission_type.lower() if communication.submission_type else 'article'
        if doc_type not in self.TYPE_MAPPING:
            raise HALConfigError(f"Type de document '{doc_type}' non configuré dans conference.yml")
            
        type_info = self.TYPE_MAPPING[doc_type]
        
        # Construire les données pour le template
        xml_data = {
            'title_fr': communication.title or '',
            'title_en': communication.title_en or communication.title or '',
            'authors': self._extract_authors(communication),
            'abstracts': {
                'fr': communication.abstract or '',
                'en': communication.abstract_en or communication.abstract or ''
            },
            'keywords': self._extract_keywords(communication),
            'doc_type': doc_type,
            'type_info': type_info,
            'communication_id': communication.id
        }
        
        return self._generate_xml(xml_data)

    def _extract_authors(self, communication: Communication) -> List[Dict]:
        """
        Extrait la liste des auteurs avec leurs affiliations HAL
        Utilise les nouveaux champs struct_id_hal, acronym_hal, type_hal
        """
        authors = []
        
        # Utiliser la relation many-to-many authors de votre modèle
        for i, author in enumerate(communication.authors, start=1):
            author_data = {
                'first_name': author.first_name or '',
                'last_name': author.last_name or '',
                'email': author.email or '',
                'idhal': getattr(author, 'idhal', '') or '',
                'orcid': getattr(author, 'orcid', '') or '',
                'affiliation_id': i,
                'role': 'aut',
                'affiliations_hal': []  # NOUVEAU : données HAL spécifiques
            }
            
            # NOUVEAU : Extraire les affiliations avec les champs HAL
            for affiliation in author.affiliations:
                hal_data = {
                    'id': affiliation.id,
                    'sigle': affiliation.sigle or '',
                    'nom_complet': affiliation.nom_complet or '',
                    'adresse': affiliation.adresse or '',
                    'struct_id_hal': affiliation.struct_id_hal,      # NOUVEAU
                    'acronym_hal': affiliation.acronym_hal,          # NOUVEAU  
                    'type_hal': affiliation.type_hal                 # NOUVEAU
                }
                
                # Debug log pour voir les données HAL
                if affiliation.struct_id_hal:
                    self.logger.info(f"Affiliation {affiliation.sigle} : struct_id_hal = {affiliation.struct_id_hal}")
                
                author_data['affiliations_hal'].append(hal_data)
            
            authors.append(author_data)
        
        return authors
    
    def _extract_keywords(self, communication: Communication) -> Dict:
        """Extrait les mots-clés"""
        keywords = {'fr': [], 'en': []}
        
        if hasattr(communication, 'keywords') and communication.keywords:
            # Supposer que les mots-clés sont séparés par des virgules
            keywords['fr'] = [kw.strip() for kw in communication.keywords.split(',') if kw.strip()]
        
        # Ajouter des mots-clés génériques 
        base_keywords_fr = ['thermique', 'transfert de chaleur', 'SFT 2026']
        base_keywords_en = ['thermal', 'heat transfer', 'SFT 2026']
        
        keywords['fr'].extend(base_keywords_fr)
        keywords['en'].extend(base_keywords_en)
        
        return keywords
    
    def _collect_affiliations_from_authors(self, authors: List[Dict]) -> List[Dict]:
        """
        Collecte toutes les affiliations uniques depuis les auteurs
        et les formate pour _generate_structures_xml
        """
        affiliations_dict = {}  # Pour éviter les doublons
        
        for author in authors:
            for affiliation_hal in author.get('affiliations_hal', []):
                affiliation_id = affiliation_hal['id']
                
                if affiliation_id not in affiliations_dict:
                    # Formatage pour compatibilité avec _generate_structures_xml
                    formatted_affiliation = {
                        'id': affiliation_id,
                        'name': affiliation_hal['nom_complet'],
                        'acronym': affiliation_hal.get('acronym_hal', '') or affiliation_hal.get('sigle', ''),
                        'address': affiliation_hal.get('adresse', 'Adresse non renseignée'),
                        'city': 'Ville non renseignée',
                        'country': 'FR',
                        # NOUVEAU : Identifiants HAL spécifiques
                        'struct_id_hal': affiliation_hal.get('struct_id_hal', ''),
                        'type_hal': affiliation_hal.get('type_hal', ''),
                        # Anciens champs pour compatibilité
                        'rnsr': '',
                        'ror': ''
                    }
                    
                    affiliations_dict[affiliation_id] = formatted_affiliation
        
        return list(affiliations_dict.values())
    
    def _generate_xml(self, data: Dict) -> str:
        """Génère le XML HAL final"""
        
        current_year = datetime.now().year
        type_info = data['type_info']
        
        # NOUVEAU : Charger les métadonnées de conférence
        conference_meta = self._load_conference_metadata()
        
        # NOUVEAU : Déterminer le texte d'audience
        audience_text = "National" if type_info['hal_audience'] == '1' else "International"
        
        # NOUVEAU : Extraire les affiliations depuis les auteurs
        all_affiliations = self._collect_affiliations_from_authors(data['authors'])
        
        xml_template = f'''<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" 
     xmlns:hal="http://hal.archives-ouvertes.fr/">
     
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title xml:lang="fr">{self._escape_xml(data['title_fr'])}</title>
                <title xml:lang="en">{self._escape_xml(data['title_en'])}</title>
                
                {self._generate_authors_xml(data['authors'])}
            </titleStmt>
            
            <editionStmt>
                <edition>
                    <date type="whenWritten">{current_year}</date>
                </edition>
            </editionStmt>
            
            <publicationStmt>
                <distributor>CCSD</distributor>
                <availability status="restricted">
                    <licence target="http://creativecommons.org/licenses/by/">
                        Attribution - CC BY 4.0
                    </licence>
                </availability>
            </publicationStmt>
            
            <sourceDesc>
                <biblStruct>
                    <analytic>
                        <title xml:lang="fr">{self._escape_xml(data['title_fr'])}</title>
                        {self._generate_authors_analytic_xml(data['authors'])}
                    </analytic>
                    
                    <monogr>
                        <title level="m">{type_info['conference_title']}</title>
                        <meeting>
                            <title>{type_info['session_title']}</title>
                            <date type="start">{conference_meta['dates']['start']}</date>
                            <date type="end">{conference_meta['dates']['end']}</date>
                            <settlement>{conference_meta['location']}</settlement>
                            <country key="{conference_meta['country']}">{conference_meta.get('country_name', 'France')}</country>
                        </meeting>
                        <imprint>
                            <publisher>{conference_meta['publisher']}</publisher>
                            <date type="datePub">{current_year}</date>
                            <note type="audience" n="{type_info['hal_audience']}">{audience_text}</note>
                        </imprint>
                    </monogr>
                </biblStruct>
            </sourceDesc>
        </fileDesc>
        
        <profileDesc>
            <langUsage>
                <language ident="fr">Français</language>
            </langUsage>
            
            <textClass>
                <classCode scheme="halDomain" n="spi.energe">Sciences de l'ingénieur/Génie énergétique</classCode>
                <classCode scheme="halTypology" n="{type_info['hal_typology']}">{self._get_typology_label(type_info['hal_typology'])}</classCode>
                <classCode scheme="halPortal" n="{self.collection_id}">{self.collection_id}</classCode>
                
                {self._generate_keywords_xml(data['keywords'])}
            </textClass>
            
            {self._generate_abstracts_xml(data['abstracts'])}
        </profileDesc>
    </teiHeader>
    
    <text>
        <body>
            <back>
                <listOrg type="structures">
                    {self._generate_structures_xml(all_affiliations)}
                </listOrg>
            </back>
        </body>
    </text>
</TEI>'''
        
        return xml_template
    
    def _generate_authors_xml(self, authors: List[Dict]) -> str:
        """Génère le XML des auteurs pour titleStmt"""
        authors_xml = []
        
        for author in authors:
            affiliation_ref = f'#localStruct-{author["affiliation_id"]}'
            
            author_xml = f'''
                <author role="{author['role']}">
                    <persName>
                        <forename type="first">{self._escape_xml(author['first_name'])}</forename>
                        <surname>{self._escape_xml(author['last_name'])}</surname>
                    </persName>
                    <email>{self._escape_xml(author['email'])}</email>'''
            
            if author['idhal']:
                author_xml += f'\n                    <idno type="idhal">{self._escape_xml(author["idhal"])}</idno>'
            if author['orcid']:
                orcid_clean = author['orcid'].replace('https://orcid.org/', '').replace('http://orcid.org/', '')
                author_xml += f'\n                    <idno type="ORCID">{orcid_clean}</idno>'
            
            author_xml += f'\n                    <affiliation ref="{affiliation_ref}"/>'
            author_xml += '\n                </author>'
            
            authors_xml.append(author_xml)
        
        return ''.join(authors_xml)
    
    def _generate_authors_analytic_xml(self, authors: List[Dict]) -> str:
        """Génère le XML des auteurs pour analytic (version simplifiée)"""
        authors_xml = []
        
        for author in authors:
            affiliation_ref = f'#localStruct-{author["affiliation_id"]}'
            
            author_xml = f'''
                        <author role="{author['role']}">
                            <persName>
                                <forename type="first">{self._escape_xml(author['first_name'])}</forename>
                                <surname>{self._escape_xml(author['last_name'])}</surname>
                            </persName>
                            <affiliation ref="{affiliation_ref}"/>
                        </author>'''
            
            authors_xml.append(author_xml)
        
        return ''.join(authors_xml)
    
    def _generate_keywords_xml(self, keywords: Dict) -> str:
        """Génère le XML des mots-clés"""
        keywords_xml = []
        
        if keywords.get('fr'):
            fr_terms = '\n                    '.join([f'<term>{self._escape_xml(kw)}</term>' 
                                                    for kw in keywords['fr'][:10]])  # Max 10 mots-clés
            keywords_xml.append(f'''
                <keywords xml:lang="fr">
                    {fr_terms}
                </keywords>''')
        
        if keywords.get('en'):
            en_terms = '\n                    '.join([f'<term>{self._escape_xml(kw)}</term>' 
                                                    for kw in keywords['en'][:10]])
            keywords_xml.append(f'''
                <keywords xml:lang="en">
                    {en_terms}
                </keywords>''')
        
        return ''.join(keywords_xml)
    
    def _generate_abstracts_xml(self, abstracts: Dict) -> str:
        """Génère le XML des résumés"""
        abstracts_xml = []
        
        if abstracts.get('fr'):
            abstracts_xml.append(f'''
            <abstract xml:lang="fr">
                <p>{self._escape_xml(abstracts['fr'])}</p>
            </abstract>''')
        
        if abstracts.get('en') and abstracts['en'] != abstracts.get('fr'):
            abstracts_xml.append(f'''
            <abstract xml:lang="en">
                <p>{self._escape_xml(abstracts['en'])}</p>
            </abstract>''')
        
        return ''.join(abstracts_xml)
    
    def _generate_structures_xml(self, affiliations: List[Dict]) -> str:
        """Génère le XML des structures d'affiliation avec support HAL"""
        structures_xml = []
        
        for affiliation in affiliations:
            struct_xml = f'''
                    <org type="institution" xml:id="localStruct-{affiliation['id']}">
                        <orgName>{self._escape_xml(affiliation['name'])}</orgName>'''
            
            if affiliation['acronym']:
                struct_xml += f'\n                        <orgName type="acronym">{self._escape_xml(affiliation["acronym"])}</orgName>'
            
            # NOUVEAU : Utiliser struct_id_hal en priorité
            if affiliation.get('struct_id_hal'):
                struct_xml += f'\n                        <idno type="structId">{affiliation["struct_id_hal"]}</idno>'
                self.logger.info(f"Structure {affiliation['name']} : utilisation struct_id_hal = {affiliation['struct_id_hal']}")
            
            # Anciens identifiants en fallback
            if affiliation.get('rnsr'):
                struct_xml += f'\n                        <idno type="RNSR">{affiliation["rnsr"]}</idno>'
            if affiliation.get('ror'):
                struct_xml += f'\n                        <idno type="ROR">{affiliation["ror"]}</idno>'
            
            struct_xml += f'''
                        <desc>
                            <address>
                                <addrLine>{self._escape_xml(affiliation.get('address', 'Adresse non renseignée'))}</addrLine>
                                <settlement>{self._escape_xml(affiliation.get('city', 'Ville non renseignée'))}</settlement>
                                <country key="{affiliation.get('country', 'FR')}">France</country>
                            </address>
                        </desc>
                    </org>'''
            
            structures_xml.append(struct_xml)
        
        return ''.join(structures_xml)
    
    def _get_typology_label(self, typology: str) -> str:
        """Retourne le label pour une typologie HAL"""
        labels = {
            'COMM': 'Communication dans un congrès',
            'POSTER': 'Poster',
            'OTHERREPORT': 'Autre publication scientifique'
        }
        return labels.get(typology, typology)
    
    def _escape_xml(self, text: str) -> str:
        """Échappe les caractères spéciaux XML"""
        if not text:
            return ''
        
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        
        return text

