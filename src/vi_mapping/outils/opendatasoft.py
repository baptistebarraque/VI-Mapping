"""Export complet d'un jeu de données Opendatasoft (API Explore v2.1)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from .http import ClientHttp


def exporter(
    http: ClientHttp, base: str, *, where: str | None = None, select: str | None = None
) -> list[dict[str, Any]]:
    """Toutes les lignes du jeu (`base` = URL du jeu dans le catalogue), sans la limite de pagination."""
    params = {"limit": "-1", "timezone": "Europe/Paris"}
    if where:
        params["where"] = where
    if select:
        params["select"] = select
    return json.loads(http.get(f"{base}/exports/json", params=params).content)


def url_fiche(base: str, champ: str, valeur: str) -> str:
    """URL de consultation d'un enregistrement précis (traçabilité)."""
    clause = quote(f'{champ}="{valeur}"')
    return f"{base}/records?where={clause}"


def grouper(http: ClientHttp, base: str, select: str, *, where: str | None = None, par: str | None = None
            ) -> list[dict[str, Any]]:
    """Petite requête d'agrégat (au plus 100 lignes)."""
    params = {"select": select, "limit": "100"}
    if where:
        params["where"] = where
    if par:
        params["group_by"] = par
    return http.json(f"{base}/records", params=params)["results"]
