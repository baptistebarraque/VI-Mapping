"""Élus municipaux et d'arrondissement (répertoire national des élus).

Lu en flux : date de naissance, sexe, nationalité et profession ne sont ni lus ni écrits.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from collections.abc import Iterator
from datetime import date
from typing import Any

from ..db import upsert
from ..outils.datagouv import Ressource, derniere
from ..outils.texte import normaliser, titre
from .base import Compteurs, Contexte, connecteur

JEU = "5c34c4d1634f4173183a64f1"
MUNICIPAUX = r"conseillers-municipaux"
ARRONDISSEMENTS = r"conseillers-d-?arrondissement|conseillers-darrondissement"


def lire(ctx: Contexte, ressource: Ressource) -> Iterator[dict[str, str]]:
    with ctx.http.flux(ressource.url) as r:
        yield from csv.DictReader((ligne.removeprefix("﻿") for ligne in r.iter_lines()), delimiter=";")


def jour(texte: str) -> date | None:
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", texte.strip())
    return date(int(m[3]), int(m[2]), int(m[1])) if m else None


def communes_du_secteur(libelle: str) -> list[str]:
    """« Paris 15Eme Secteur » -> 75115 ; le 1er secteur (Paris Centre) réunit les quatre premiers."""
    m = re.search(r"Paris (\d+)", libelle or "")
    if not m:
        return []
    n = int(m[1])
    return [f"751{i:02d}" for i in (range(1, 5) if n == 1 else [n])]


def identifiant(commune: str, nom: str, prenom: str, rang: int) -> str:
    cle = f"{commune}|{normaliser(nom)}|{normaliser(prenom)}|{rang}"
    return f"rne:{hashlib.sha1(cle.encode()).hexdigest()[:16]}"


@connecteur("rne", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    departements = set(ctx.idf.departements)
    connues = {r["code_insee"] for r in ctx.conn.execute("SELECT code_insee FROM commune")}
    elus: list[dict[str, Any]] = []
    homonymes: Counter[tuple[str, str, str]] = Counter()

    def ajouter(r: dict[str, str], commune: str, defaut: str, url: str) -> None:
        nom, prenom = r["Nom de l'élu"].strip(), r["Prénom de l'élu"].strip()
        cle = (commune, normaliser(nom), normaliser(prenom))
        homonymes[cle] += 1
        elus.append({
            "id": identifiant(commune, nom, prenom, homonymes[cle]),
            "commune": commune,
            "nom": titre(nom),
            "prenom": titre(prenom),
            "fonction": (r["Libellé de la fonction"].strip() or defaut).replace("’", "'"),
            "debut_mandat": jour(r["Date de début du mandat"]),
            **ctx.provenance(url),
        })

    municipaux = derniere(ctx.http, JEU, MUNICIPAUX)
    for r in lire(ctx, municipaux):
        if r["Code du département"] in departements and r["Code de la commune"] in connues:
            defaut = "Conseiller de Paris" if r["Code de la commune"] == "75056" else "Conseiller municipal"
            ajouter(r, r["Code de la commune"], defaut, municipaux.url)
    n_municipaux = len(elus)

    arrondissements = derniere(ctx.http, JEU, ARRONDISSEMENTS)
    for r in lire(ctx, arrondissements):
        if r["Code du département"] in departements:
            for commune in communes_du_secteur(r["Libellé du secteur"]):
                if commune in connues:
                    ajouter(r, commune, "Conseiller d'arrondissement", arrondissements.url)

    n = upsert(ctx.conn, "elu", elus, ["id"])
    return {"municipaux": n_municipaux, "arrondissements": len(elus) - n_municipaux, "ecrits": n,
            "supprimes": ctx.purger("elu")}
