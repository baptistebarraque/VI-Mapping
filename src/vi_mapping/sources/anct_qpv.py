"""Quartiers prioritaires de la politique de la ville (périmètres 2024)."""

from __future__ import annotations

import json
from typing import Any

from ..db import upsert
from ..outils.opendatasoft import exporter, url_fiche
from .base import Compteurs, Contexte, connecteur


def ligne_qpv(
    code: str, nom: str, communes: list[str], forme: dict[str, Any] | None, provenance: dict[str, Any]
) -> dict[str, Any]:
    """Ligne de la table dispositif ; `forme` est une entité ou une géométrie GeoJSON."""
    geometrie = forme.get("geometry", forme) if forme else None
    if geometrie and geometrie["type"] == "Polygon":
        geometrie = {"type": "MultiPolygon", "coordinates": [geometrie["coordinates"]]}
    return {
        "id": f"qpv:{code}",
        "type": "qpv",
        "nom": nom,
        "communes": communes,
        "axe_education_alimentaire": None,
        "annee": 2024,
        "niveau": None,
        "geom": json.dumps(geometrie) if geometrie else None,
        **provenance,
    }


@connecteur("anct_qpv", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    base = ctx.config.url
    quartiers = exporter(ctx.http, base)
    lignes = [
        ligne_qpv(q["code_qp"], q["lib_qp"], list(q["insee_com"] or []), q["geo_shape"],
                  ctx.provenance(url_fiche(base, "code_qp", q["code_qp"])))
        for q in quartiers if q["geo_shape"]
    ]
    n = upsert(ctx.conn, "dispositif", lignes, ["id"])
    return {"qpv": n, "sans_contour": len(quartiers) - len(lignes),
            "supprimes": ctx.purger("dispositif")}
