"""Familles et familles avec enfants de moins de 25 ans, par IRIS (recensement)."""

from __future__ import annotations

from collections import defaultdict

from ..outils.melodi import observations
from .base import Compteurs, Contexte, connecteur

AVEC_ENFANTS = {"CH1_Y_LT25", "CH2_Y_LT25", "CH3_Y_LT25", "CH_GE4_Y_LT25"}


@connecteur("insee_familles_iris", depend_de=["ign_iris"])
def collecter(ctx: Contexte) -> Compteurs:
    departements = set(ctx.idf.departements)
    url, lignes = observations(ctx.http, ctx.config.url, "insee_familles_iris.zip")
    total: dict[str, float] = {}
    enfants: dict[str, float] = defaultdict(float)
    annee = 0
    for o in lignes:
        if o["RP_MEASURE"] != "NBFAM" or o["TFN"] != "_T" or o["GEO"][:2] not in departements:
            continue
        annee = int(o["TIME_PERIOD"])
        # Commune non découpée : publiée au code commune, dont l'IRIS porte le suffixe 0000.
        iris = o["GEO"] if o["GEO_OBJECT"] == "IRIS" else f"{o['GEO']}0000"
        if o["NCH"] == "_T":
            total[iris] = float(o["OBS_VALUE"])
        elif o["NCH"] in AVEC_ENFANTS:
            enfants[iris] += float(o["OBS_VALUE"])
    n = ctx.enrichir("territoire_social", [
        {
            "iris": iris,
            "familles": round(v),
            "familles_avec_enfants": round(enfants[iris]),
            "annee_familles": annee,
            "provenance": ctx.provenance_json(url),
        }
        for iris, v in total.items()
    ], "iris", "familles")
    return {"millesime": annee, "iris": n}
