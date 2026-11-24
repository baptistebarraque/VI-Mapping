"""Catalogue data.gouv.fr : retrouve la dernière version d'une ressource."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .http import ClientHttp

API = "https://www.data.gouv.fr/api/1/datasets"


@dataclass(frozen=True)
class Ressource:
    id: str
    titre: str
    url: str
    maj: str


def ressources(http: ClientHttp, jeu: str) -> list[Ressource]:
    d = http.json(f"{API}/{jeu}/")
    return [
        Ressource(r["id"], r["title"] or "", r["url"], (r.get("last_modified") or "")[:10])
        for r in d["resources"]
    ]


def derniere(http: ClientHttp, jeu: str, motif: str) -> Ressource:
    """Ressource la plus récente dont le titre ou l'URL correspond au motif (regex)."""
    trouvees = [r for r in ressources(http, jeu) if re.search(motif, r.titre) or re.search(motif, r.url)]
    if not trouvees:
        raise LookupError(f"data.gouv {jeu} : aucune ressource ne correspond à {motif!r}")
    return max(trouvees, key=lambda r: (r.maj, r.url))
