"""Restauration scolaire du 1er degré par commune : gestion, % bio, % EGalim, cuisines centrales (ma cantine).

Les taux viennent de la télédéclaration du restaurant, sinon de celle de la cuisine centrale qui le sert.
Les cuisines centrales sont celles que citent les restaurants satellites ; leur type (municipale, caisse des écoles,
intercommunale, privée) est déduit ensuite de la catégorie juridique Sirene (connecteur sirene_unites).
"""

from __future__ import annotations

import csv
import io
import re
import sys
from collections import defaultdict
from typing import Any

from ..db import upsert
from ..outils.datagouv import ressources
from ..outils.texte import propre
from .base import Compteurs, Contexte, connecteur

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

SECTEUR = "Ecole primaire (maternelle et élémentaire)"
JEU_TELEDECLARATIONS = "6482ed2ee3f9ec5215b41828"
REGISTRE = "https://cellar-c2.services.clever-cloud.com/ma-cantine-egalim-prod/media/open_data/registre_cantines.csv"
MODES_CENTRAUX = {"CENTRAL_ALL", "CENTRAL_APPRO"}
SATELLITE = "site_cooked_elsewhere"
SUR_PLACE = {"site", "central_serving"}
GESTION = {"direct": "regie", "conceded": "concedee"}


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


def siret_valide(texte: str | None) -> str | None:
    """Siret à 14 chiffres ; les cantines saisissent aussi des zéros, qui confondraient des cuisines sans rapport."""
    return texte if texte and re.fullmatch(r"(?!0{9})\d{14}", texte) else None


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
            "gestion": GESTION.get(c["management_type"]),
            "repas": nombre(c["daily_meal_count"]) or 1.0,
            "repas_connus": nombre(c["daily_meal_count"]),
            "bio": nombre(td["teledeclaration_ratio_bio"]) if td else None,
            "egalim_hors_bio": nombre(td["teledeclaration_ratio_egalim_hors_bio"]) if td else None,
            "production": c["production_type"],
            "centrale": siret_valide(c["central_producer_siret"]) if c["production_type"] == SATELLITE else None,
            "pat": [f"pat:{x.strip()}" for x in c["pat_list"].split(",") if x.strip()],
        }
        cantines[commune].append(ligne)
        if commune.startswith("751"):
            cantines["75056"].append(ligne)

    communes_idf = {r["code_insee"] for r in ctx.conn.execute("SELECT code_insee FROM commune")}
    lignes = [ligne_commune(ctx, commune, liste, annee, url_td) for commune, liste in cantines.items()]
    n = ctx.enrichir("commune", lignes, "code_insee", "cantine")
    cuisines = cuisines_centrales(ctx, cantines, registre, centrales, communes_idf, annee, url_td)
    # Type et catégorie juridique : renseignés par sirene_unites, à ne pas effacer.
    upsert(ctx.conn, "cuisine_centrale", cuisines, ["siret"], ne_pas_ecraser=["type", "categorie_juridique"])
    return {
        "campagne": annee, "restaurants": sum(len(v) for k, v in cantines.items() if k != "75056"),
        "taux_de_la_cuisine_centrale": heritees, "communes": n,
        "communes_avec_pct_bio": sum(ligne["cantine_pct_bio"] is not None for ligne in lignes),
        "cuisines_centrales": len(cuisines), "supprimees": ctx.purger("cuisine_centrale"),
    }


