"""Couches de points : accueils, associations, producteurs, relais (les doublons entre sources sont masqués)."""

from __future__ import annotations

from typing import Any

from ..config import ConfigJauges
from .commun import Connexion, collection, feature_point, prov


def accueils(conn: Connexion) -> dict[str, Any]:
    return collection(
        feature_point(r["lon"], r["lat"], {
            "id": r["id"], "nom": r["nom"], "adresse": r["adresse"], "commune": r["commune"],
            "soir": r["accueil_soir"], "mercredi": r["accueil_mercredi"], "horaires": r["horaires"],
            "gestionnaire": r["gestionnaire"] or r["exploitant"], "ecoles": r["ecoles"], **prov(r),
        })
        for r in conn.execute(
            """SELECT a.*, ST_X(a.geom) AS lon, ST_Y(a.geom) AS lat, g.nom AS gestionnaire,
                      (SELECT count(*) FROM accueil_ecole l WHERE l.accueil_id = a.id) AS ecoles
               FROM accueil_periscolaire a LEFT JOIN gestionnaire_perisco g ON g.siren = a.gestionnaire_siren
               WHERE a.doublon_de IS NULL ORDER BY a.id""")
    )


def assos(conn: Connexion) -> dict[str, Any]:
    return collection(
        feature_point(r["lon"], r["lat"], {
            "id": r["id"], "nom": r["nom"], "siege": r["siege"], "commune": r["commune"],
            "federation": r["federation"], "site": r["site_web"], "creation": r["date_creation"],
            "activite": r["derniere_activite"], "ecoles": r["ecoles"], **prov(r),
        })
        for r in conn.execute(
            """SELECT a.*, ST_X(a.geom) AS lon, ST_Y(a.geom) AS lat,
                      (SELECT count(*) FROM asso_ecole l WHERE l.asso_id = a.id) AS ecoles
               FROM asso_parents a
               WHERE a.doublon_de IS NULL AND a.geom IS NOT NULL AND a.niveau <> 'second_degre' ORDER BY a.id""")
    )


def producteurs(conn: Connexion, cfg: ConfigJauges) -> tuple[dict[str, Any], dict[str, int]]:
    """Couche des producteurs et rang de chacun (les fiches y renvoient par ce rang)."""
    lignes = conn.execute(
        "SELECT *, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM producteur ORDER BY id").fetchall()
    features = [
        feature_point(r["lon"], r["lat"], {
            "id": r["id"], "nom": r["nom"], "activites": ", ".join(r["activites"]), "bio": r["etat_bio"],
            "legumes": r["maraichage"], "fruits": r["fruits"], "vente": r["vente_directe"],
            "amap": r["membre_amap"], "eligible": r["eligible"],
            "compte": r["eligible"] and r["adresse_type"] in cfg.producteurs.adresses,
            "adresse": r["adresse"], "adresse_type": r["adresse_type"], "commune": r["commune"], **prov(r),
        })
        for r in lignes
    ]
    return collection(features), {r["id"]: i for i, r in enumerate(lignes)}


def relais(conn: Connexion) -> tuple[dict[str, Any], dict[str, int]]:
    """Couche des relais locaux et rang de chacun."""
    lignes = conn.execute(
        "SELECT *, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM relais_local WHERE doublon_de IS NULL ORDER BY id"
    ).fetchall()
    features = [
        feature_point(r["lon"], r["lat"], {
            "id": r["id"], "type": r["type"], "nom": r["nom"], "adresse": r["adresse"], "site": r["site_web"],
            "commune": r["commune"], **prov(r),
        })
        for r in lignes
    ]
    return collection(features), {r["id"]: i for i, r in enumerate(lignes)}
