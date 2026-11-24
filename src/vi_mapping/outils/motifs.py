"""Reconnaissance des lieux par leur nom (accueils de loisirs, AMAP, épiceries solidaires…).

Les motifs s'appliquent à un texte passé par `normaliser()` : minuscules, sans accent ni ponctuation.
"""

from __future__ import annotations

import re

# ----------------------------------------------------------------- accueils périscolaires
ACCUEIL = re.compile(
    r"\b(centres?|accueils?|ctre|cent|espaces?) ((municipal|municipaux|intercommunal|communal) )?"
    r"(d |de |des )?(accueil )?((de|des|d) )?(loisirs?)\b"
    r"|\bcentres? de loisirs? sans hebergement\b|\balsh\b|\bclsh\b|\balae\b|\bcentres? aeres?\b"
    r"|\baccueils? (de loisirs? )?peri ?scolaires?\b|\b(service|activites?|garderie|accueil) peri ?scolaires?\b"
    r"|\bperi ?scolaire\b|\bgarderie (scolaire|du soir)\b|\baccueil (du )?(matin et )?(du )?soir\b"
)
# Lieux de même vocabulaire qui n'accueillent pas les écoliers : base de loisirs, petite enfance, abords…
PAS_ACCUEIL = re.compile(
    r"\bbase de loisirs?\b|\bequestre|\bponey|\bnautique|\bkarting|\bsports? et loisirs\b|\bfrance loisirs\b"
    r"|\bhalte garderie\b|\bcreche\b|\bmulti accueil\b|\bpetite enfance\b|\bp et t\b|\bpostes? et tele"
    r"|\bbois du\b|\bcour\b|\bparking\b|\bnautisme\b|\bseniors?\b|\bpersonnes agees\b|\btroisieme age\b|\b3eme age\b"
    r"|\bferme du centre de loisirs\b|\barret\b|\bcomite d entreprise\b|\bville de paris loisirs\b"
)
SOIR = re.compile(r"\bperi ?scolaires?\b|\bgarderie\b|\bsoir\b|\bpost ?scolaire\b|\balae\b")
MERCREDI = re.compile(r"\bmercredis?\b")


def est_accueil(nom: str) -> bool:
    return bool(ACCUEIL.search(nom)) and not PAS_ACCUEIL.search(nom)


def accueil_soir(nom: str) -> bool | None:
    """True si le nom annonce un accueil périscolaire ou du soir ; sinon inconnu (jamais False)."""
    return True if SOIR.search(nom) else None


def accueil_mercredi(nom: str) -> bool | None:
    return True if MERCREDI.search(nom) else None


# ----------------------------------------------------------------- relais locaux
AMAP = re.compile(
    r"\bamaps?\b|\bassociation pour le maintien (de l|d une|des?) ?(l )?agricultures? (paysannes?|de proximite)\b"
)
PAS_AMAP = re.compile(r"\bmecanique\b|\btolerie\b|\breseau (des )?amap\b|\bamap ile de france\b")
EPICERIE = re.compile(r"\bepiceries? (sociales?|solidaires?)\b|\bepiceries? (sociale et|et) solidaires?\b")
FERME = re.compile(r"\bfermes? (urbaines? )?(et )?pedagogiques?\b|\bfermes? d animation\b")
CENTRE_SOCIAL = re.compile(
    r"\bcentres? (social|sociaux)\b|\bcentres? socio ?(culturels?|educatifs?)\b|\bespaces? de vie sociale\b"
)
PAS_CENTRE_SOCIAL = re.compile(
    r"\bmosquee|\bislam|\bcultuel|\beglise|\bculte\b|\bfederation\b|\bunion\b|\bmedico|\baction sociale\b"
    r"|\bressources humaines\b|\bformation\b|\bsecurite sociale\b|\bimmigrant"
)

RELAIS = {
    "distribution_amap": (AMAP, PAS_AMAP),
    "epicerie_solidaire": (EPICERIE, None),
    "ferme_pedagogique": (FERME, None),
    "centre_social": (CENTRE_SOCIAL, PAS_CENTRE_SOCIAL),
}


def type_relais(nom: str) -> str | None:
    """Type de relais reconnu dans un nom normalisé, ou None."""
    for type_, (motif, exclusion) in RELAIS.items():
        if motif.search(nom) and not (exclusion and exclusion.search(nom)):
            return type_
    return None


# ----------------------------------------------------------------- associations de parents
PARENTS = re.compile(r"\bparents? (et amis )?d ?eleves?\b")
DEPARTEMENTALE = re.compile(
    r"\bdepartementa(l|le|ux|les)\b|\bacademiques?\b|\bregiona(l|le|ux|les)\b|\bunion (nationale|des associations)\b"
    r"|\bcdpe\b|\bfederation (nationale|des conseils)\b|\bile de france\b"
)
FEDERATIONS = {
    "FCPE": re.compile(
        r"\bfcpe\b|\bf c p e\b|\bfederation des conseils de parents\b|\bconseil local (de|des) parents\b"
        r"|\bconseils? (de|des) parents d eleves\b"
    ),
    "PEEP": re.compile(
        r"\bpeep\b|\bp e e p\b|\bparents d eleves de l enseignement public\b"
        r"|\bprincipes laiques de neutralite scolaire\b|\ble parent premier educateur\b"
    ),
    "UNAAPE": re.compile(r"\bunaape\b|\bu n a a p e\b"),
    "APEL": re.compile(
        r"\bapel\b|\ba p e l\b|\bparents d eleves de l enseignement (libre|catholique)\b"
        r"|\bgarantir le libre choix de l ecole\b|\bgarantir le choix de l ecole\b"
    ),
}


_SANS_FEDERATION = re.compile(r"\bautonomes?\b|\bindependant(s|es|e)?\b|\bnon affiliee?s?\b")


def federation(titre: str, objet: str) -> str | None:
    """Fédération reconnue dans le titre, sinon dans l'objet (sauf association qui se dit autonome)."""
    textes = (titre,) if _SANS_FEDERATION.search(titre) else (titre, objet)
    for texte in textes:
        for nom, motif in FEDERATIONS.items():
            if motif.search(texte):
                return nom
    return None


_PREMIER_TITRE = re.compile(
    r"\becoles?\b|\bmaternelles?\b|\belementaires?\b|\bprimaires?\b|\bgroupes? scolaires?\b|\brpi\b|\bpolyvalente\b"
)
_PREMIER_OBJET = re.compile(
    r"\becoles? (maternelles?|elementaires?|primaires?|polyvalentes?|communales?|jules|jean)\b|\bmaternelles?\b"
    r"|\belementaires?\b|\bgroupes? scolaires?\b|\bpremier degre\b|\b1er degre\b"
)
_SECOND = re.compile(r"\bcolleges?\b|\blycees?\b|\bsecond degre\b|\blep\b|\blycee professionnel\b")


def niveau_scolaire(titre: str, objet: str) -> str:
    premier, second = _PREMIER_TITRE.search(titre), _SECOND.search(titre)
    if premier:
        return "premier_degre"
    if second:
        return "second_degre"
    premier, second = _PREMIER_OBJET.search(objet), _SECOND.search(objet)
    if premier:
        return "premier_degre"
    return "second_degre" if second else "indetermine"
