"""Relance de l'analyse d'une école : site de sa mairie, puis calculs.

La visite suit les mêmes règles que la campagne mensuelle : délai entre deux visites, plafond sans VI_CONTACT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import psycopg

from .db import connexion
from .scrapers.campagne import DELAI_ENTRE_VISITES
from .sources.base import calculer_tout, executer

# faite : site visité ; recente : déjà vu il y a moins de 25 jours ; plafond : quota du mois atteint sans VI_CONTACT
Visite = Literal["faite", "recente", "plafond", "sans_site", "echec"]


class EcoleInconnue(Exception):
    pass


@dataclass
class Bilan:
    uai: str
    visite: Visite
    echecs: list[str] = field(default_factory=list)


def sites(conn: psycopg.Connection[Any], uai: str, depuis: datetime) -> tuple[list[str], list[str]]:
    """Communes de l'école qui ont un site (la sienne, puis la commune mère) : (à visiter, vues depuis `depuis`).

    Un site partagé par plusieurs communes est vu dès qu'il l'a été pour l'une d'elles.
    """
    if conn.execute("SELECT 1 FROM ecole WHERE uai = %s", (uai,)).fetchone() is None:
        raise EcoleInconnue(uai)
    lignes = conn.execute(
        """SELECT c.code_insee, EXISTS (
                    SELECT 1 FROM crawl_site v JOIN commune o ON o.code_insee = v.objet_id
                    WHERE v.objet_type = 'commune' AND o.site_web = c.site_web AND v.visite_le >= %s) AS vue
           FROM ecole e JOIN commune s ON s.code_insee = e.commune
           JOIN commune c ON c.code_insee IN (s.code_insee, s.commune_mere)
           WHERE e.uai = %s AND c.site_web IS NOT NULL ORDER BY c.code_insee = s.code_insee DESC""",
        (depuis, uai),
    ).fetchall()
    return [r["code_insee"] for r in lignes if not r["vue"]], [r["code_insee"] for r in lignes if r["vue"]]


def relancer(uai: str) -> Bilan:
    debut = datetime.now(UTC)
    with connexion() as conn:
        a_voir, vues = sites(conn, uai, debut - DELAI_ENTRE_VISITES)
    visite: Visite = "recente" if vues else "sans_site"
    echecs: list[str] = []
    if a_voir:
        if executer("sites_mairies", options={"communes": a_voir}) == "echec":
            visite, echecs = "echec", ["sites_mairies"]
        else:
            with connexion() as conn:
                faites = sites(conn, uai, debut)[1]
            visite = "faite" if faites else "plafond"
    return Bilan(uai, visite, echecs + calculer_tout())
