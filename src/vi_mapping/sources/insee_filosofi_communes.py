"""Revenus des communes non découpées en IRIS (Filosofi communal), où IRIS et commune se confondent."""

from __future__ import annotations

from collections import defaultdict

from psycopg.types.json import Jsonb

from ..outils.melodi import observations
from .base import Compteurs, Contexte, connecteur

MESURES = {"MED_SL": "revenu_median", "PR_MD60": "taux_pauvrete"}


@connecteur("insee_filosofi_communes", depend_de=["ign_iris", "insee_filosofi_iris"])
def collecter(ctx: Contexte) -> Compteurs:
    departements = set(ctx.idf.departements)
    url, lignes = observations(ctx.http, ctx.config.url, "insee_filosofi_communes.zip")
    valeurs: dict[str, dict[str, float]] = defaultdict(dict)
    annee = 0
    for o in lignes:
        mesure = MESURES.get(o["FILOSOFI_MEASURE"])
        if mesure and o["GEO_OBJECT"] == "COM" and o["OBS_VALUE"] and o["GEO"][:2] in departements:
            annee = int(o["TIME_PERIOD"])
            valeurs[o["GEO"]][mesure] = float(o["OBS_VALUE"])
    ctx.conn.execute(
        "UPDATE territoire_social SET revenu_median = NULL, taux_pauvrete = NULL, annee_revenus = NULL, "
        "provenances = provenances - 'revenus' WHERE provenances->'revenus'->>'source' = %s", (ctx.code,)
    )
    prov = Jsonb(ctx.provenance_json(url))
    n = 0
    for commune, v in valeurs.items():
        n += ctx.conn.execute(
            "UPDATE territoire_social SET revenu_median = %s, taux_pauvrete = %s, annee_revenus = %s, "
            "provenances = provenances || jsonb_build_object('revenus', %s::jsonb) "
            "WHERE iris = %s AND revenu_median IS NULL",
            (v.get("revenu_median"), v.get("taux_pauvrete"), annee, prov, f"{commune}0000"),
        ).rowcount
    return {"millesime": annee, "communes_publiees": len(valeurs), "iris": n}