def ligne_commune(
    ctx: Contexte, commune: str, liste: list[dict[str, Any]], annee: int, url_td: str
) -> dict[str, Any]:
    gestions = {c["gestion"] for c in liste} - {None}
    declarees = [c for c in liste if c["bio"] is not None]
    bio = moyenne(declarees, lambda c: c["bio"])
    egalim = moyenne(declarees, lambda c: c["bio"] + (c["egalim_hors_bio"] or 0))
    # Confiance réduite quand peu de restaurants de la commune sont couverts.
    couverture = len(declarees) / len(liste)
    gerees = [c for c in liste if c["gestion"]]
    repas = [c["repas_connus"] for c in liste if c["repas_connus"]]
    # Cuisine centrale principale : celle qui livre le plus de repas aux satellites de la commune
    livres: dict[str, float] = defaultdict(float)
    for c in liste:
        if c["centrale"]:
            livres[c["centrale"]] += c["repas"]
    return {
        "code_insee": commune,
        "cantine_gestion": None if not gestions else next(iter(gestions)) if len(gestions) == 1 else "mixte",
        "cantine_nb": len(liste),
        "cantine_nb_declarations": len(declarees),
        "cantine_pct_bio": bio,
        "cantine_pct_egalim": egalim,
        "cantine_annee": annee if declarees else None,
        "cantine_nb_satellites": sum(c["production"] == SATELLITE for c in liste),
        "cantine_nb_sur_place": sum(c["production"] in SUR_PLACE for c in liste),
        "cantine_part_regie": round(sum(c["gestion"] == "regie" for c in gerees) / len(gerees), 3) if gerees else None,
        "cantine_repas_jour": round(sum(repas)) if repas else None,
        "cuisine_centrale_siret": max(livres, key=lambda s: (livres[s], s)) if livres else None,
        "cantine_pat": sorted({p for c in liste for p in c["pat"]}),
        "provenance": ctx.provenance_json(
            url_td if declarees else REGISTRE,
            confiance=ctx.config.confiance * (0.75 + 0.25 * couverture),
        ),
    }


def cuisines_centrales(
    ctx: Contexte, cantines: dict[str, list[dict[str, Any]]], registre: list[dict[str, str]],
    centrales: dict[str, dict[str, str]], communes_idf: set[str], annee: int, url_td: str,
) -> list[dict[str, Any]]:
    """Cuisines centrales citées par les restaurants satellites d'Île-de-France."""
    servies: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for commune, liste in cantines.items():
        if commune != "75056":
            for c in liste:
                if c["centrale"]:
                    servies[c["centrale"]].append(c)
    inscrites = {c["siret"]: c for c in registre if c["siret"]}
    lignes = []
    for siret, liste in servies.items():
        td, fiche = centrales.get(siret) or {}, inscrites.get(siret) or {}
        nom = td.get("canteen_name") or fiche.get("name") or f"Cuisine centrale {siret}"
        commune = td.get("canteen_city_insee_code") or fiche.get("city_insee_code")
        gestion = td.get("canteen_management_type") or fiche.get("management_type") or ""
        bio = nombre(td.get("teledeclaration_ratio_bio"))
        hors_bio = nombre(td.get("teledeclaration_ratio_egalim_hors_bio"))
        repas = [c["repas_connus"] for c in liste if c["repas_connus"]]
        lignes.append({
            "siret": siret, "nom": propre(nom) or f"Cuisine centrale {siret}", "type": "inconnu",
            "categorie_juridique": None,
            "commune": commune if commune in communes_idf else None,
            "gestion": GESTION.get(gestion),
            "nb_cantines": len(liste),
            "repas_jour": round(sum(repas)) if repas else None,
            "pct_bio": None if bio is None else round(min(100.0, 100 * bio), 2),
            "pct_egalim": None if bio is None else round(min(100.0, 100 * (bio + (hors_bio or 0))), 2),
            "annee": annee if bio is not None else None,
            # Cuisine absente du registre et des déclarations : seul son SIRET est connu.
            **ctx.provenance(url_td if td else REGISTRE, confiance=ctx.config.confiance * (1 if td or fiche else 0.8)),
        })
    return lignes


def moyenne(cantines: list[dict[str, Any]], valeur: Any) -> float | None:
    """Moyenne en %, pondérée par le nombre de repas quotidiens."""
    if not cantines:
        return None
    total = sum(c["repas"] for c in cantines)
    return round(min(100.0, 100 * sum(valeur(c) * c["repas"] for c in cantines) / total), 2)
