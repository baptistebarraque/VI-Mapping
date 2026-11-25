"""Accueils périscolaires nommés avec leur adresse sur les sites des mairies.

Seuls le nom et l'adresse du lieu sont relevés : ni nom de directeur, ni téléphone, ni e-mail.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..outils import motifs
from ..outils.texte import adresse_sans_personne, normaliser, propre, sans_contact
from . import themes
from .page import Contenu

ADRESSE = re.compile(
    r"\b\d{1,4}\s?(?:bis|ter|quater|[A-D])?\s?(?:[-/]\s?\d{1,4})?,?\s+"
    r"(?:rue|avenue|av\.?|boulevard|bd\.?|place|pl\.?|allée|allee|chemin|impasse|square|route|cours|passage|quai"
    r"|sentier|sente|villa|mail|promenade|esplanade|clos|ruelle|voie|rond-point)\b[^,;|•()\n]{2,60}",
    re.I,
)
_PERSONNE = re.compile(r"\b(directeur|directrice|responsable|referente?|contact|mme|madame|monsieur|m)\b")
_ACTION = re.compile(  # phrases et rubriques, pas des noms de lieux
    r"\b(inscri\w*|reserv\w*|tarifs?|reglement|factur\w*|telecharg\w*|dossiers?|comment|horaires?|calendrier|programmes?"
    r"|projet|menus?|nos|les|votre|vos|quels?|recrut\w*|recherche|demande\w*|fermeture|ouverture|annul\w*|paiement"
    r"|adresses?|listes?|frequente\w*|avant|apres|une|un|annuaires?|contacts?|informations?|poles?|hotel de ville"
    r"|mini sejours?)\b|^(centres|accueils|services|activites|enfance) "
)
_GENERIQUE = re.compile(
    r"^(les? |l )?(accueils?|centres?|services?) (de loisirs?|peri ?scolaires?)"
    r"( (maternels?|elementaires?|municipa(l|ux)))?$"
)
_MUNICIPAL = re.compile(
    r"\b(accueils?|centres?) de loisirs? (maternels? |elementaires? |primaires? )?municipa(l|ux)\b"
    r"|\bgere(s|e)? par la (ville|commune|mairie)\b|\bservices? municipa(l|ux)\b"
    r"|\b(service|direction|pole) [a-z ]{0,30}de la (ville|mairie|commune)\b"
)
LONGUEUR_MAX = 90


@dataclass(frozen=True)
class AccueilTrouve:
    nom: str
    adresse: str
    url: str
    soir: bool | None
    mercredi: bool | None
    municipal: bool


def lire_accueils(c: Contenu, url: str) -> list[AccueilTrouve]:
    """Accueils de la page : fiche consacrée à un lieu, ou liste « nom, puis adresse »."""
    presents = themes.themes_de(c.texte)
    soir = True if "periscolaire_soir" in presents else None
    mercredi = True if "periscolaire_mercredi" in presents else None
    municipal = bool(_MUNICIPAL.search(c.texte))

    trouves: dict[tuple[str, str], AccueilTrouve] = {}

    def ajouter(nom: str, brute: str) -> None:
        adresse = adresse_sans_personne(brute)
        if adresse and nom:
            cle = (normaliser(nom), normaliser(adresse))
            trouves.setdefault(cle, AccueilTrouve(nom, adresse, url, soir, mercredi, municipal))

    for i, ligne in enumerate(c.lignes):
        nom = nom_de_lieu(ligne)
        if nom is None:
            continue
        for suivante in c.lignes[i : i + 5]:
            if suivante is not ligne and nom_de_lieu(suivante):
                break  # un autre accueil commence
            if m := ADRESSE.search(suivante):
                ajouter(nom, m.group())
                break

    if not trouves:  # fiche : le nom est dans le titre de la page
        nom = nom_de_lieu(re.split(r"\s+[|–—-]\s+", c.titre)[0])
        adresses = [m.group() for m in (ADRESSE.search(x) for x in c.lignes) if m]
        if nom and len({normaliser(a) for a in adresses}) == 1:
            ajouter(nom, adresses[0])
    return list(trouves.values())


def nom_de_lieu(ligne: str) -> str | None:
    """La ligne est-elle le nom d'un accueil (et non une phrase ou une rubrique) ?"""
    texte = propre(ADRESSE.split(ligne)[0]) or ""
    texte = re.split(r"\s+[:|•]\s+|\s:|:\s", texte)[0].strip(" ,;:-–•")
    if not 8 <= len(texte) <= LONGUEUR_MAX:
        return None
    n = normaliser(texte)
    if (
        not motifs.est_accueil(n) or _PERSONNE.search(n) or _ACTION.search(n) or texte.endswith(".")
        or _GENERIQUE.match(n) or len(n.split()) > 11
    ):
        return None
    return sans_contact(texte)
