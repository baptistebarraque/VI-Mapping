"""Fichiers de l'API Melodi (Insee) : CSV compressés, une observation par ligne."""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterator

from .http import ClientHttp


def observations(http: ClientHttp, catalogue: str, nom: str) -> tuple[str, Iterator[dict[str, str]]]:
    """(URL du fichier, observations) du produit CSV le plus récent du jeu."""
    produits = [p for p in http.json(catalogue)["product"] if p["format"] == "CSV"]
    if not produits:
        raise LookupError(f"{catalogue} : aucun fichier CSV")
    url = max(produits, key=lambda p: p["id"])["accessURL"]
    return url, _lire(http, url, nom)


def _lire(http: ClientHttp, url: str, nom: str) -> Iterator[dict[str, str]]:
    chemin = http.telecharger(url, nom)
    with zipfile.ZipFile(chemin) as archive:
        membre = next(n for n in archive.namelist() if n.endswith("_data.csv"))
        with archive.open(membre) as f:
            yield from csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"), delimiter=";")
