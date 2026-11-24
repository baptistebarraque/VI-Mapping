"""Numéro Siren des associations de parents, retrouvé par leur numéro RNA (stock Sirene des unités légales)."""

from __future__ import annotations

import duckdb

from ..outils.datagouv import derniere
from .base import Compteurs, Contexte, connecteur
from .sirene import JEU


@connecteur("sirene_unites", depend_de=["rna"])
def collecter(ctx: Contexte) -> Compteurs:
    ressource = derniere(ctx.http, JEU, r"stock-stockunitelegale-parquet\.parquet")
    rna = [r["rna"] for r in ctx.conn.execute("SELECT rna FROM asso_parents WHERE rna IS NOT NULL")]
    base = duckdb.connect()
    base.execute("INSTALL httpfs; LOAD httpfs; SET enable_progress_bar = false;")
    trouves = base.execute(
        "SELECT identifiantAssociationUniteLegale, min(siren) FROM read_parquet(?) "
        "WHERE identifiantAssociationUniteLegale IN (SELECT unnest(?)) AND etatAdministratifUniteLegale = 'A' "
        "GROUP BY 1",
        [ressource.url, rna],
    ).fetchall()
    base.close()
    n = ctx.enrichir("asso_parents", [
        {
            "id": f"rna:{numero}",
            "siren": siren,
            "provenance": ctx.provenance_json(f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}"),
        }
        for numero, siren in trouves
    ], "id", "siren")
    return {"assos": len(rna), "siren_trouves": n}
