"""Indice de position sociale (IPS) des écoles, dernière rentrée publiée pour chacune.

L'IPS est calculé sur les élèves de CM2 : les écoles maternelles n'en ont pas.
"""

from __future__ import annotations

from ..outils.opendatasoft import exporter, url_fiche
from .base import Compteurs, Contexte, connecteur


@connecteur("ips_ecoles", depend_de=["annuaire_education"])
def collecter(ctx: Contexte) -> Compteurs:
    base = ctx.config.url
    # « code_region » y est un code académique, pas le code Insee : on filtre par département.
    codes = ",".join(f'"{forme}"' for d in ctx.idf.departements for forme in (d, f"0{d}"))
    lignes = exporter(ctx.http, base, where=f"code_du_departement in ({codes})", select="uai,ips,rentree_scolaire")
    derniers: dict[str, dict[str, str]] = {}
    for e in lignes:
        try:
            float(e["ips"])
        except (TypeError, ValueError):
            continue  # « NS » : non significatif
        if e["uai"] not in derniers or e["rentree_scolaire"] > derniers[e["uai"]]["rentree_scolaire"]:
            derniers[e["uai"]] = e
    n = ctx.enrichir("ecole", [
        {
            "uai": uai,
            "ips": float(e["ips"]),
            "ips_rentree": e["rentree_scolaire"],
            "provenance": ctx.provenance_json(url_fiche(base, "uai", uai)),
        }
        for uai, e in derniers.items()
    ], "uai", "ips")
    return {"lignes": len(lignes), "ecoles": n}
