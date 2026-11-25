"""Taille d'une campagne de visites."""

from __future__ import annotations

from datetime import timedelta

from ..config import contact
from ..sources.base import Contexte

DELAI_ENTRE_VISITES = timedelta(days=25)


def plafond(ctx: Contexte, objet_type: str, n: int) -> int:
    """Nombre de sites à visiter parmi `n`.

    Sans VI_CONTACT, le robot n'est joignable par personne : il s'en tient à un échantillon par mois, toutes
    exécutions confondues.
    """
    maximum = min(ctx.limite or n, n)
    if contact() is not None:
        return maximum
    deja = 0
    if not ctx.options.get("forcer"):
        r = ctx.conn.execute(
            "SELECT count(DISTINCT url_depart) AS n FROM crawl_site WHERE objet_type = %s AND visite_le >= %s",
            (objet_type, ctx.debut - DELAI_ENTRE_VISITES)).fetchone()
        deja = r["n"] if r else 0
    reste = max(0, ctx.idf.scraping.echantillon_sans_contact - deja)
    if reste < maximum:
        ctx.note(f"VI_CONTACT absent : {reste} sites de plus ce mois-ci au maximum ({deja} déjà visités)")
    return min(maximum, reste)
