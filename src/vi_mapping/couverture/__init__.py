"""Rapport de couverture : taux de remplissage par champ et par département."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg

from ..config import config_idf
from .champs import TABLES, Champ, Table

REGION = "IdF"


@dataclass(frozen=True)
class Mesure:
    table: Table
    total: dict[str, int]  # zone (IdF ou département) → lignes
    concernees: dict[str, dict[str, int]]  # champ → zone → lignes concernées
    remplies: dict[str, dict[str, int]]  # champ → zone → lignes remplies

    def taux(self, champ: Champ, zone: str) -> float | None:
        n = self.concernees[champ.code].get(zone, 0)
        return self.remplies[champ.code].get(zone, 0) / n if n else None


@dataclass(frozen=True)
class Rapport:
    genere_le: datetime
    departements: dict[str, str]
    mesures: list[Mesure]
    sources: list[dict[str, Any]]
    visites: list[dict[str, Any]]  # sites visités : type d'objet, statut, nombre

    @property
    def zones(self) -> list[str]:
        return [REGION, *self.departements]


def requete(table: Table) -> str:
    colonnes = ",\n".join(
        f"count(DISTINCT t.cle) FILTER (WHERE {c.parmi or 'true'}) AS n{i},\n"
        f"count(DISTINCT t.cle) FILTER (WHERE ({c.parmi or 'true'}) AND ({c.rempli})) AS c{i}"
        for i, c in enumerate(table.champs)
    )
    return (f"SELECT t.dep, count(DISTINCT t.cle) AS total,\n{colonnes}\nFROM ({table.source}) t\n"
            "GROUP BY GROUPING SETS ((t.dep), ())")


def mesurer(conn: psycopg.Connection[Any]) -> Rapport:
    mesures = []
    for table in TABLES:
        total: dict[str, int] = {}
        concernees: dict[str, dict[str, int]] = {c.code: {} for c in table.champs}
        remplies: dict[str, dict[str, int]] = {c.code: {} for c in table.champs}
        for r in conn.execute(requete(table)):  # type: ignore[arg-type]
            zone = r["dep"] or REGION
            total[zone] = r["total"]
            for i, c in enumerate(table.champs):
                concernees[c.code][zone], remplies[c.code][zone] = r[f"n{i}"], r[f"c{i}"]
        mesures.append(Mesure(table, total, concernees, remplies))
    sources = conn.execute(
        """SELECT s.code, s.libelle, s.methode::text, s.frequence, s.statut, s.verification,
                  max(r.fin) FILTER (WHERE r.statut = 'succes' AND NOT r.parametres ? 'communes') AS collecte
           FROM source_donnees s LEFT JOIN collecte_run r ON r.source = s.code
           GROUP BY s.code ORDER BY s.statut, s.code""").fetchall()
    visites = conn.execute(
        "SELECT objet_type, statut, count(*) AS n FROM crawl_site GROUP BY 1, 2 ORDER BY 1, 3 DESC").fetchall()
    return Rapport(datetime.now(UTC), config_idf().region.departements, mesures, sources, visites)
