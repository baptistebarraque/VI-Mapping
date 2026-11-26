"""Couches de zones, simplifiées pour l'affichage (la base garde les contours d'origine)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .commun import Connexion, collection, prov, sans_vide

TOLERANCE_COMMUNES_M = 60
TOLERANCE_IRIS_M = 30
TOLERANCE_QPV_M = 5
TOLERANCE_DISPOSITIFS_M = 40

# Couverture simplifiée d'un bloc : les limites communes restent jointives. La fonction perd le SRID.
_COUVERTURE = (
    "ST_AsGeoJSON(ST_Transform(ST_SetSRID(ST_CoverageSimplify(ST_Transform({geom}, 2154), {tolerance}) OVER (), 2154),"
    " 4326), 5)"
)
# GEOS antérieur à 3.12 (image PostGIS de docker-compose.yml) : chaque contour est simplifié seul.
_PAR_CONTOUR = (
    "ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(ST_Transform({geom}, 2154), {tolerance}), 4326), 5)"
)


def _simplifier(conn: Connexion, geom: str, tolerance: int) -> str:
    r = conn.execute("SELECT string_to_array(split_part(postgis_geos_version(), '-', 1), '.')::int[] AS v").fetchone()
    couverture = r is not None and r["v"][:2] >= [3, 12]
    return (_COUVERTURE if couverture else _PAR_CONTOUR).format(geom=geom, tolerance=tolerance)


def _feature(geojson: str, proprietes: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "geometry": json.loads(geojson), "properties": sans_vide(proprietes)}


def communes(conn: Connexion) -> dict[str, Any]:
    """Communes et arrondissements de Paris (la commune de Paris entière n'est pas dessinée)."""
    g = _simplifier(conn, "geom", TOLERANCE_COMMUNES_M)
    return collection(
        _feature(r["g"], {"code": r["code_insee"], "nom": r["nom"], "dep": r["departement"]})
        for r in conn.execute(
            f"""SELECT code_insee, nom, departement, {g} AS g FROM commune c
                WHERE NOT EXISTS (SELECT 1 FROM commune f WHERE f.commune_mere = c.code_insee) ORDER BY code_insee""")
    )


def iris(conn: Connexion) -> dict[str, Any]:
    g = _simplifier(conn, "t.geom", TOLERANCE_IRIS_M)
    return collection(
        _feature(r["g"], {
            "iris": r["iris"], "nom": r["nom"], "commune": r["commune"], "familles": r["familles_avec_enfants"],
            "revenu": r["revenu_median"], "pauvrete": r["taux_pauvrete"], "qpv": ", ".join(r["noms_qpv"] or []),
        })
        for r in conn.execute(
            f"""SELECT t.*, {g} AS g,
                       (SELECT array_agg(d.nom ORDER BY d.nom) FROM dispositif d WHERE d.id = ANY(t.qpv)) AS noms_qpv
                FROM territoire_social t ORDER BY t.iris""")
    )


def dispositifs(
    conn: Connexion, type_: str, complements: Callable[[str], dict[str, Any]] | None = None
) -> dict[str, Any]:
    """PAT (communes, mention « lauréat de l'appel à projets du PNA », contact du porteur), QPV ou cités éducatives.

    `deps` : départements couverts (« 75,93 »), pour que la carte filtre la zone avec les départements choisis.
    """
    tolerance = TOLERANCE_QPV_M if type_ == "qpv" else TOLERANCE_DISPOSITIFS_M
    return collection(
        _feature(r["g"], {
            "id": r["id"], "nom": r["nom"], "axe": r["axe_education_alimentaire"], "annee": r["annee"],
            "niveau": r["niveau"], "laureat": r["laureat"] or None,
            "communes": r["communes"] if type_ == "pat" else None, "deps": r["deps"], **prov(r),
            **(complements(r["id"]) if complements else {}),
        })
        for r in conn.execute(
            """SELECT d.*,
                      EXISTS (SELECT 1 FROM dispositif l WHERE l.id = replace(d.id, 'pat:', 'laureat_aap:')
                              AND l.type = 'laureat_aap' AND d.type = 'pat') AS laureat,
                      (SELECT string_agg(DISTINCT c.departement, ',' ORDER BY c.departement) FROM commune c
                       WHERE c.code_insee = ANY(d.communes)) AS deps,
                      ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(ST_Transform(d.geom, 2154), %s), 4326), 5)
                        AS g
               FROM dispositif d WHERE d.type = %s AND d.geom IS NOT NULL ORDER BY d.id""", (tolerance, type_))
    )
