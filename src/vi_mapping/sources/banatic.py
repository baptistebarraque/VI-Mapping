"""Intercommunalités : EPCI et établissement public territorial (EPT) de chaque commune, contact de leur siège.

Les syndicats de restauration collective sont gardés avec leurs communes membres.
"""

from __future__ import annotations

import io
import re
from typing import Any

import openpyxl
from psycopg.types.json import Jsonb

from ..db import upsert
from ..outils.texte import email_de_contact, normaliser, propre, site_web, telephone
from .base import Compteurs, Contexte, connecteur

FISCALITE_PROPRE = {"CC", "CA", "CU", "METRO", "MET69"}
_RESTAURATION = re.compile(r"\b(restauration|repas|cantines?|cuisines?)\b")
_AUTRE_RESTAURATION = re.compile(r"\b(riviere|rivieres|berges|milieux|patrimoine|terrains|eau|eaux|bassin)\b")


def est_restauration(nom: str) -> bool:
    """« SI pour la restauration des villes » oui, « restauration des rivières » non."""
    n = normaliser(nom)
    return bool(_RESTAURATION.search(n)) and not _AUTRE_RESTAURATION.search(n)


def contact(valeurs: dict[str, Any]) -> dict[str, str | None]:
    """Contact du siège d'un groupement ; « a@x.fr et b@x.fr » : la première adresse."""
    return {
        "telephone": telephone(valeurs["Téléphone du siège"]) or telephone(valeurs["Téléphone administrative"]),
        "email": email_de_contact(propre(valeurs["Courriel du siège"])),
        "site_web": site_web(propre(valeurs["Site internet du siège"])),
    }


@connecteur("banatic", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    contenu = ctx.http.get(ctx.config.url).content
    feuille = openpyxl.load_workbook(io.BytesIO(contenu), read_only=True).worksheets[0]
    lignes = feuille.iter_rows(values_only=True)
    entete = [str(c).strip() for c in next(lignes)]
    i_siren, i_nom = entete.index("N° SIREN"), entete.index("Nom du groupement")
    i_nature, i_membre = entete.index("Nature juridique"), entete.index("Siren membre")
    codes = {r["siren"]: r["code_insee"] for r in ctx.conn.execute(
        "SELECT siren, code_insee FROM commune WHERE siren IS NOT NULL")}
    organismes: dict[str, dict[str, Any]] = {}

    epci: dict[str, tuple[str, str]] = {}
    ept: dict[str, tuple[str, str]] = {}
    for ligne in lignes:
        membre = str(ligne[i_membre] or "").strip()[:9]
        groupement = (str(ligne[i_siren]).strip(), str(ligne[i_nom]).strip())
        nature = str(ligne[i_nature] or "").strip()
        if nature in FISCALITE_PROPRE:
            epci[membre] = groupement
        elif nature == "EPT":
            ept[membre] = groupement
        type_ = ("epci" if nature in FISCALITE_PROPRE else "ept" if nature == "EPT"
                 else "syndicat_restauration" if est_restauration(groupement[1]) else None)
        if type_ is None or membre not in codes:
            continue
        valeurs = dict(zip(entete, ligne, strict=False))
        fiche = organismes.setdefault(groupement[0], {
            "siren": groupement[0], "type": type_, "nom": groupement[1],
            "departement": str(valeurs["Département"] or "")[:2] or None, "communes": [], **contact(valeurs),
            "formulaire": None, **ctx.provenance(),
        })
        fiche["communes"] = sorted({*fiche["communes"], codes[membre]})
    if not epci:
        raise RuntimeError("aucun EPCI à fiscalité propre lu : format Banatic modifié ?")

    prov = Jsonb(ctx.provenance_json())
    n_epci = n_ept = 0
    for siren, (code, nom) in epci.items():
        n_epci += ctx.conn.execute(
            "UPDATE commune SET epci_siren = %s, epci_nom = %s, "
            "provenances = provenances || jsonb_build_object('intercommunalite', %s::jsonb) WHERE siren = %s",
            (code, nom, prov, siren),
        ).rowcount
    ctx.conn.execute("UPDATE commune SET ept_siren = NULL, ept_nom = NULL")
    for siren, (code, nom) in ept.items():
        n_ept += ctx.conn.execute(
            "UPDATE commune SET ept_siren = %s, ept_nom = %s WHERE siren = %s", (code, nom, siren)
        ).rowcount
    upsert(ctx.conn, "organisme", organismes.values(), ["siren"])
    return {
        "communes_avec_epci": n_epci, "communes_avec_ept": n_ept, "organismes": len(organismes),
        "organismes_avec_email": sum(o["email"] is not None for o in organismes.values()),
        "syndicats_restauration": sum(o["type"] == "syndicat_restauration" for o in organismes.values()),
        "supprimes": ctx.purger("organisme"),
    }
