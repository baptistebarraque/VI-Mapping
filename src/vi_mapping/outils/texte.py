"""Normalisation de textes et nettoyage des données personnelles."""

from __future__ import annotations

import re
import unicodedata

_EMAIL = re.compile(r"[\w.+-]+\s?(?:@|\[at\]|\(at\))\s?[\w-]+(?:\.[\w-]+)+", re.I)
_TEL = re.compile(r"(?<!\d)(?:(?:\+|00)33[\s.\-]?(?:\(0\)\s?)?|0)[1-9](?:[\s.\-]?\d{2}){4}(?!\d)")
# « chez M. Dupont », « c/o Mme X », « Mme X » en complément d'adresse
_CHEZ = re.compile(
    r"\b(?:chez|c/o|c/ ?o\.?|a l.attention de|attn?\.?)\b[^,;]*"
    r"|\b(?:m|mr|mme|mlle|monsieur|madame|mademoiselle)\b\.?\s+[^,;]*",
    re.I,
)
_ESPACES = re.compile(r"\s+")


def sans_accents(texte: str) -> str:
    texte = texte.replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae")
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def normaliser(texte: str | None) -> str:
    """Minuscules, sans accents ni ponctuation, espaces simples."""
    if not texte:
        return ""
    t = sans_accents(texte).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return _ESPACES.sub(" ", t).strip()


def propre(texte: str | None) -> str | None:
    """Espaces réduits ; None si vide."""
    if texte is None:
        return None
    t = _ESPACES.sub(" ", str(texte)).strip()
    return t or None


def sans_contact(texte: str | None) -> str | None:
    """Retire e-mails et numéros de téléphone d'un texte libre."""
    if texte is None:
        return None
    return propre(_TEL.sub("", _EMAIL.sub("", texte)))


def contient_contact(texte: str | None) -> bool:
    return bool(texte) and bool(_EMAIL.search(texte) or _TEL.search(texte))


def adresse_sans_personne(texte: str | None) -> str | None:
    """Retire d'une adresse les mentions de personnes (« chez Mme X ») et les contacts."""
    if texte is None:
        return None
    t = sans_contact(_CHEZ.sub("", texte))
    return propre(t.strip(" ,;-")) if t else None


_PETITS_MOTS = {"de", "du", "des", "la", "le", "les", "et", "en", "sur", "sous", "aux", "au", "a", "d", "l", "lès"}


def titre(texte: str | None) -> str | None:
    """« ECOLE JULES FERRY » -> « Ecole Jules Ferry » (laisse intacts les textes déjà en casse mixte)."""
    t = propre(texte)
    if t is None or t != t.upper():
        return t
    mots = []
    for i, mot in enumerate(t.lower().split(" ")):
        morceaux = [
            m if (i > 0 and m in _PETITS_MOTS) else m[:1].upper() + m[1:]
            for m in re.split(r"(?<=[-'’])", mot)
        ]
        mots.append("".join(morceaux))
    return " ".join(mots)
