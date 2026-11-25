"""Contrôles de la base : données personnelles, périmètre, provenance, cohérence des calculs.

Un contrôle compte les lignes fautives. Il n'affiche que leur identifiant, jamais leur contenu.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import psycopg
from psycopg import sql

from .config import ConfigIdf, config_idf, config_jauges, config_sources
from .sources.base import DUREE, a_collecter, dernier_succes

Gravite = Literal["erreur", "alerte"]

# Même sens que outils/texte.py, en expressions régulières PostgreSQL
_EMAIL = r"[[:alnum:]_.+-]+ ?(@|\[at\]|\(at\)) ?[[:alnum:]-]+\.[[:alpha:]]{2,}"
_TEL = r"(^|[^0-9])((\+|00)33[ .-]?(\(0\))?[ .-]?|0)[1-9]([ .-]?[0-9]{2}){4}([^0-9]|$)"
_CHEZ = r"\m(chez|c/o)\M"

# Coordonnées institutionnelles admises (standard et adresse générique) ; leur forme est contrôlée à part.
CONTACTS_INSTITUTIONNELS = {
    ("commune", "mairie_telephone"), ("commune", "mairie_email"), ("ecole", "telephone"), ("ecole", "email"),
}

# Tables sans texte collecté sur les personnes ou les lieux
_HORS_TEXTE = ("spatial_ref_sys", "schema_migration", "collecte_run", "source_donnees", "modele_provenance",
               "proximite", "jauge_ecole", "jauge_commune", "crawl_site")


@dataclass(frozen=True)
class Constat:
    nom: str
    gravite: Gravite
    nombre: int
    exemples: tuple[str, ...] = ()

    @property
    def conforme(self) -> bool:
        return self.nombre == 0


# Nom du contrôle, gravité, requête qui rend une colonne `cle` par ligne fautive
_REQUETES: tuple[tuple[str, Gravite, str], ...] = (
    ("Écoles hors premier degré, hors contrat ou hors périmètre", "erreur", """
        SELECT uai AS cle FROM ecole WHERE NOT departement = ANY(%(deps)s)
           OR secteur NOT IN ('public', 'prive_sous_contrat')
           OR type NOT IN ('maternelle', 'elementaire', 'primaire')"""),
    ("Communes hors périmètre", "erreur", """
        SELECT code_insee AS cle FROM commune WHERE NOT departement = ANY(%(deps)s)"""),
    ("Positions hors Île-de-France", "erreur", """
        SELECT x.cle FROM (
          SELECT 'ecole ' || uai AS cle, geom FROM ecole UNION ALL
          SELECT 'accueil ' || id, geom FROM accueil_periscolaire UNION ALL
          SELECT 'asso ' || id, geom FROM asso_parents UNION ALL
          SELECT 'relais ' || id, geom FROM relais_local UNION ALL
          SELECT 'producteur ' || id, geom FROM producteur) x
        WHERE geom IS NOT NULL AND NOT geom && ST_MakeEnvelope(%(o)s, %(s)s, %(e)s, %(n)s, 4326)"""),
    ("Écoles sans position", "alerte", "SELECT uai AS cle FROM ecole WHERE geom IS NULL"),
    ("Points placés à plus de 2 km de leur commune", "alerte", """
        SELECT x.cle FROM (
          SELECT 'ecole ' || uai AS cle, commune, geom FROM ecole UNION ALL
          SELECT 'accueil ' || id, commune, geom FROM accueil_periscolaire UNION ALL
          SELECT 'asso ' || id, commune, geom FROM asso_parents UNION ALL
          SELECT 'relais ' || id, commune, geom FROM relais_local UNION ALL
          SELECT 'producteur ' || id, commune, geom FROM producteur) x
        JOIN commune c ON c.code_insee = x.commune
        WHERE NOT ST_DWithin(x.geom::geography, c.geom::geography, 2000)"""),
    ("Lignes d'une source verrouillée", "erreur", """
        SELECT source || ' ' || id AS cle FROM accueil_periscolaire WHERE source = ANY(%(verrouillees)s) UNION ALL
        SELECT source || ' ' || id FROM asso_parents WHERE source = ANY(%(verrouillees)s) UNION ALL
        SELECT source || ' ' || id FROM relais_local WHERE source = ANY(%(verrouillees)s)"""),
    ("Cibles de proximité disparues", "erreur", """
        SELECT DISTINCT x.cible_type || ' ' || x.cible_id AS cle FROM proximite x
        WHERE NOT EXISTS (SELECT 1 FROM producteur p WHERE x.cible_type = 'producteur' AND p.id = x.cible_id)
          AND NOT EXISTS (SELECT 1 FROM relais_local r WHERE x.cible_type = 'relais_local' AND r.id = x.cible_id)"""),
    ("Paires de plus de 50 km à vol d'oiseau", "erreur", """
        SELECT ecole_uai || ' ' || cible_id AS cle FROM proximite WHERE km_vol_oiseau > %(km_max)s"""),
    ("Route plus courte que le vol d'oiseau", "alerte", """
        SELECT ecole_uai || ' ' || cible_id AS cle FROM proximite
        WHERE km_route < km_vol_oiseau - 0.6"""),  # rattachement des points à la route : 300 m à chaque bout
    ("Paires sans distance par la route", "alerte", """
        SELECT ecole_uai || ' ' || cible_id AS cle FROM proximite WHERE km_route IS NULL"""),
    ("Écoles sans jauges calculées", "erreur", """
        SELECT uai AS cle FROM ecole e WHERE NOT EXISTS (SELECT 1 FROM jauge_ecole j WHERE j.ecole_uai = e.uai)"""),
    ("Jauges calculées avec une autre configuration", "erreur", """
        SELECT ecole_uai AS cle FROM jauge_ecole WHERE config_hash <> %(empreinte)s"""),
    ("Communes sans score calculé", "erreur", """
        SELECT code_insee AS cle FROM commune c
        WHERE NOT EXISTS (SELECT 1 FROM jauge_commune j WHERE j.code_insee = c.code_insee)"""),
    ("Scores des communes calculés avec une autre configuration", "erreur", """
        SELECT code_insee AS cle FROM jauge_commune WHERE config_hash <> %(empreinte)s"""),
    ("Jauges plus anciennes que la dernière collecte", "alerte", """
        SELECT min(j.ecole_uai) AS cle FROM jauge_ecole j
        HAVING min(j.collecte_le) < (SELECT max(r.fin) FROM collecte_run r JOIN source_donnees s ON s.code = r.source
                                     WHERE r.statut = 'succes' AND s.methode <> 'calcul')"""),
    ("Score présent sans aucune jauge", "erreur", """
        SELECT ecole_uai AS cle FROM jauge_ecole WHERE score IS NOT NULL
          AND coalesce(engagement, periscolaire, parents, producteurs, familles) IS NULL"""),
    ("Écoles liées à un doublon sans l'être à la fiche principale", "erreur", """
        SELECT 'asso ' || l.asso_id AS cle FROM asso_ecole l JOIN asso_parents a ON a.id = l.asso_id
        WHERE a.doublon_de IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM asso_ecole m WHERE (m.asso_id, m.ecole_uai) = (a.doublon_de, l.ecole_uai))
        UNION
        SELECT 'accueil ' || l.accueil_id FROM accueil_ecole l JOIN accueil_periscolaire a ON a.id = l.accueil_id
        WHERE a.doublon_de IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM accueil_ecole m
                          WHERE (m.accueil_id, m.ecole_uai) = (a.doublon_de, l.ecole_uai))"""),
    ("Coordonnées d'école qui ne sont pas institutionnelles", "erreur", r"""
        SELECT uai AS cle FROM ecole
        WHERE (email IS NOT NULL AND email !~ ('^ce\.' || lower(uai) || '@ac-[a-z-]+\.fr$'))
           OR (telephone IS NOT NULL AND telephone !~ '^0[1-589]( [0-9]{2}){4}$')"""),
    ("Contacts de mairie mal formés", "erreur", r"""
        SELECT code_insee AS cle FROM commune
        WHERE (mairie_email IS NOT NULL AND mairie_email !~ '^[^@ ]+@[^@ ]+\.[a-z]{2,}$')
           OR (mairie_telephone IS NOT NULL AND mairie_telephone !~ '^0[1-9]( [0-9]{2}){4}$')"""),
    ("Adresses qui nomment une personne", "erreur", """
        SELECT 'asso ' || id AS cle FROM asso_parents WHERE siege ~* %(chez)s UNION ALL
        SELECT 'accueil ' || id FROM accueil_periscolaire WHERE adresse ~* %(chez)s UNION ALL
        SELECT 'relais ' || id FROM relais_local WHERE adresse ~* %(chez)s"""),
    ("Dates de collecte dans le futur", "erreur", """
        SELECT 'ecole ' || uai AS cle FROM ecole WHERE collecte_le > now() UNION ALL
        SELECT 'jauge ' || ecole_uai FROM jauge_ecole WHERE collecte_le > now()"""),
)


def _compter(conn: psycopg.Connection[Any], nom: str, gravite: Gravite, requete: Any, params: Any) -> Constat:
    r = conn.execute(
        sql.SQL("SELECT count(*) AS n, (array_agg(t.cle::text ORDER BY t.cle::text))[1:3] AS ex FROM ({}) t "
                "WHERE t.cle IS NOT NULL").format(requete if isinstance(requete, sql.Composable) else sql.SQL(requete)),
        params,
    ).fetchone()
    return Constat(nom, gravite, r["n"], tuple(r["ex"] or ())) if r else Constat(nom, gravite, 0)


def contacts(conn: psycopg.Connection[Any]) -> Iterator[Constat]:
    """E-mails et téléphones dans les colonnes de texte. Les adresses web ne comptent que pour les e-mails."""
    colonnes = conn.execute(
        """SELECT c.table_name AS t, c.column_name AS c FROM information_schema.columns c
           JOIN information_schema.tables b USING (table_schema, table_name)
           WHERE c.table_schema = 'public' AND b.table_type = 'BASE TABLE' AND c.data_type IN ('text', 'ARRAY', 'jsonb')
             AND c.table_name <> ALL(%s) ORDER BY 1, 2""", (list(_HORS_TEXTE),)).fetchall()
    for nom, motif in (("E-mails", _EMAIL), ("Numéros de téléphone", _TEL)):
        trouves = []
        for x in colonnes:
            web = x["c"] in ("url", "site_web", "derniere_activite_url", "provenances")
            if (x["t"], x["c"]) in CONTACTS_INSTITUTIONNELS:
                continue
            if motif == _TEL and (web or x["c"] in ("id", "cle", "indices")):
                continue
            c = _compter(conn, "", "erreur", sql.SQL(
                "SELECT {t} || '.' || {c} AS cle FROM {table} WHERE {col}::text ~* {m}").format(
                    t=sql.Literal(x["t"]), c=sql.Literal(x["c"]), table=sql.Identifier(x["t"]),
                    col=sql.Identifier(x["c"]), m=sql.Literal(motif)), None)
            if c.nombre:
                trouves.append((c.nombre, f"{x['t']}.{x['c']}"))
        yield Constat(f"{nom} dans la base", "erreur", sum(n for n, _ in trouves), tuple(c for _, c in trouves[:3]))


def fraicheur(conn: psycopg.Connection[Any]) -> Constat:
    """Sources ouvertes sans collecte réussie depuis plus de deux périodes."""
    maintenant = datetime.now(UTC)
    sources = config_sources()
    retard = []
    for code in a_collecter():
        fait = dernier_succes(conn, code)
        if not sources[code].verrouillee and (fait is None or maintenant - fait > 2 * DUREE[sources[code].frequence]):
            retard.append(code)
    return Constat("Sources en retard de plus de deux périodes", "alerte", len(retard), tuple(retard[:3]))


def verifier(conn: psycopg.Connection[Any]) -> Iterator[Constat]:
    idf: ConfigIdf = config_idf()
    o, s, e, n = idf.region.bbox
    params = {
        "deps": list(idf.region.departements), "o": o, "s": s, "e": e, "n": n, "chez": _CHEZ, "km_max": 50,
        "verrouillees": [c for c, x in config_sources().items() if x.verrouillee],
        "empreinte": config_jauges().empreinte(),
    }
    yield from contacts(conn)
    for nom, gravite, requete in _REQUETES:
        yield _compter(conn, nom, gravite, requete, params)
    yield fraicheur(conn)
