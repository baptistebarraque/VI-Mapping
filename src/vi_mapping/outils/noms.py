"""Comparaison de noms de lieux et d'adresses."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from .motifs import nom_propre
from .texte import normaliser

# Mots trop courants pour désigner à eux seuls une école : lieux-dits génériques et prénoms
_FAIBLES = frozenset(
    """centre village bourg parc mairie gare eglise moulin bois clos prairie nord sud est ouest saint sainte notre dame
    chateau fontaine ferme pre pres mare val plaine cote coteau coteaux butte hauts haut bas grand grande petit petite
    ville cite quartier jardin jardins square marche croix pont rives rive lac etang sources source vallee vignes
    tilleuls jean pierre paul louis marie jacques charles henri victor jules marcel georges andre francois robert
    albert emile leon anne antoine joseph michel philippe alexandre honore edouard auguste simone helene claude alfred
    arthur gabriel denis germain martin vincent laurent nicolas etienne lucie irene ecole ecoles paris france republique
    general marechal docteur president professeur abbe colonel capitaine commandant freres soeurs
    union coordination locale conseil federation""".split()  # noqa: SIM905
)
_VIDES = frozenset("de du des d la le les l et en a au aux sur sous".split())  # noqa: SIM905
_ABREGES = {
    "av": "avenue", "ave": "avenue", "bd": "boulevard", "bld": "boulevard", "boul": "boulevard", "pl": "place",
    "all": "allee", "che": "chemin", "chem": "chemin", "imp": "impasse", "rte": "route", "sq": "square",
    "crs": "cours", "fg": "faubourg", "fbg": "faubourg", "st": "saint", "ste": "sainte", "gal": "general",
    "gl": "general", "mal": "marechal", "dr": "docteur", "pdt": "president", "pt": "president", "prof": "professeur",
    "cdt": "commandant", "cne": "capitaine", "col": "colonel", "qu": "quai", "pass": "passage", "res": "residence",
}


_TITRES = {
    "st": "saint", "ste": "sainte", "dr": "docteur", "gal": "general", "gl": "general", "mal": "marechal",
    "pdt": "president", "prof": "professeur", "cdt": "commandant", "cne": "capitaine", "col": "colonel",
}


def radical(mot: str) -> str:
    """Forme comparable d'un mot normalisé : abréviation développée, pluriel ignoré."""
    mot = _TITRES.get(mot, mot)
    return mot[:-1] if len(mot) >= 5 and mot[-1] in "sx" else mot


FAIBLES = _FAIBLES | {radical(m) for m in _FAIBLES}


def radicaux(texte: str) -> str:
    """Texte normalisé dont chaque mot est ramené à son radical."""
    return " ".join(radical(m) for m in normaliser(texte).split())


def mots(texte: str) -> list[str]:
    return [m for m in normaliser(texte).split() if m not in _VIDES]


def distinctifs(nom: str) -> list[str]:
    """Mots du nom propre d'un lieu, sans mots vides."""
    return mots(nom_propre(nom))


def fort(mots_: list[str]) -> bool:
    """Le nom suffit-il à désigner une école dans sa commune ?"""
    utiles = [m for m in mots_ if m not in FAIBLES]
    return any(len(m) >= 4 for m in utiles) or len(mots_) >= 2


def similarite(a: list[str], b: list[str]) -> float:
    """0 à 1 entre deux listes de mots distinctifs ; un nom inclus dans l'autre vaut 0,85 s'il est assez précis."""
    if not a or not b:
        return 0.0
    ta, tb = " ".join(a), " ".join(b)
    s = max(fuzz.ratio(ta, tb), fuzz.token_sort_ratio(ta, tb)) / 100
    petit, grand = (a, b) if len(a) <= len(b) else (b, a)
    if set(petit) <= set(grand) and any(len(m) >= 5 and m not in FAIBLES for m in petit):
        s = max(s, 0.85)
    return s


_NUMERO = re.compile(r"^\s*(\d{1,4})\s?(?:[-/]\s?\d{1,4})?\s?(bis|ter|quater|[a-dA-D])?\b[\s,]+(.*)$", re.I)


_DEBUT_VOIE = re.compile(
    r"\d{1,4}\s?(?:bis|ter|quater|[a-d]\b)?\s?,?\s+"
    r"(?:rue|av|bd|bou|pl|all|ch|imp|r|sq|cours|quai|pas|sen|vil|mail|prom|esp|clos|voie|rond)", re.I)


def cle_adresse(adresse: str | None) -> tuple[str, str] | None:
    """(numéro, voie) comparables d'une adresse ; None sans numéro de rue.

    « 7 B Av. du Gal de Gaulle 94220 Charenton » → ("7", "avenue general gaulle") : l'indice de répétition et le
    code postal sont ignorés.
    """
    if not adresse:
        return None
    debut = re.split(r"\b\d{5}\b", adresse)[0]
    m = _DEBUT_VOIE.search(debut)
    m = _NUMERO.match(debut[m.start():] if m else debut)
    if not m:
        return None
    voie = m[3].split(",")[0]
    cles = [_ABREGES.get(x, x) for x in normaliser(voie).split()]
    cles = [x for x in cles if x not in _VIDES]
    return (m[1], " ".join(cles)) if cles else None


_NUMEROS = r"((?:\d{1,4}(?: ?(?:bis|ter|quater|[a-d]))?(?: et| ou| a)? )+)"
_LIAISON = r"(?:(?:de|du|des|d|la|le|les|l) )*"


def developper(texte: str) -> str:
    """Texte normalisé dont les abréviations de voie sont développées (« bd » → « boulevard »)."""
    return " ".join(_ABREGES.get(m, m) for m in normaliser(texte).split())


def numeros_cites(texte: str, voie: str) -> set[int]:
    """Numéros de rue cités devant une voie (clé de `cle_adresse`) dans un texte passé par `developper`.

    « des écoles du 3 et 3 bis rue d'Alésia » et « rue alesia » → {3}
    """
    type_, _, nom = voie.partition(" ")
    if not nom:
        return set()
    suite = " ".join(re.escape(m) for m in nom.split()).replace(" ", f" {_LIAISON}")
    trouves = re.findall(rf"{_NUMEROS}{_LIAISON}{re.escape(type_)} {_LIAISON}{suite}\b", texte)
    return {int(n) for t in trouves for n in re.findall(r"\d+", t)}


def meme_adresse(a: tuple[str, str] | None, b: tuple[str, str] | None) -> bool:
    return bool(a and b) and a[0] == b[0] and fuzz.ratio(a[1], b[1]) >= 90  # type: ignore[index]


_VOCABULAIRE_ACCUEIL = frozenset(
    """centre centres accueil accueils loisir loisirs espace service alsh clsh alae adl clae periscolaire periscolaires
    peri scolaire extrascolaire garderie maternel maternelle elementaire elementaires primaire maternels municipal
    municipale municipaux communal intercommunal enfance enfant enfants jeunesse ados ado sans hebergement aere site
    asso association mercredi mercredis soir matin ecole groupe""".split()  # noqa: SIM905
)


def distinctifs_accueil(nom: str, commune: str) -> list[str]:
    """Mots propres au nom d'un accueil : ni le vocabulaire courant, ni le nom de la commune."""
    n = normaliser(nom)
    c = normaliser(commune)
    if c and n.endswith(c):
        n = n[: -len(c)]
    return [m for m in mots(nom_propre(n) or n) if m not in _VOCABULAIRE_ACCUEIL]
