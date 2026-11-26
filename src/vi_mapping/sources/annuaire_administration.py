"""Site web officiel et contacts des mairies, des départements et de la région (annuaire de l'administration, DILA).

Nom, code commune, site, téléphone, adresse e-mail et formulaire de contact sont demandés, tels que l'annuaire les
publie : une adresse nominative est gardée.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from ..db import upsert
from ..outils.opendatasoft import exporter
from ..outils.texte import email_de_contact, propre, site_web, telephone
from .base import Compteurs, Contexte, connecteur

RESEAUX_SOCIAUX = ("facebook.", "instagram.", "twitter.", "x.com", "linkedin.", "youtube.")


@dataclass(frozen=True, order=True)
class Mairie:
    longueur_nom: int  # plusieurs mairies (annexes, déléguées) : la fiche au nom le plus court est la principale
    fiche: str
    site: str | None = field(compare=False)
    telephone: str | None = field(compare=False)
    email: str | None = field(compare=False)
    formulaire: str | None = field(compare=False)


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


def premier_telephone(brut: str | None) -> str | None:
    """Premier numéro lisible de la liste."""
    return next((t for tel in (json.loads(brut) if brut else []) if (t := telephone(tel.get("valeur")))), None)


def region_et_departements(ctx: Contexte) -> list[dict[str, Any]]:
    """Conseil régional et conseils départementaux d'Île-de-France (« cr » et « cg » dans l'annuaire)."""
    sirens = {r["departement"]: r["siren"] for r in ctx.conn.execute(
        "SELECT departement, siren FROM commune WHERE departement = '75' AND siren IS NOT NULL")}
    lignes = []
    for pivot, type_ in (("cr", "region"), ("cg", "departement")):
        for s in exporter(
            ctx.http, ctx.config.url, where=f'pivot LIKE "%\\"{pivot}\\"%"',
            select="nom,pivot,siren,site_internet,telephone,adresse_courriel,formulaire_contact,url_service_public",
        ):
            sieges = [c for p in json.loads(s["pivot"] or "[]") if p.get("type_service_local") == pivot
                      for c in p.get("code_insee_commune", [])]
            dep = next((c[:2] for c in sieges if c[:2] in ctx.idf.departements), None)
            siren = s["siren"] or sirens.get(dep or "")  # Paris : à la fois commune et département
            if dep is None or not siren:
                continue
            lignes.append({
                "siren": siren, "type": type_, "nom": propre(s["nom"].replace(" - ", " — ")),
                "departement": dep if type_ == "departement" else None, "communes": [],
                "telephone": premier_telephone(s["telephone"]), "email": email_de_contact(s["adresse_courriel"]),
                "site_web": premier_site(s["site_internet"]), "formulaire": site_web(s["formulaire_contact"]),
                **ctx.provenance(s["url_service_public"]),
            })
    return lignes


@connecteur("annuaire_administration", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    mairies: dict[str, list[Mairie]] = {}
    vues = 0
    for dep in ctx.idf.departements:
        for s in exporter(
            ctx.http, ctx.config.url,
            where=f'startswith(code_insee_commune,"{dep}") and pivot LIKE "%mairie%"',
            select="nom,pivot,site_internet,telephone,adresse_courriel,formulaire_contact,url_service_public",
        ):
            vues += 1
            candidat = Mairie(
                len(s["nom"]), s["url_service_public"] or ctx.config.url, premier_site(s["site_internet"]),
                premier_telephone(s["telephone"]), email_de_contact(s["adresse_courriel"]),
                site_web(s["formulaire_contact"]),
            )
            for pivot in json.loads(s["pivot"] or "[]"):
                if pivot.get("type_service_local") != "mairie":
                    continue
                for commune in pivot.get("code_insee_commune", []):
                    mairies.setdefault(commune, []).append(candidat)
    avec_site = {c: m for c, liste in mairies.items() if (m := min((x for x in liste if x.site), default=None))}
    avec_contact = {
        c: m for c, liste in mairies.items()
        if (m := min((x for x in liste if x.telephone or x.email or x.formulaire), default=None))
    }
    sites = ctx.enrichir("commune", [
        {"code_insee": commune, "site_web": m.site, "provenance": ctx.provenance_json(m.fiche)}
        for commune, m in avec_site.items()
    ], "code_insee", "site_web")
    contacts = ctx.enrichir("commune", [
        {"code_insee": commune, "mairie_telephone": m.telephone, "mairie_email": m.email,
         "mairie_formulaire": m.formulaire, "provenance": ctx.provenance_json(m.fiche)}
        for commune, m in avec_contact.items()
    ], "code_insee", "contact_mairie")
    organismes = region_et_departements(ctx)
    upsert(ctx.conn, "organisme", organismes, ["siren"])
    return {"mairies": vues, "communes_avec_site": sites, "communes_avec_contact": contacts,
            "organismes": len(organismes), "supprimes": ctx.purger("organisme")}
