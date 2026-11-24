"""Accès PostgreSQL : migrations, écriture idempotente, purge des lignes disparues."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import DOSSIER_SQL, config_sources, url_base

Ligne = dict[str, Any]


def connexion(url: str | None = None) -> psycopg.Connection[Ligne]:
    return psycopg.connect(url or url_base(), row_factory=dict_row)  # type: ignore[arg-type]


def migrer(conn: psycopg.Connection[Any]) -> list[str]:
    """Applique les fichiers sql/*.sql non encore appliqués, puis synchronise le registre des sources."""
    with conn.transaction():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migration "
            "(fichier text PRIMARY KEY, applique_le timestamptz NOT NULL DEFAULT now())"
        )
        deja = {r["fichier"] for r in conn.execute("SELECT fichier FROM schema_migration")}
        faits = []
        for f in sorted(DOSSIER_SQL.glob("*.sql")):
            if f.name in deja:
                continue
            conn.execute(f.read_text(encoding="utf-8"))  # type: ignore[arg-type]
            conn.execute("INSERT INTO schema_migration (fichier) VALUES (%s)", (f.name,))
            faits.append(f.name)
        _synchroniser_sources(conn)
    return faits


def _synchroniser_sources(conn: psycopg.Connection[Any]) -> None:
    for code, s in config_sources().items():
        verification = {}
        if s.verification:
            verification = json.loads(s.verification.model_dump_json(exclude_none=True))
        if s.autorisation:
            verification["autorisation"] = json.loads(s.autorisation.model_dump_json())
        conn.execute(
            """INSERT INTO source_donnees (code, libelle, producteur, url, licence, methode, frequence,
                                           statut, confiance, verification)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle, producteur = EXCLUDED.producteur,
                 url = EXCLUDED.url, licence = EXCLUDED.licence, methode = EXCLUDED.methode,
                 frequence = EXCLUDED.frequence, statut = EXCLUDED.statut, confiance = EXCLUDED.confiance,
                 verification = EXCLUDED.verification, maj_config_le = now()""",
            (code, s.libelle, s.producteur, s.url, s.licence, s.methode, s.frequence,
             "verrouillee" if s.verrouillee else "ouverte", s.confiance, Jsonb(verification)),
        )


def _adapter(valeur: Any) -> Any:
    return Jsonb(valeur) if isinstance(valeur, dict) else valeur


def upsert(
    conn: psycopg.Connection[Any],
    table: str,
    lignes: Iterable[Ligne],
    cle: Sequence[str],
    *,
    ne_pas_ecraser: Sequence[str] = (),
) -> int:
    """Insère ou met à jour des lignes sur leur clé naturelle (COPY puis ON CONFLICT).

    Toutes les lignes doivent avoir les mêmes colonnes ; une clé en double garde la dernière.
    `ne_pas_ecraser` : colonnes fournies seulement à l'insertion.
    """
    uniques: dict[tuple[Any, ...], Ligne] = {}
    for ligne in lignes:
        uniques[tuple(ligne[c] for c in cle)] = ligne
    if not uniques:
        return 0
    colonnes = list(next(iter(uniques.values())))
    ident = sql.SQL(", ").join(map(sql.Identifier, colonnes))
    temp = sql.Identifier(f"_lot_{table}")
    cible = sql.Identifier(table)
    maj = [c for c in colonnes if c not in cle and c not in ne_pas_ecraser]
    action = (
        sql.SQL("DO UPDATE SET {}").format(
            sql.SQL(", ").join(sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(c)) for c in maj)
        )
        if maj
        else sql.SQL("DO NOTHING")
    )
    with conn.cursor() as cur:
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(temp))
        cur.execute(
            sql.SQL("CREATE TEMP TABLE {} ON COMMIT DROP AS SELECT {} FROM {} WITH NO DATA").format(
                temp, ident, cible
            )
        )
        with cur.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(temp, ident)) as copie:
            for ligne in uniques.values():
                copie.write_row([_adapter(ligne[c]) for c in colonnes])
        cur.execute(
            sql.SQL("INSERT INTO {} ({}) SELECT {} FROM {} ON CONFLICT ({}) {}").format(
                cible, ident, ident, temp, sql.SQL(", ").join(map(sql.Identifier, cle)), action
            )
        )
        cur.execute(sql.SQL("DROP TABLE {}").format(temp))
    return len(uniques)


class ChuteAnormale(RuntimeError):
    """La collecte rapporte beaucoup moins de lignes que la précédente : on refuse de purger."""


def purger_absents(
    conn: psycopg.Connection[Any],
    table: str,
    source: str,
    depuis: datetime,
    *,
    filtre: str = "TRUE",
    chute_max: float = 0.5,
) -> int:
    """Supprime les lignes de `source` non revues depuis `depuis` (début de la collecte).

    Garde-fou : si plus de `chute_max` des lignes disparaissaient, la source est sans doute en panne.
    """
    avant = conn.execute(
        sql.SQL("SELECT count(*) AS n, count(*) FILTER (WHERE collecte_le < %s) AS vieux "
                "FROM {} WHERE source = %s AND " + filtre).format(sql.Identifier(table)),
        (depuis, source),
    ).fetchone()
    assert avant is not None
    if avant["n"] >= 20 and avant["vieux"] > chute_max * avant["n"]:
        raise ChuteAnormale(f"{table}/{source} : {avant['vieux']} lignes sur {avant['n']} disparaîtraient")
    cur = conn.execute(
        sql.SQL("DELETE FROM {} WHERE source = %s AND collecte_le < %s AND " + filtre).format(
            sql.Identifier(table)
        ),
        (source, depuis),
    )
    return cur.rowcount


def enrichir(
    conn: psycopg.Connection[Any],
    table: str,
    lignes: Iterable[Ligne],
    cle: str,
    groupe: str,
    *,
    chute_max: float = 0.5,
) -> int:
    """Met à jour des colonnes de lignes existantes et trace leur origine dans `provenances[groupe]`.

    Chaque ligne porte la clé, les colonnes à écrire et `provenance` (dict). Les lignes enrichies lors d'une
    collecte précédente mais absentes de celle-ci sont remises à NULL. Retourne le nombre de lignes touchées.
    """
    uniques = {ligne[cle]: ligne for ligne in lignes}
    avant = conn.execute(
        sql.SQL("SELECT count(*) AS n FROM {} WHERE provenances ? %s").format(sql.Identifier(table)), (groupe,)
    ).fetchone()
    assert avant is not None
    if avant["n"] >= 20 and len(uniques) < (1 - chute_max) * avant["n"]:
        raise ChuteAnormale(f"{table}/{groupe} : {len(uniques)} lignes au lieu de {avant['n']}")
    if not uniques:
        return 0
    colonnes = [c for c in next(iter(uniques.values())) if c not in (cle, "provenance")]
    temp = sql.Identifier(f"_enrichir_{table}")
    liste = sql.SQL(", ").join(map(sql.Identifier, [cle, *colonnes]))
    conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(temp))
    conn.execute(
        sql.SQL("CREATE TEMP TABLE {} ON COMMIT DROP AS SELECT {}, '{{}}'::jsonb AS _prov FROM {} WITH NO DATA").format(
            temp, liste, sql.Identifier(table)
        )
    )
    with conn.cursor() as cur, cur.copy(
        sql.SQL("COPY {} ({}, _prov) FROM STDIN").format(temp, liste)
    ) as copie:
        for ligne in uniques.values():
            copie.write_row([ligne[cle], *(_adapter(ligne[c]) for c in colonnes), Jsonb(ligne["provenance"])])
    conn.execute(
        sql.SQL("UPDATE {} SET {}, provenances = provenances - %s WHERE provenances ? %s").format(
            sql.Identifier(table),
            sql.SQL(", ").join(sql.SQL("{} = DEFAULT").format(sql.Identifier(c)) for c in colonnes),
        ),
        (groupe, groupe),
    )
    n = conn.execute(
        sql.SQL("UPDATE {0} AS t SET {1}, provenances = t.provenances || jsonb_build_object(%s::text, l._prov) "
                "FROM {2} AS l WHERE t.{3} = l.{3}").format(
            sql.Identifier(table),
            sql.SQL(", ").join(sql.SQL("{0} = l.{0}").format(sql.Identifier(c)) for c in colonnes),
            temp,
            sql.Identifier(cle),
        ),
        (groupe,),
    ).rowcount
    conn.execute(sql.SQL("DROP TABLE {}").format(temp))
    return n


def point(lon: float, lat: float) -> str:
    """EWKT accepté par COPY dans une colonne geometry(Point, 4326)."""
    return f"SRID=4326;POINT({lon:.7f} {lat:.7f})"
