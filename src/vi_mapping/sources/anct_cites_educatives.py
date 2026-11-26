"""Cités éducatives : communes et quartiers prioritaires couverts."""

from __future__ import annotations

import csv
import io
from collections import defaultdict

from ..db import upsert
from ..outils.datagouv import Ressource, derniere
from .base import Compteurs, Contexte, communes_actuelles, connecteur

JEU = "60d315f1b58635c5d9fc9db4"


def lire(ctx: Contexte, motif: str) -> tuple[Ressource, list[dict[str, str]]]:
    r = derniere(ctx.http, JEU, motif)
    return r, list(csv.DictReader(io.StringIO(ctx.http.get(r.url).content.decode("utf-8-sig"))))


@connecteur("anct_cites_educatives", depend_de=["ign_admin_express", "anct_qpv", "cdc_qpv"])
def collecter(ctx: Contexte) -> Compteurs:
    departements = set(ctx.idf.departements)
    ressource, communes = lire(ctx, r"liste-cite-com")
    _, quartiers = lire(ctx, r"liste-cite-grpt")
    annee = int(ressource.maj[:4])

    noms: dict[str, str] = {}
    perimetre: dict[str, set[str]] = defaultdict(set)
    qpv: dict[str, set[str]] = defaultdict(set)
    for c in communes:
        if c["insee_com"][:2] in departements:
            noms[c["id_cite"]] = c["lib_cite"]
            perimetre[c["id_cite"]].add(c["insee_com"])
    for q in quartiers:
        if q["id_cite"] in noms and q["id_qpv"]:
            qpv[q["id_cite"]].add(f"qpv:{q['id_qpv']}")

    n = upsert(ctx.conn, "dispositif", [
        {
            "id": f"cite_educative:{cite}",
            "type": "cite_educative",
            "nom": nom,
            "communes": communes_actuelles(perimetre[cite]),
            "axe_education_alimentaire": None,
            "annee": annee,
            "niveau": None,
            **ctx.provenance(ressource.url),
        }
        for cite, nom in noms.items()
    ], ["id"])
    # Contour : réunion des quartiers couverts ; à défaut, des communes.
    sur_qpv = 0
    for cite in noms:
        sur_qpv += ctx.conn.execute(
            "UPDATE dispositif SET geom = u.g FROM (SELECT ST_Multi(ST_Union(geom)) AS g FROM dispositif "
            "WHERE type = 'qpv' AND id = ANY(%s)) u WHERE id = %s AND u.g IS NOT NULL",
            (sorted(qpv[cite]), f"cite_educative:{cite}"),
        ).rowcount
    ctx.conn.execute(
        "UPDATE dispositif d SET geom = (SELECT ST_Multi(ST_Union(c.geom)) FROM commune c "
        "WHERE c.code_insee = ANY(d.communes)), niveau = 'communes entières (quartiers non publiés)' "
        "WHERE d.type = 'cite_educative' AND d.geom IS NULL"
    )
    return {"cites_educatives": n, "contour_par_quartier": sur_qpv,
            "supprimees": ctx.purger("dispositif")}
