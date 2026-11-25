"""Site web officiel des mairies (annuaire de l'administration, DILA).

Seuls le nom, le code commune et le site sont demandés : ni e-mail, ni téléphone.
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from ..outils.opendatasoft import exporter
from .base import Compteurs, Contexte, connecteur

RESEAUX_SOCIAUX = ("facebook.", "instagram.", "twitter.", "x.com", "linkedin.", "youtube.")


def premier_site(brut: str | None) -> str | None:
    """Première adresse http(s) exploitable, hors réseaux sociaux."""
    for site in json.loads(brut) if brut else []:
        url = (site.get("valeur") or "").strip()
        if url and "://" not in url:
            url = f"https://{url}"
        hote = urlsplit(url).netloc.lower()
        if url.startswith("http") and "." in hote and not any(r in hote for r in RESEAUX_SOCIAUX):
            return url
    return None


@connecteur("annuaire_administration", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    sites: dict[str, tuple[int, str, str]] = {}
    mairies = 0
    for dep in ctx.idf.departements:
        for s in exporter(
            ctx.http, ctx.config.url,
            where=f'startswith(code_insee_commune,"{dep}") and pivot LIKE "%mairie%"',
            select="nom,pivot,site_internet,url_service_public",
        ):
            mairies += 1
            url = premier_site(s["site_internet"])
            if url is None:
                continue
            for pivot in json.loads(s["pivot"] or "[]"):
                if pivot.get("type_service_local") != "mairie":
                    continue
                for commune in pivot.get("code_insee_commune", []):
                    # Plusieurs mairies (annexes, déléguées) : la fiche au nom le plus court est la principale.
                    candidat = (len(s["nom"]), url, s["url_service_public"] or ctx.config.url)
                    if commune not in sites or candidat < sites[commune]:
                        sites[commune] = candidat
    n = ctx.enrichir("commune", [
        {"code_insee": commune, "site_web": url, "provenance": ctx.provenance_json(fiche)}
        for commune, (_, url, fiche) in sites.items()
    ], "code_insee", "site_web")
    return {"mairies": mairies, "communes_avec_site": n}
