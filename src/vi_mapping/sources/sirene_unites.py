"""Stock Sirene des unités légales : Siren des associations de parents (par leur numéro RNA) et nature juridique
des cuisines centrales (municipale, caisse des écoles, intercommunale, privée)."""

from __future__ import annotations

from typing import Any

import duckdb

from ..outils.datagouv import derniere
from ..outils.texte import titre
from .base import Compteurs, Contexte, connecteur
from .sirene import JEU

FICHE = "https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}"


def type_cuisine(categorie: str | None) -> str:
    """Catégorie juridique Insee -> gestionnaire d'une cuisine centrale."""
    c = categorie or ""
    if c in ("7210", "7312"):          # commune, commune associée ou déléguée
        return "municipale"
    if c == "7362":                    # caisse des écoles
        return "caisse_des_ecoles"
    if c.startswith(("734", "735")):   # EPCI, métropole, EPT, syndicats intercommunaux ou mixtes
        return "intercommunale"
    if c.startswith(("4", "7")):       # autres personnes morales de droit public
        return "autre_public"
    return "privee" if c else "inconnu"


@connecteur("sirene_unites", depend_de=["rna", "ma_cantine"])
def collecter(ctx: Contexte) -> Compteurs:
    ressource = derniere(ctx.http, JEU, r"stock-stockunitelegale-parquet\.parquet")
    rna = [r["rna"] for r in ctx.conn.execute("SELECT rna FROM asso_parents WHERE rna IS NOT NULL")]
    cuisines = {r["siret"][:9]: r for r in ctx.conn.execute("SELECT siret, nom FROM cuisine_centrale")}
    base = duckdb.connect()
    base.execute("INSTALL httpfs; LOAD httpfs; SET enable_progress_bar = false;")
    trouves = base.execute(
        "SELECT identifiantAssociationUniteLegale, min(siren) FROM read_parquet(?) "
        "WHERE identifiantAssociationUniteLegale IN (SELECT unnest(?)) AND etatAdministratifUniteLegale = 'A' "
        "GROUP BY 1",
        [ressource.url, rna],
    ).fetchall()
    unites = base.execute(
        "SELECT siren, CAST(categorieJuridiqueUniteLegale AS VARCHAR), denominationUniteLegale FROM read_parquet(?) "
        "WHERE siren IN (SELECT unnest(?))",
        [ressource.url, list(cuisines)],
    ).fetchall()
    base.close()
    n = ctx.enrichir("asso_parents", [
        {
            "id": f"rna:{numero}",
            "siren": siren,
            "provenance": ctx.provenance_json(FICHE.format(siren=siren)),
        }
        for numero, siren in trouves
    ], "id", "siren")
    return {"assos": len(rna), "siren_trouves": n, **classer_cuisines(ctx, unites)}


def classer_cuisines(ctx: Contexte, unites: list[tuple[str, Any, Any]]) -> Compteurs:
    """Type de gestionnaire et, faute de mieux, nom de l'unité légale pour une cuisine connue par son seul SIRET."""
    compte: Compteurs = {}
    for siren, categorie, denomination in unites:
        categorie = (categorie or "").split(".")[0] or None  # un entier lu en flottant : « 7210.0 »
        type_ = type_cuisine(categorie)
        compte[f"cuisines_{type_}"] = compte.get(f"cuisines_{type_}", 0) + 1
        ctx.conn.execute(
            """UPDATE cuisine_centrale SET type = %s, categorie_juridique = %s,
                      nom = CASE WHEN nom LIKE 'Cuisine centrale %%' AND %s::text IS NOT NULL THEN %s ELSE nom END
               WHERE left(siret, 9) = %s""",
            (type_, categorie, denomination, titre(denomination or ""), siren),
        )
    return compte
