"""Rattachements géographiques : école ↔ IRIS, école ↔ QPV, IRIS ↔ QPV."""

from __future__ import annotations

from psycopg.types.json import Jsonb

from ..sources.base import Compteurs, Contexte

PART_QPV_MIN = 0.01   # recouvrement négligeable d'un IRIS par un QPV (précision des contours)
IRIS_VOISIN_M = 200   # école tombant entre deux contours : IRIS le plus proche de la même commune


def rattacher(ctx: Contexte) -> Compteurs:
    iris = Jsonb(ctx.provenance_json("https://geoservices.ign.fr/contoursiris", confiance=0.95))
    qpv = Jsonb(ctx.provenance_json("https://sig.ville.gouv.fr", confiance=0.95))
    conn = ctx.conn
    conn.execute("UPDATE ecole SET iris = NULL, qpv = NULL, qpv_distance_m = NULL, "
                 "provenances = provenances - 'iris' - 'qpv'")
    dedans = conn.execute(
        "UPDATE ecole e SET iris = t.iris, provenances = e.provenances || jsonb_build_object('iris', %s::jsonb) "
        "FROM territoire_social t WHERE ST_Covers(t.geom, e.geom)", (iris,),
    ).rowcount
    voisins = conn.execute(
        """UPDATE ecole e SET iris = v.iris, provenances = e.provenances || jsonb_build_object('iris', %s::jsonb)
           FROM (
             SELECT DISTINCT ON (s.uai) s.uai, t.iris
             FROM ecole s JOIN territoire_social t ON t.commune = s.commune
             WHERE s.iris IS NULL AND s.geom IS NOT NULL
               AND ST_DWithin(s.geom_l93, ST_Transform(t.geom, 2154), %s)
             ORDER BY s.uai, ST_Distance(s.geom_l93, ST_Transform(t.geom, 2154))
           ) v WHERE v.uai = e.uai""", (iris, IRIS_VOISIN_M),
    ).rowcount
    ecoles_qpv = conn.execute(
        """WITH q AS MATERIALIZED (
             SELECT id, ST_Transform(geom, 2154) AS g FROM dispositif WHERE type = 'qpv' AND geom IS NOT NULL
           )
           UPDATE ecole e SET qpv = v.id, qpv_distance_m = v.d,
                  provenances = e.provenances || jsonb_build_object('qpv', %s::jsonb)
           FROM (
             SELECT DISTINCT ON (s.uai) s.uai, q.id, round(ST_Distance(s.geom_l93, q.g))::int AS d
             FROM ecole s JOIN q ON ST_DWithin(s.geom_l93, q.g, %s)
             ORDER BY s.uai, ST_Distance(s.geom_l93, q.g), q.id
           ) v WHERE v.uai = e.uai""", (qpv, ctx.idf.rattachements.qpv_distance_max_m),
    ).rowcount
    conn.execute("UPDATE territoire_social SET qpv = '{}', part_qpv = 0, provenances = provenances - 'qpv'")
    iris_qpv = conn.execute(
        """WITH q AS MATERIALIZED (
             SELECT id, ST_MakeValid(geom) AS g FROM dispositif WHERE type = 'qpv' AND geom IS NOT NULL
           ), paires AS (
             SELECT t.iris, q.id, ST_Area(ST_Intersection(ST_MakeValid(t.geom), q.g)) / ST_Area(t.geom) AS part
             FROM territoire_social t JOIN q ON ST_Intersects(t.geom, q.g)
           ), retenues AS (
             SELECT iris, array_agg(id ORDER BY part DESC, id) AS qpv, least(sum(part), 1) AS part
             FROM paires WHERE part >= %s GROUP BY iris
           )
           UPDATE territoire_social t SET qpv = r.qpv, part_qpv = round(r.part::numeric, 3),
                  provenances = t.provenances || jsonb_build_object('qpv', %s::jsonb)
           FROM retenues r WHERE r.iris = t.iris""", (PART_QPV_MIN, qpv),
    ).rowcount
    return {"ecoles_iris": dedans + voisins, "ecoles_qpv_proche": ecoles_qpv, "iris_avec_qpv": iris_qpv}
