"""Contours IRIS de l'Île-de-France (maille des données sociales)."""

from __future__ import annotations

from ..db import upsert
from ..outils.wfs import entites, url_entite
from .base import Compteurs, Contexte, connecteur

COUCHE = "STATISTICALUNITS.IRIS:contours_iris"


@connecteur("ign_iris", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    communes = {r["code_insee"] for r in ctx.conn.execute("SELECT code_insee FROM commune")}
    lignes, ignores = [], 0
    for dep in ctx.idf.departements:
        for p, geom in entites(ctx.http, COUCHE, f"code_insee LIKE '{dep}%'", tri="code_iris"):
            if p["code_insee"] not in communes:
                ignores += 1
                continue
            lignes.append({
                "iris": p["code_iris"],
                "nom": p["nom_iris"],
                "type_iris": p["type_iris"],
                "commune": p["code_insee"],
                "geom": geom,
                **ctx.provenance(url_entite(COUCHE, "code_iris", p["code_iris"])),
            })
    n = upsert(ctx.conn, "territoire_social", lignes, ["iris"])
    return {"iris": n, "commune_inconnue": ignores,
            "supprimes": ctx.purger("territoire_social")}
