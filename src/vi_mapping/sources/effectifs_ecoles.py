"""Nombre d'élèves et de classes de chaque école (dernière rentrée publiée)."""

from __future__ import annotations

from ..outils.opendatasoft import exporter, grouper, url_fiche
from .base import Compteurs, Contexte, connecteur


@connecteur("effectifs_ecoles", depend_de=["annuaire_education"])
def collecter(ctx: Contexte) -> Compteurs:
    base, region = ctx.config.url, ctx.idf.region.code
    rentrees = grouper(ctx.http, base, "rentree_scolaire, count(*) as n", par="rentree_scolaire",
                       where=f'code_region_insee="{region}"')
    annee = max(r["rentree_scolaire"][:4] for r in rentrees if r["n"] > 1000)
    lignes = exporter(
        ctx.http, base, where=f"code_region_insee=\"{region}\" and rentree_scolaire=date'{annee}'",
        select="numero_ecole,nombre_total_eleves,nombre_total_classes",
    )
    n = ctx.enrichir("ecole", [
        {
            "uai": e["numero_ecole"],
            "nb_eleves": int(e["nombre_total_eleves"]),
            "nb_classes": int(e["nombre_total_classes"]) if e["nombre_total_classes"] is not None else None,
            "effectifs_rentree": int(annee),
            "provenance": ctx.provenance_json(url_fiche(base, "numero_ecole", e["numero_ecole"])),
        }
        for e in lignes if e["nombre_total_eleves"] is not None
    ], "uai", "effectifs")
    return {"rentree": int(annee), "lignes": len(lignes), "ecoles": n}
