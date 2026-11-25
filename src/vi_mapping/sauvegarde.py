"""Archive portable de la base : un zip, un fichier COPY par table. Aucun client PostgreSQL requis.

Publiable : sans cache de géocodage (adresses brutes) ni messages d'erreur (chemins locaux).
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from .db import migrer

# Ordre des clés étrangères ; source_donnees est rempli par « vi migrer ».
TABLES = (
    "collecte_run", "crawl_site", "commune", "dispositif", "territoire_social", "ecole", "gestionnaire_perisco",
    "accueil_periscolaire", "accueil_ecole", "asso_parents", "asso_ecole", "relais_local", "elu", "signal_web",
    "producteur", "proximite", "jauge_ecole",
)
EXCLUES = {"collecte_run": {"id", "message"}}
BLOC = 1 << 20

Conn = psycopg.Connection[Any]


def _colonnes(conn: Conn, table: str) -> list[str]:
    return [r["column_name"] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s "
        "AND is_generated = 'NEVER' ORDER BY ordinal_position", (table,))
        if r["column_name"] not in EXCLUES.get(table, ())]


def _liste(colonnes: list[str]) -> sql.Composable:
    return sql.SQL(", ").join(map(sql.Identifier, colonnes))


def sauvegarder(conn: Conn, fichier: Path) -> None:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    with zipfile.ZipFile(fichier, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for table in TABLES:
            colonnes = _colonnes(conn, table)
            with z.open(f"{table}.txt", "w", force_zip64=True) as f:
                f.write(("\t".join(colonnes) + "\n").encode())
                with conn.cursor() as cur, cur.copy(sql.SQL("COPY {} ({}) TO STDOUT").format(
                        sql.Identifier(table), _liste(colonnes))) as copie:
                    for bloc in copie:
                        f.write(bloc)


def restaurer(conn: Conn, fichier: Path, *, remplacer: bool = False) -> dict[str, int]:
    """Recharge l'archive en une transaction. Refuse une base déjà remplie, sauf `remplacer`."""
    migrer(conn)
    compte: dict[str, int] = {}
    with conn.transaction():
        r = conn.execute("SELECT EXISTS (SELECT 1 FROM commune) OR EXISTS (SELECT 1 FROM collecte_run) AS p").fetchone()
        if r and r["p"] and not remplacer:
            raise RuntimeError("la base contient déjà des données (--remplacer pour les effacer)")
        conn.execute(sql.SQL("TRUNCATE {}").format(_liste(list(TABLES))))
        with zipfile.ZipFile(fichier) as z:
            for table in TABLES:
                with z.open(f"{table}.txt") as f, conn.cursor() as cur:
                    colonnes = f.readline().decode().rstrip("\n").split("\t")
                    with cur.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(
                            sql.Identifier(table), _liste(colonnes))) as copie:
                        while bloc := f.read(BLOC):
                            copie.write(bloc)
                    compte[table] = cur.rowcount
    conn.commit()
    conn.autocommit = True
    conn.execute("ANALYZE")
    return compte
