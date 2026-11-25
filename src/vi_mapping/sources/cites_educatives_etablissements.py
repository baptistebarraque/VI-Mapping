"""Écoles membres d'une cité éducative."""

from __future__ import annotations

from ..outils.opendatasoft import exporter, url_fiche
from ..outils.texte import titre
from .base import Compteurs, Contexte, connecteur


@connecteur("cites_educatives_etablissements", depend_de=["annuaire_education"])
def collecter(ctx: Contexte) -> Compteurs:
    base = ctx.config.url
    lignes = exporter(ctx.http, base, where=f'code_region="{ctx.idf.region.code}"',
                      select="uai,libelle_long_cite_educative")
    n = ctx.enrichir("ecole", [
        {
            "uai": e["uai"],
            "cite_educative": titre(e["libelle_long_cite_educative"]),
            "provenance": ctx.provenance_json(url_fiche(base, "uai", e["uai"])),
        }
        for e in lignes
    ], "uai", "cite_educative")
    return {"etablissements": len(lignes), "ecoles": n}
