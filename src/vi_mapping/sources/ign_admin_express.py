"""Communes et arrondissements de Paris : contours, Siren, EPCI, population (IGN Admin Express + Insee)."""

from __future__ import annotations

from ..db import upsert
from ..outils.wfs import entites, url_entite
from .base import Compteurs, Contexte, connecteur

COMMUNE = "ADMINEXPRESS-COG-CARTO.LATEST:commune"
ARRONDISSEMENT = "ADMINEXPRESS-COG-CARTO.LATEST:arrondissement_municipal"


@connecteur("ign_admin_express")
def collecter(ctx: Contexte) -> Compteurs:
    region = ctx.idf.region.code
    communes = []
    for p, geom in entites(ctx.http, COMMUNE, f"code_insee_de_la_region='{region}'", tri="code_insee"):
        epci = (p["codes_siren_des_epci"] or "").split("/")[0] or None
        communes.append({
            "code_insee": p["code_insee"],
            "nom": p["nom_officiel"],
            "type": "commune",
            "commune_mere": None,
            "departement": p["code_insee_du_departement"],
            "siren": p["code_siren"],
            "epci_siren": epci,
            "population": p["population"],
            "population_annee": int(p["date_du_recensement"][:4]) if p["date_du_recensement"] else None,
            "code_postal": p["code_postal"],
            "geom": geom,
            **ctx.provenance(url_entite(COMMUNE, "code_insee", p["code_insee"])),
        })
    paris = next(c for c in communes if c["code_insee"] == "75056")
    arrondissements = [
        {
            "code_insee": p["code_insee"],
            "nom": p["nom_officiel"],
            "type": "arrondissement",
            "commune_mere": "75056",
            "departement": "75",
            "siren": paris["siren"],
            "epci_siren": paris["epci_siren"],
            "population": p["population"],
            "population_annee": paris["population_annee"],
            "code_postal": p["code_postal"],
            "geom": geom,
            **ctx.provenance(url_entite(ARRONDISSEMENT, "code_insee", p["code_insee"])),
        }
        for p, geom in entites(
            ctx.http, ARRONDISSEMENT, "code_insee_de_la_commune_de_rattach='75056'", tri="code_insee"
        )
    ]
    n = upsert(ctx.conn, "commune", communes, ["code_insee"])
    n += upsert(ctx.conn, "commune", arrondissements, ["code_insee"])
    # Superficie calculée sur le contour : le cadastre manque pour les arrondissements.
    ctx.conn.execute("UPDATE commune SET superficie_km2 = ST_Area(geom::geography) / 1e6")
    supprimees = ctx.purger("commune")
    return {"communes": len(communes), "arrondissements": len(arrondissements), "ecrites": n,
            "supprimees": supprimees}
