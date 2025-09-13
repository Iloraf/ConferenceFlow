"""
Utilitaires pour nettoyer et valider les textes saisis par les utilisateurs.
Gère les caractères spéciaux, symboles mathématiques, etc.
"""

import re
import unicodedata
from typing import Dict, List, Tuple

# Mappage des caractères mathématiques courants vers leurs équivalents ASCII/LaTeX
MATH_SYMBOLS_MAP = {
    # Lettres grecques
    'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'ε': 'epsilon',
    'ζ': 'zeta', 'η': 'eta', 'θ': 'theta', 'ι': 'iota', 'κ': 'kappa',
    'λ': 'lambda', 'μ': 'mu', 'ν': 'nu', 'ξ': 'xi', 'π': 'pi',
    'ρ': 'rho', 'σ': 'sigma', 'τ': 'tau', 'υ': 'upsilon', 'φ': 'phi',
    'χ': 'chi', 'ψ': 'psi', 'ω': 'omega',
    'Α': 'Alpha', 'Β': 'Beta', 'Γ': 'Gamma', 'Δ': 'Delta', 'Ε': 'Epsilon',
    'Ζ': 'Zeta', 'Η': 'Eta', 'Θ': 'Theta', 'Ι': 'Iota', 'Κ': 'Kappa',
    'Λ': 'Lambda', 'Μ': 'Mu', 'Ν': 'Nu', 'Ξ': 'Xi', 'Π': 'Pi',
    'Ρ': 'Rho', 'Σ': 'Sigma', 'Τ': 'Tau', 'Υ': 'Upsilon', 'Φ': 'Phi',
    'Χ': 'Chi', 'Ψ': 'Psi', 'Ω': 'Omega',
    
    # Symboles mathématiques
    '∞': 'infinity', '∂': 'partial', '∆': 'Delta', '∇': 'nabla',
    '∫': 'integral', '∑': 'sum', '∏': 'product', '√': 'sqrt',
    '≤': '<=', '≥': '>=', '≠': '!=', '≈': '~=', '±': '+/-',
    '×': 'x', '÷': '/', '°': 'deg', '′': "'", '″': '"',
    
    # Indices et exposants
    '₀': '_0', '₁': '_1', '₂': '_2', '₃': '_3', '₄': '_4',
    '₅': '_5', '₆': '_6', '₇': '_7', '₈': '_8', '₉': '_9',
    '⁰': '^0', '¹': '^1', '²': '^2', '³': '^3', '⁴': '^4',
    '⁵': '^5', '⁶': '^6', '⁷': '^7', '⁸': '^8', '⁹': '^9',
    
    # Autres caractères problématiques
    '"': '"', '"': '"', ''': "'", ''': "'",
    '–': '-', '—': '-', '…': '...',
}

# Caractères autorisés (expression régulière)
ALLOWED_CHARS = re.compile(r'^[\w\s\-\.\,\;\:\!\?\(\)\[\]\{\}\/\+\=\<\>\%\$\&\#\@\*\|\\\_\^\~\`\"\'àáâãäåçèéêëìíîïðñòóôõöùúûüýÿÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝŸ]*$', re.UNICODE)

def clean_text(text: str, mode: str = 'soft') -> Tuple[str, List[str]]:
    """
    Nettoie un texte en gérant les caractères spéciaux.
    
    Args:
        text: Le texte à nettoyer
        mode: 'soft' (remplacement) ou 'strict' (suppression)
    
    Returns:
        Tuple[str, List[str]]: (texte nettoyé, liste des avertissements)
    """
    if not text:
        return text, []
    
    warnings = []
    original_text = text
    
    # 1. Normalisation Unicode (décomposer puis recomposer)
    text = unicodedata.normalize('NFKC', text)
    
    # 2. Remplacer les caractères mathématiques connus
    replaced_chars = []
    for char, replacement in MATH_SYMBOLS_MAP.items():
        if char in text:
            text = text.replace(char, replacement)
            replaced_chars.append(f"'{char}' → '{replacement}'")
    
    if replaced_chars:
        warnings.append(f"Symboles remplacés: {', '.join(replaced_chars[:5])}" + 
                       (f" (et {len(replaced_chars)-5} autres)" if len(replaced_chars) > 5 else ""))
    
    # 3. Détecter les caractères problématiques restants
    problematic_chars = []
    for char in text:
        if ord(char) > 127 and char not in MATH_SYMBOLS_MAP.values():
            if char not in [c for line in problematic_chars for c in line]:
                problematic_chars.append(char)
    
    if problematic_chars and mode == 'strict':
        # Mode strict : supprimer les caractères non ASCII
        text = ''.join(char for char in text if ord(char) < 128 or char in MATH_SYMBOLS_MAP.values())
        warnings.append(f"Caractères supprimés: {', '.join(problematic_chars[:10])}")
    #elif problematic_chars:
        # Mode soft : avertir seulement
    #    warnings.append(f"Caractères détectés: {', '.join(problematic_chars[:10])} - Vérifiez la compatibilité")
    
    # 4. Nettoyer les espaces multiples
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 5. Vérifier la longueur
    if len(text) != len(original_text) and not warnings:
        warnings.append("Texte modifié lors du nettoyage")
    
    return text, warnings

def validate_for_hal(text: str) -> Tuple[bool, List[str]]:
    """
    Valide un texte pour l'export HAL.
    
    Returns:
        Tuple[bool, List[str]]: (valide, liste des erreurs)
    """
    errors = []
    
    if not text:
        return True, []
    
    # Caractères interdits pour HAL/XML
    forbidden_chars = ['<', '>', '&', '"']
    found_forbidden = [char for char in forbidden_chars if char in text]
    
    if found_forbidden:
        errors.append(f"Caractères interdits pour HAL: {', '.join(found_forbidden)}")
    
    # Vérifier l'encodage UTF-8
    try:
        text.encode('utf-8')
    except UnicodeEncodeError as e:
        errors.append(f"Erreur d'encodage UTF-8: {str(e)}")
    
    return len(errors) == 0, errors

def suggest_latex_equivalent(text: str) -> str:
    """
    Suggère des équivalents LaTeX pour les expressions mathématiques détectées.
    """
    suggestions = []
    
    # Détecter les patterns mathématiques
    if any(char in MATH_SYMBOLS_MAP for char in text):
        suggestions.append("Utilisez la notation LaTeX pour les formules (ex: $\\alpha$, $x^2$, $\\Delta T$)")
    
    if re.search(r'\d+[\.\,]\d+\s*[×xX]\s*10[\^⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+', text):
        suggestions.append("Notation scientifique: utilisez 'e' (ex: 1.5e-3 au lieu de 1.5×10⁻³)")
    
    if re.search(r'[²³⁴⁵⁶⁷⁸⁹]', text):
        suggestions.append("Exposants: utilisez ^ (ex: x^2 au lieu de x²)")
    
    return " | ".join(suggestions) if suggestions else ""

def clean_for_filename(text: str) -> str:
    """
    Nettoie un texte pour l'utiliser dans un nom de fichier.
    """
    # Remplacer les caractères problématiques
    text = re.sub(r'[^\w\s\-]', '', text, flags=re.UNICODE)
    text = re.sub(r'\s+', '_', text)
    text = text.strip('_')
    
    # Limiter la longueur
    if len(text) > 50:
        text = text[:50].rstrip('_')
    
    return text or "document"
