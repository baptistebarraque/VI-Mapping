"""Métadonnées de la carte : réglages des jauges, communes, sources et dates de collecte."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..config import ConfigIdf, ConfigJauges, config_sources
from .commun import Connexion, sans_vide


def communes(conn: Connexion) -> list[dict[str, Any]]:
    """Communes et arrondissements, dans l'ordre auquel renvoient les écoles."""
    return [
        sans_vide({"code": r["code_insee"], "nom": r["nom"], "dep": r["departement"], "mere": r["commune_mere"],
                   "ecoles": r["ecoles"], "bbox": [round(x, 4) for x in r["bbox"]]})
        for r in conn.execute(
            """SELECT code_insee, nom, departement, commune_mere,
                      (SELECT count(*) FROM ecole e WHERE e.commune = c.code_insee) AS ecoles,
                      ARRAY[ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)] AS bbox
               FROM commune c ORDER BY code_insee""")
    ]


def sources(conn: Connexion) -> dict[str, dict[str, Any]]:
    dates = {r["source"]: r["fin"] for r in conn.execute(
        "SELECT source, max(fin) AS fin FROM collecte_run WHERE statut = 'succes' GROUP BY source")}
    return {
        code: sans_vide({
            "libelle": s.libelle, "producteur": s.producteur, "url": s.url, "licence": s.licence,
            "methode": s.methode, "frequence": s.frequence, "verrouillee": s.verrouillee or None,
            "collecte": dates[code].date() if code in dates else None,
            "constat": s.verification.constat if s.verrouillee and s.verification else None,
            "remplacement": s.verification.remplacement if s.verrouillee and s.verification else None,
        })
        for code, s in config_sources().items()
    }


def meta(conn: Connexion, idf: ConfigIdf, cfg: ConfigJauges, liste_communes: list[dict[str, Any]]) -> dict[str, Any]:
    p = cfg.producteurs
    return {
        "genere_le": datetime.now(UTC),
        "config": cfg.empreinte(),
        "departements": idf.region.departements,
        "bbox": idf.region.bbox,
        "poids": cfg.poids,
        "rayon": cfg.rayon.model_dump(),
        "km_max": idf.proximite.km_vol_oiseau_max,
        "part_min_score": cfg.donnees_insuffisantes.part_min_connue_score,
        "producteurs": {"sous_poids": p.sous_poids, "minutes_plein": p.minutes_plein, "km_plein": p.km_plein,
                        "nombre_plein": p.nombre_plein},
        "sous_poids": {"engagement": cfg.engagement.sous_poids, "periscolaire": cfg.periscolaire.sous_poids,
                       "parents": cfg.parents.sous_poids, "producteurs": p.sous_poids,
                       "familles": cfg.familles.sous_poids},
        "seuils": {"web_mois": cfg.engagement.web.fenetre_mois, "parents_mois": cfg.parents.fenetre_activite_mois,
                   "accueil_m": cfg.periscolaire.distance_max_m, "asso_confiance": cfg.parents.confiance_min,
                   "bio_pct_plein": cfg.engagement.bio.pct_plein},
        "communes": liste_communes,
        "sources": sources(conn),
    }
