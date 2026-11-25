"""Restauration scolaire du 1er degré par commune : gestion, % bio, % EGalim (ma cantine).

Les taux viennent de la télédéclaration du restaurant, sinon de celle de la cuisine centrale qui le sert.
"""

from __future__ import annotations

import csv
import io
import re
import sys
from collections import defaultdict
from typing import Any

from ..outils.datagouv import ressources
from .base import Compteurs, Contexte, connecteur

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

SECTEUR = "Ecole primaire (maternelle et élémentaire)"
JEU_TELEDECLARATIONS = "6482ed2ee3f9ec5215b41828"
REGISTRE = "https://cellar-c2.services.clever-cloud.com/ma-cantine-egalim-prod/media/open_data/registre_cantines.csv"
MODES_CENTRAUX = {"CENTRAL_ALL", "CENTRAL_APPRO"}


def derniere_campagne(ctx: Contexte) -> tuple[int, str]:
    """(année, URL) de la dernière campagne de télédéclaration effectivement téléchargeable."""
    campagnes = {}
    for r in ressources(ctx.http, JEU_TELEDECLARATIONS):
        if m := re.search(r"campagne_td_(\d{4})\.csv", r.url):
            campagnes[int(m.group(1))] = r.url
    for annee in sorted(campagnes, reverse=True):
        try:
            ctx.http.requete("HEAD", campagnes[annee])
        except Exception as e:
            ctx.note(f"campagne {annee} indisponible ({type(e).__name__})")
            continue
        return annee, campagnes[annee]
    raise LookupError("aucune campagne de télédéclaration accessible")


def lire(contenu: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(contenu.decode("utf-8-sig"))))


def nombre(texte: str | None) -> float | None:
    try:
        return float(texte) if texte not in (None, "") else None
    except ValueError:
        return None


@connecteur("ma_cantine", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    annee, url_td = derniere_campagne(ctx)
    registre = lire(ctx.http.telecharger(REGISTRE, "ma_cantine_registre.csv").read_bytes())
    declarations = lire(ctx.http.telecharger(url_td, f"ma_cantine_td_{annee}.csv").read_bytes())

    par_id = {d["canteen_id"]: d for d in declarations}
    centrales = {
        d["canteen_siret"]: d for d in declarations
        if d["canteen_siret"] and d["teledeclaration_mode"] in MODES_CENTRAUX
    }
    centrales_id = {d["canteen_id"]: d for d in declarations if d["teledeclaration_mode"] in MODES_CENTRAUX}
    champ_declare = f"declaration_donnees_{annee}"

    cantines: dict[str, list[dict[str, Any]]] = defaultdict(list)
    heritees = 0
    for c in registre:
        if c["region"] != ctx.idf.region.code or c["economic_model"] != "public" or SECTEUR not in c["sector_list"]:
            continue
        td = par_id.get(c["id"])
        if td is None and c.get(champ_declare) != "False":
            td = centrales.get(c["central_producer_siret"]) or centrales_id.get(c["groupe_id"])
            heritees += td is not None
        commune = c["city_insee_code"]
        ligne = {
            "gestion": {"direct": "regie", "conceded": "concedee"}.get(c["management_type"]),
            "repas": nombre(c["daily_meal_count"]) or 1.0,
            "bio": nombre(td["teledeclaration_ratio_bio"]) if td else None,
            "egalim_hors_bio": nombre(td["teledeclaration_ratio_egalim_hors_bio"]) if td else None,
        }
        cantines[commune].append(ligne)
        if commune.startswith("751"):
            cantines["75056"].append(ligne)

    lignes = []
    for commune, liste in cantines.items():
        gestions = {c["gestion"] for c in liste} - {None}
        declarees = [c for c in liste if c["bio"] is not None]
        bio = moyenne(declarees, lambda c: c["bio"])
        egalim = moyenne(declarees, lambda c: c["bio"] + (c["egalim_hors_bio"] or 0))
        # Confiance réduite quand peu de restaurants de la commune sont couverts.
        couverture = len(declarees) / len(liste)
        lignes.append({
            "code_insee": commune,
            "cantine_gestion": None if not gestions else gestions.pop() if len(gestions) == 1 else "mixte",
            "cantine_nb": len(liste),
            "cantine_nb_declarations": len(declarees),
            "cantine_pct_bio": bio,
            "cantine_pct_egalim": egalim,
            "cantine_annee": annee if declarees else None,
            "provenance": ctx.provenance_json(
                url_td if declarees else REGISTRE,
                confiance=ctx.config.confiance * (0.75 + 0.25 * couverture),
            ),
        })
    n = ctx.enrichir("commune", lignes, "code_insee", "cantine")
    return {
        "campagne": annee, "restaurants": sum(len(v) for k, v in cantines.items() if k != "75056"),
        "taux_de_la_cuisine_centrale": heritees, "communes": n,
        "communes_avec_pct_bio": sum(ligne["cantine_pct_bio"] is not None for ligne in lignes),
    }


def moyenne(cantines: list[dict[str, Any]], valeur: Any) -> float | None:
    """Moyenne en %, pondérée par le nombre de repas quotidiens."""
    if not cantines:
        return None
    total = sum(c["repas"] for c in cantines)
    return round(min(100.0, 100 * sum(valeur(c) * c["repas"] for c in cantines) / total), 2)
