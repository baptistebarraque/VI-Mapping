"""Export complet d'un jeu de données Opendatasoft (API Explore v2.1)."""

from __future__ import annotations

import json
from typing import Any

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
