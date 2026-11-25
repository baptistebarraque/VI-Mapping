"""Site web officiel et contacts génériques des mairies (annuaire de l'administration, DILA).

Seuls le nom, le code commune, le site, le standard téléphonique et l'adresse e-mail générique de la mairie sont
demandés : coordonnées institutionnelles publiées pour joindre le service, jamais celles d'une personne.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from ..outils.opendatasoft import exporter
from .base import Compteurs, Contexte, connecteur

RESEAUX_SOCIAUX = ("facebook.", "instagram.", "twitter.", "x.com", "linkedin.", "youtube.")
EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


@dataclass(frozen=True, order=True)
class Mairie:
    longueur_nom: int  # plusieurs mairies (annexes, déléguées) : la fiche au nom le plus court est la principale
    fiche: str
    site: str | None = field(compare=False)
    telephone: str | None = field(compare=False)
    email: str | None = field(compare=False)


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
    """Premier numéro, chiffres groupés par deux (« 01 34 33 44 00 »)."""
    for tel in json.loads(brut) if brut else []:
        chiffres = re.sub(r"\D", "", tel.get("valeur") or "")
        if chiffres.startswith("33") and len(chiffres) == 11:
            chiffres = "0" + chiffres[2:]
        if len(chiffres) == 10 and chiffres.startswith("0"):
            return " ".join(chiffres[i:i + 2] for i in range(0, 10, 2))
    return None


def premier_email(brut: str | None) -> str | None:
    for email in re.split(r"[;,\s]+", brut or ""):
        if EMAIL.match(email.strip()):
            return email.strip().lower()
    return None


@connecteur("annuaire_administration", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    mairies: dict[str, list[Mairie]] = {}
    vues = 0
    for dep in ctx.idf.departements:
        for s in exporter(
            ctx.http, ctx.config.url,
            where=f'startswith(code_insee_commune,"{dep}") and pivot LIKE "%mairie%"',
            select="nom,pivot,site_internet,telephone,adresse_courriel,url_service_public",
        ):
            vues += 1
            candidat = Mairie(
                len(s["nom"]), s["url_service_public"] or ctx.config.url, premier_site(s["site_internet"]),
                premier_telephone(s["telephone"]), premier_email(s["adresse_courriel"]),
            )
            for pivot in json.loads(s["pivot"] or "[]"):
                if pivot.get("type_service_local") != "mairie":
                    continue
                for commune in pivot.get("code_insee_commune", []):
                    mairies.setdefault(commune, []).append(candidat)
    avec_site = {c: m for c, liste in mairies.items() if (m := min((x for x in liste if x.site), default=None))}
    avec_contact = {
        c: m for c, liste in mairies.items() if (m := min((x for x in liste if x.telephone or x.email), default=None))
    }
    sites = ctx.enrichir("commune", [
        {"code_insee": commune, "site_web": m.site, "provenance": ctx.provenance_json(m.fiche)}
        for commune, m in avec_site.items()
    ], "code_insee", "site_web")
    contacts = ctx.enrichir("commune", [
        {"code_insee": commune, "mairie_telephone": m.telephone, "mairie_email": m.email,
         "provenance": ctx.provenance_json(m.fiche)}
        for commune, m in avec_contact.items()
    ], "code_insee", "contact_mairie")
    return {"mairies": vues, "communes_avec_site": sites, "communes_avec_contact": contacts}
