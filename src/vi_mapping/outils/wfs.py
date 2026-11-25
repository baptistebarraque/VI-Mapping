"""Lecture paginée du WFS de la Géoplateforme IGN."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from .http import ClientHttp

WFS = "https://data.geopf.fr/wfs/ows"


def entites(
    http: ClientHttp, couche: str, filtre: str, *, tri: str, page: int = 500
) -> Iterator[tuple[dict[str, Any], str]]:
    """Donne (attributs, géométrie GeoJSON en texte) ; `tri` garantit une pagination stable."""
    debut = 0
    while True:
        d = http.json(WFS, params={
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": couche,
            "OUTPUTFORMAT": "application/json", "SRSNAME": "EPSG:4326", "CQL_FILTER": filtre,
            "SORTBY": tri, "COUNT": page, "STARTINDEX": debut,
        })
        for f in d["features"]:
            yield f["properties"], json.dumps(f["geometry"])
        debut += len(d["features"])
        if not d["features"] or debut >= d["numberMatched"]:
            return


def url_entite(couche: str, champ: str, valeur: str) -> str:
    """URL de consultation d'une entité précise (traçabilité)."""
    return (
        f"{WFS}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES={couche}"
        f"&OUTPUTFORMAT=application/json&CQL_FILTER={champ}='{valeur}'"
    )
