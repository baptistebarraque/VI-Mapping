"""Référentiel V.i : faits publics relevés à la main, chacun avec sa source (config/referentiel/*.csv).

- PAT du livret DRIAAF : axes (restauration collective, éducation alimentaire), priorités, précision du périmètre
  et communes rattachées hors du périmètre France PAT. Les PAT connus de France PAT sont complétés, jamais remplacés.
- Soutiens de la région, des départements et des intercommunalités (score de 0 à 2).
- Communes lauréates de l'appel à projets MGP « Restauration collective bio et locale ».
- Syndicats intercommunaux de restauration et leurs communes membres (liste partielle).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..config import DOSSIER_CONFIG
from ..db import upsert
from .base import Compteurs, Contexte, connecteur

DOSSIER = DOSSIER_CONFIG / "referentiel"


def lire(nom: str, dossier: Path = DOSSIER) -> list[dict[str, str]]:
    with open(dossier / nom, encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def booleen(texte: str) -> bool | None:
    return {"oui": True, "non": False}.get(texte.lower())


def entier(texte: str) -> int | None:
    return int(texte) if texte.isdigit() else None


@connecteur("referentiel_vi", depend_de=["ign_admin_express", "banatic", "france_pat"])
def collecter(ctx: Contexte) -> Compteurs:
    dossier = Path(ctx.options.get("dossier", DOSSIER))
    communes = {
        r["code_insee"]: r for r in ctx.conn.execute(
            "SELECT code_insee, departement, epci_siren, ept_siren, commune_mere FROM commune")
    }
    compte: Compteurs = {}
    nouveaux: list[dict[str, Any]] = []

    # ------------------------------------------------------------- PAT du livret DRIAAF
    perimetres: dict[str, set[str]] = defaultdict(set)
    for r in lire("pat_driaaf_communes.csv", dossier):
        if r["code_insee"] in communes:
            perimetres[r["pat_id"]].add(r["code_insee"])
    france_pat = {
        r["id"]: set(r["communes"]) for r in ctx.conn.execute("SELECT id, communes FROM dispositif WHERE type = 'pat'")
    }
    completes = []
    for p in lire("pat_driaaf.csv", dossier):
        commun = {
            "axe_restauration_collective": booleen(p["axe_restauration_collective"]),
            "axe_education_verifie": booleen(p["axe_education_alimentaire"]),
            "priorites": p["priorites"] or None,
            "perimetre_precision": p["perimetre_precision"] or None,
        }
        cible = f"pat:{p['france_pat_id']}" if p["france_pat_id"] else None
        if cible in france_pat:
            deja = france_pat[cible]
            # Arrondissements de Paris : couverts par la commune mère
            ajoutees = sorted(c for c in perimetres[p["id"]] - deja if communes[c]["commune_mere"] not in deja)
            completes.append({
                "id": cible, **commun, "communes_ajoutees": ajoutees,
                "provenance": ctx.provenance_json(p["url"]),
            })
        else:
            nouveaux.append(_dispositif(
                ctx, f"referentiel:{p['id']}", "pat", p["nom"], sorted(perimetres[p["id"]]), p["url"],
                confiance=0.6 if "vérifier" in p["statut"].lower() else None,
                axe_education_alimentaire=commun["axe_education_verifie"], niveau=p["niveau"] or p["statut"] or None,
                niveau_num=entier(p["niveau_num"]), **commun,
            ))
    compte["pat_completes"] = ctx.enrichir("dispositif", completes, "id", "referentiel")
    compte["pat_ajoutes"] = len(nouveaux)

    # ------------------------------------------------------------- soutiens territoriaux
    for s in lire("soutiens.csv", dossier):
        cle = {"region": None, "departement": "departement", "epci": "epci_siren", "ept": "ept_siren"}[
            s["perimetre_type"]]
        perimetre = sorted(c for c, x in communes.items() if cle is None or x[cle] == s["perimetre"])
        nouveaux.append(_dispositif(ctx, f"soutien:{s['id']}", "soutien_territorial", s["territoire"], perimetre,
                                    s["url"], echelon=s["echelon"], score=entier(s["score"]),
                                    priorites=s["dispositif"] or None))
    compte["soutiens"] = sum(d["type"] == "soutien_territorial" for d in nouveaux)

    # ------------------------------------------------------------- lauréats AAP MGP, syndicats de restauration
    for r in lire("laureats_aap_mgp.csv", dossier):
        if r["code_insee"] in communes:
            nouveaux.append(_dispositif(ctx, f"aap_mgp:{r['code_insee']}", "laureat_aap_mgp",
                                        f"Lauréat AAP MGP « Restauration collective bio et locale » : {r['commune']}",
                                        [r["code_insee"]], r["url"], editions=r["editions"]))
    compte["laureats_aap_mgp"] = sum(d["type"] == "laureat_aap_mgp" for d in nouveaux)
    membres: dict[str, list[str]] = defaultdict(list)
    urls: dict[str, str] = {}
    for r in lire("syndicats_restauration.csv", dossier):
        if r["code_insee"] in communes:
            membres[r["syndicat"]].append(r["code_insee"])
            urls[r["syndicat"]] = r["url"]
    for nom, codes in membres.items():
        nouveaux.append(_dispositif(ctx, f"syndicat:{nom}", "syndicat_restauration", nom, sorted(codes), urls[nom]))
    compte["syndicats"] = len(membres)

    upsert(ctx.conn, "dispositif", nouveaux, ["id"])
    ctx.conn.execute(
        "UPDATE dispositif d SET geom = (SELECT ST_Multi(ST_Union(c.geom)) FROM commune c "
        "WHERE c.code_insee = ANY(d.communes)) WHERE d.source = %s", (ctx.code,)
    )
    compte["supprimes"] = ctx.purger("dispositif")
    return compte


def _dispositif(
    ctx: Contexte, id_: str, type_: str, nom: str, communes: list[str], url: str, *, confiance: float | None = None,
    **champs: Any,
) -> dict[str, Any]:
    return {
        "id": id_, "type": type_, "nom": nom, "communes": communes, "axe_education_alimentaire": None,
        "annee": None, "niveau": None, "niveau_num": None, "axe_restauration_collective": None,
        "axe_education_verifie": None, "priorites": None, "perimetre_precision": None, "communes_ajoutees": [],
        "echelon": None, "score": None, "editions": None, **champs, **ctx.provenance(url, confiance=confiance),
    }
