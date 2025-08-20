# app/hal_integration/hal_xml_generator.py
"""
Générateur XML HAL pour Conference Flow - SFT 2026
Utilise les données des modèles Communication de Conference Flow
"""

from datetime import datetime
from typing import Dict, List
from flask import current_app
from app.models import Communication, User
import logging

class HALXMLGenerator:
    """Générateur de XML HAL à partir des données Conference Flow"""
    
    # Mapping des types Conference Flow vers HAL
    TYPE_MAPPING = {
        'article': {
            'hal_typology': 'COMM',  # Communication dans un congrès (inproceedings)
            'hal_audience': '2',     # International
            'conference_title': 'Actes du Congrès de la Société Française de Thermique SFT 2026',
            'session_title': 'Congrès SFT 2026'
        },
        'wip': {
            'hal_typology': 'OTHERREPORT',  # Document de travail
            'hal_audience': '2',            # International
            'conference_title': 'Work in Progress - Congrès SFT 2026',
            'session_title': 'Congrès SFT 2026 - Session Work in Progress'
        },
        'poster': {
            'hal_typology': 'POSTER',  # Poster de conférence
            'hal_audience': '2',       # International
            'conference_title': 'Posters - Congrès SFT 2026',
            'session_title': 'Congrès SFT 2026 - Session Posters'
        }
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.collection_id = "SFT2026"
        
    def generate_for_communication(self, communication: Communication) -> str:
        """
        Génère le XML HAL pour une communication Conference Flow
        
        Args:
            communication: Instance Communication de Conference Flow
            
        Returns:
            str: XML HAL formaté
        """
        
        # Récupérer le type de document
        doc_type = communication.submission_type.lower() if communication.submission_type else 'article'
        if doc_type not in self.TYPE_MAPPING:
            doc_type = 'article'  # Par défaut
            
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
            'affiliations': self._extract_affiliations(communication),
            'doc_type': doc_type,
            'type_info': type_info,
            'communication_id': communication.id
        }
        
        return self._generate_xml(xml_data)
    
    def _extract_authors(self, communication: Communication) -> List[Dict]:
        """Extrait la liste des auteurs depuis Communication"""
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
                'role': 'aut'
            }
            authors.append(author_data)
        
        return authors
    
    def _extract_keywords(self, communication: Communication) -> Dict:
        """Extrait les mots-clés"""
        keywords = {'fr': [], 'en': []}
        
        if hasattr(communication, 'keywords') and communication.keywords:
            # Supposer que les mots-clés sont séparés par des virgules
            keywords['fr'] = [kw.strip() for kw in communication.keywords.split(',') if kw.strip()]
        
        # Ajouter des mots-clés génériques SFT
        base_keywords_fr = ['thermique', 'transfert de chaleur', 'SFT 2026']
        base_keywords_en = ['thermal', 'heat transfer', 'SFT 2026']
        
        keywords['fr'].extend(base_keywords_fr)
        keywords['en'].extend(base_keywords_en)
        
        return keywords
    
    def _extract_affiliations(self, communication: Communication) -> List[Dict]:
        """Extrait les affiliations"""
        affiliations = []
        
        # Affiliation principale
        main_affiliation = {
            'id': 1,
            'name': communication.user.affiliation or 'Institution non renseignée',
            'acronym': '',
            'address': '',
            'city': '',
            'country': 'FR',
            'rnsr': '',
            'ror': ''
        }
        affiliations.append(main_affiliation)
        
        # TODO: Gérer les affiliations des co-auteurs
        # Cela dépend de la structure de vos données coauteurs
        
        return affiliations
    
    def _generate_xml(self, data: Dict) -> str:
        """Génère le XML HAL final"""
        
        current_year = datetime.now().year
        type_info = data['type_info']
        
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
                            <date type="start">2026-05-26</date>
                            <date type="end">2026-05-29</date>
                            <settlement>Flavigny-sur-Moselle</settlement>
                            <country key="FR">France</country>
                        </meeting>
                        <imprint>
                            <publisher>Société Française de Thermique</publisher>
                            <date type="datePub">{current_year}</date>
                            <note type="audience" n="{type_info['hal_audience']}">International</note>
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
                <classCode scheme="halPortal" n="{self.collection_id}">SFT 2026</classCode>
                
                {self._generate_keywords_xml(data['keywords'])}
            </textClass>
            
            {self._generate_abstracts_xml(data['abstracts'])}
        </profileDesc>
    </teiHeader>
    
    <text>
        <body>
            <back>
                <listOrg type="structures">
                    {self._generate_structures_xml(data['affiliations'])}
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
        """Génère le XML des structures d'affiliation"""
        structures_xml = []
        
        for affiliation in affiliations:
            struct_xml = f'''
                    <org type="institution" xml:id="localStruct-{affiliation['id']}">
                        <orgName>{self._escape_xml(affiliation['name'])}</orgName>'''
            
            if affiliation['acronym']:
                struct_xml += f'\n                        <orgName type="acronym">{self._escape_xml(affiliation["acronym"])}</orgName>'
            
            if affiliation['rnsr']:
                struct_xml += f'\n                        <idno type="RNSR">{affiliation["rnsr"]}</idno>'
            if affiliation['ror']:
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
