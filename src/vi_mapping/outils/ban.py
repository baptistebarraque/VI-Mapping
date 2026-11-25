"""Géocodage par lots avec la Base adresse nationale (Géoplateforme), avec cache en base.

Seules des adresses d'établissements ou de sièges d'associations sont envoyées, jamais de nom.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import psycopg

from ..db import upsert
from .http import ClientHttp
from .texte import normaliser

URL = "https://data.geopf.fr/geocodage/search/csv"
LOT = 2000
PRECIS = {"housenumber", "street", "locality"}


@dataclass(frozen=True)
class Adresse:
    adresse: str
    code_postal: str = ""
    code_insee: str = ""

    @property
    def cle(self) -> str:
        return f"{normaliser(self.adresse)}|{self.code_postal}|{self.code_insee}"


@dataclass(frozen=True)
class Position:
    lon: float
    lat: float
    score: float
    type: str          # housenumber, street, locality, municipality
    code_insee: str
    libelle: str

    @property
    def confiance(self) -> float:
        """De 0 à 1 : score BAN pondéré par la finesse du résultat."""
        finesse = {"housenumber": 1.0, "street": 0.85, "locality": 0.7, "municipality": 0.4}
        return round(min(1.0, self.score * finesse.get(self.type, 0.4)), 2)


def geocoder(
    conn: psycopg.Connection[Any], http: ClientHttp, adresses: Iterable[Adresse]
) -> dict[Adresse, Position]:
    """Position de chaque adresse trouvée. Les réponses (même vides) sont mises en cache."""
    voulues = {a.cle: a for a in adresses if normaliser(a.adresse)}
    connues = {
        r["cle"]: r
        for r in conn.execute("SELECT * FROM geocodage_cache WHERE cle = ANY(%s)", (list(voulues),))
    }
    manquantes = [a for cle, a in voulues.items() if cle not in connues]
    for i in range(0, len(manquantes), LOT):
        lignes = _appeler(http, manquantes[i : i + LOT])
        upsert(conn, "geocodage_cache", lignes, ["cle"])
        connues.update({ligne["cle"]: ligne for ligne in lignes})
    return {
        a: Position(r["lon"], r["lat"], r["score"], r["type"], r["code_insee"], r["libelle"])
        for cle, a in voulues.items()
        if (r := connues[cle])["lon"] is not None
    }


def _appeler(http: ClientHttp, adresses: list[Adresse]) -> list[dict[str, Any]]:
    tampon = io.StringIO()
    sortie = csv.writer(tampon)
    sortie.writerow(["cle", "adresse", "code_postal", "code_insee"])
    for a in adresses:
        # 75056 (Paris entier) n'est pas un code de la BAN, qui raisonne par arrondissement.
        sortie.writerow([a.cle, a.adresse, a.code_postal, "" if a.code_insee == "75056" else a.code_insee])
    colonnes = ["longitude", "latitude", "result_score", "result_type", "result_citycode", "result_label"]
    r = http.requete(
        "POST",
        URL,
        files={"data": ("adresses.csv", tampon.getvalue().encode(), "text/csv")},
        data={"columns": "adresse", "citycode": "code_insee", "postcode": "code_postal",
              "result_columns": colonnes},
    )
    resultat = []
    for ligne in csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))):
        trouve = bool(ligne["longitude"] and ligne["latitude"])
        resultat.append({
            "cle": ligne["cle"],
            "lon": float(ligne["longitude"]) if trouve else None,
            "lat": float(ligne["latitude"]) if trouve else None,
            "score": float(ligne["result_score"]) if trouve else None,
            "type": ligne["result_type"] or None if trouve else None,
            "code_insee": (ligne["result_citycode"] or None) if trouve else None,
            "libelle": (ligne["result_label"] or None) if trouve else None,
        })
    if len(resultat) != len(adresses):
        raise RuntimeError(f"BAN : {len(resultat)} réponses pour {len(adresses)} adresses")
    return resultat
