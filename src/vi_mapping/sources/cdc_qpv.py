"""Complément : quartiers prioritaires dont le jeu régional n'a pas le contour (Caisse des Dépôts)."""

from __future__ import annotations

from ..db import upsert
from ..outils.opendatasoft import exporter, url_fiche
from .anct_qpv import ligne_qpv
from .base import Compteurs, Contexte, connecteur


@connecteur("cdc_qpv", depend_de=["anct_qpv"])
def collecter(ctx: Contexte) -> Compteurs:
    base = ctx.config.url
    connus = {
        r["id"] for r in ctx.conn.execute("SELECT id FROM dispositif WHERE type = 'qpv' AND source <> %s", (ctx.code,))
    }
    prefixes = [f"QN0{d}" for d in ctx.idf.departements]
    lignes = []
    for q in exporter(ctx.http, base, where=" or ".join(f'startswith(code_quartier,"{p}")' for p in prefixes)):
        if f"qpv:{q['code_quartier']}" in connus:
            continue
        # Sans contour publié nulle part, le quartier reste listé (par commune) mais non cartographié.
        lignes.append(ligne_qpv(
            q["code_quartier"], q["nom_quartier"], [q["code_insee_commune"]], q["geo_shape"],
            ctx.provenance(url_fiche(base, "code_quartier", q["code_quartier"])),
        ))
    n = upsert(ctx.conn, "dispositif", lignes, ["id"])
    return {"qpv_ajoutes": n, "sans_contour": sum(ligne["geom"] is None for ligne in lignes),
            "supprimes": ctx.purger("dispositif")}
