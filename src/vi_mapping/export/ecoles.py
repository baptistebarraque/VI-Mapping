"""Table des écoles en colonnes : ce qu'il faut pour filtrer, classer et recalculer le score dans la carte."""

from __future__ import annotations

from typing import Any

from ..calculs.jauges import distances_producteurs
from ..config import ConfigJauges
from .commun import Connexion

TYPES = ("maternelle", "elementaire", "primaire")
SECTEURS = ("public", "prive_sous_contrat")
EDUCATION_PRIORITAIRE = (None, "REP", "REP+")


def ecoles(conn: Connexion, cfg: ConfigJauges, rang_commune: dict[str, int]) -> dict[str, Any]:
    """Colonnes parallèles, triées par UAI. `prod` : [km, minutes, km, minutes…] des producteurs utiles à la jauge."""
    distances = distances_producteurs(conn, cfg)
    colonnes: dict[str, list[Any]] = {}
    for e in conn.execute(
        """SELECT e.uai, e.nom, e.commune, e.type, e.secteur, e.nb_eleves, e.ips, e.education_prioritaire,
                  e.cite_educative IS NOT NULL AS cite, ST_X(e.geom) AS lon, ST_Y(e.geom) AS lat,
                  j.engagement, j.periscolaire, j.parents, j.producteurs, j.familles, j.score, j.confiance
           FROM ecole e JOIN jauge_ecole j ON j.ecole_uai = e.uai
           WHERE e.geom IS NOT NULL ORDER BY e.uai"""
    ):
        ligne = {
            "uai": e["uai"],
            "nom": e["nom"],
            "commune": rang_commune[e["commune"]],
            "type": TYPES.index(e["type"]),
            "secteur": SECTEURS.index(e["secteur"]),
            "eleves": e["nb_eleves"],
            "ips": e["ips"],
            "rep": EDUCATION_PRIORITAIRE.index(e["education_prioritaire"]),
            "cite": int(e["cite"]),
            "lon": round(e["lon"], 5),
            "lat": round(e["lat"], 5),
            **{n: e[n] for n in (*cfg.poids, "score", "confiance")},
            "prod": [x for paire in sorted(distances[e["uai"]], key=lambda p: (p[1] is None, p[1], p[0]))
                     for x in paire] if e["uai"] in distances else None,
        }
        for nom, valeur in ligne.items():
            colonnes.setdefault(nom, []).append(valeur)
    return colonnes
