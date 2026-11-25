"""Rattachements automatiques : IRIS, QPV, doublons, accueils, associations de parents."""

from __future__ import annotations

from ..sources.base import Compteurs, Contexte, connecteur
from . import accueils, assos, doublons, spatial


@connecteur("rattachements", calcul=True)
def rattacher(ctx: Contexte) -> Compteurs:
    compte: Compteurs = {}
    for etape in (spatial, doublons, accueils, assos):
        compte |= etape.rattacher(ctx)
    ctx.conn.execute(
        "UPDATE gestionnaire_perisco g SET nb_accueils = (SELECT count(*) FROM accueil_periscolaire a "
        "WHERE a.gestionnaire_siren = g.siren AND a.doublon_de IS NULL)"
    )
    return compte
