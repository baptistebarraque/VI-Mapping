"""Conseils locaux FCPE publiés par les fédérations départementales 93 et 95 (nom, commune, site web).

Les autres fédérations franciliennes n'ont pas d'annuaire joignable ou interdisent la réutilisation
(voir docs/SOURCES.md). Les pages de réseaux sociaux ne sont ni visitées ni conservées.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from rapidfuzz import fuzz

from ..db import upsert
from ..outils.http import Cadence
from ..outils.motifs import niveau_scolaire, nom_propre
from ..outils.texte import normaliser, propre, sans_contact, site_web
from ..sources.base import Compteurs, Contexte, connecteur
from .page import Contenu, extraire
from .robot import Refus, SiteWeb

PAGES = {
    "93": "https://fcpe93.fr/des-nouvelles-des-conseils-locaux-et-unions-de-coordination-locale/",
    "95": "https://www.fcpe95.com/conseils-locaux/sites-des-conseils-locaux/",
}
_PREFIXES = re.compile(r"^(?:(?:fb|site|blog|page)\s+)*(?:(?:cl|conseil local)\s+)?", re.I)
_UNION = re.compile(r"\bu ?c ?l?\b|\bunion\b|\bcoordination\b")
_FIN = re.compile(r"^(annuler|laisser un commentaire|rechercher|commentaires?)\b", re.I)
_ADRESSE_WEB = re.compile(r"(?:https?://)?[\w.-]+\.[a-z]{2,}(?:/\S*)?")
_HEBERGEURS = re.compile(r"\.(over-blog|blogspot|wordpress|e-monsite|fcpe9[35]|sitew|free)\.(com|fr)$")
_ANNUAIRES = re.compile(r"(^|\.)(autoyas|pagesjaunes|net1901)\.(com|fr|org)$")  # ne sont pas le site de l'association


@dataclass(frozen=True)
class Conseil:
    commune: str
    nom: str
    site: str | None
    niveau: str


def trouver_commune(texte: str, communes: dict[str, str]) -> str | None:
    """Code Insee d'un nom de commune, exact ou abrégé sans ambiguïté (« Montigny », « Enghien »)."""
    n = normaliser(texte)
    if len(n) < 3:
        return None
    if n in communes:
        return communes[n]
    proches = {code for nom, code in communes.items() if nom.startswith(n + " ")}
    return proches.pop() if len(proches) == 1 else None


def lire_conseils(
    c: Contenu, communes: dict[str, str], ecoles: dict[str, list[str]] | None = None
) -> list[Conseil]:
    """Parcourt « Commune : libellé ; libellé ; … ».

    `communes` : {nom normalisé: code Insee} du département ; `ecoles` : noms propres d'écoles par commune.
    """
    liens: dict[str, str] = {}
    for url, libelle in c.liens:
        liens.setdefault(libelle, url)
    noms = {code: nom for nom, code in communes.items()}
    commune: str | None = None
    trouves: dict[tuple[str, str], Conseil] = {}
    i = 0
    while i < len(c.lignes):
        ligne, suivante = c.lignes[i], c.lignes[i + 1] if i + 1 < len(c.lignes) else ""
        i += 1
        if _FIN.match(ligne):
            break
        # « Ville : », « Ville » puis « : », ou nom coupé en deux par la mise en page (« Noisy-le-Se » « c : »)
        entier = ligne.rstrip(" :")
        if ligne.endswith(":") or suivante.startswith(":"):
            if m := re.search(r"pour la ville de (.+?)(?: sur\b.*)?$", entier, re.I):
                entier = m[1]
            if code := trouver_commune(entier, communes):
                commune = code
                continue
        if (
            re.fullmatch(r"\w{1,3}\s*:", suivante) and ligne not in liens
            and (code := trouver_commune(ligne + suivante.rstrip(" :"), communes))
        ):
            commune, i = code, i + 1
            continue
        if commune is None or ligne not in liens or not re.search(r"[a-zA-Z]{2}", ligne):
            continue
        site = site_web(liens[ligne])
        if site and _ANNUAIRES.search(urlsplit(site).netloc):
            site = None
        if _ADRESSE_WEB.fullmatch(ligne):
            nom = nom_dans_url(ligne, noms[commune], (ecoles or {}).get(commune, []))
        else:
            nom = propre(_PREFIXES.sub("", sans_contact(ligne) or ""))
        if nom and fuzz.ratio(re.sub(r"^fcpe ", "", normaliser(nom)), noms[commune]) >= 88:
            nom = None  # le libellé ne cite que la commune
        union = nom is None or bool(_UNION.search(normaliser(nom)))
        libelle = "FCPE, union de coordination locale" if union else f"Conseil local FCPE {nom}"
        niveau = "indetermine" if union else niveau_scolaire(normaliser(nom), "")
        trouves.setdefault((commune, normaliser(libelle)), Conseil(commune, libelle, site, niveau))
    return list(trouves.values())


def nom_dans_url(adresse: str, commune: str, ecoles: list[str]) -> str | None:
    """École citée par l'adresse d'un blog : « fcpepaulbertmontigny95.blogspot.com » → « Paul Bert »."""
    hote = re.sub(r"^(?:https?://)?(?:www\.)?", "", adresse).split("/")[0]
    compact = normaliser(_HEBERGEURS.sub("", hote)).replace(" ", "")
    if "college" in compact or "lycee" in compact:
        return "collège" if "college" in compact else "lycée"
    candidats = [e for e in ecoles if len(normaliser(e)) >= 5 and normaliser(e).replace(" ", "") in compact]
    return max(candidats, key=len) if candidats else None


@connecteur("fcpe_departements", depend_de=["ign_admin_express", "annuaire_education"])
def collecter(ctx: Contexte) -> Compteurs:
    cadence = Cadence(ctx.idf.scraping.delai_s)
    compte: Counter[str] = Counter()
    refuses = 0
    for dep, url in PAGES.items():
        communes = {
            normaliser(r["nom"]): r["code_insee"]
            for r in ctx.conn.execute(
                "SELECT code_insee, nom FROM commune WHERE departement = %s AND type = 'commune'", (dep,))
        }
        ecoles: dict[str, list[str]] = defaultdict(list)
        for e in ctx.conn.execute("SELECT commune, nom FROM ecole WHERE departement = %s", (dep,)):
            ecoles[e["commune"]].append(nom_propre(e["nom"]))
        conseils: list[Conseil] = []
        statut, detail, pages, interdites = "ok", None, 0, 0
        with SiteWeb(url, cadence=cadence) as site:
            try:
                page = site.lire(url, premiere=True)
                if page is not None:
                    contenu = extraire(page.html, page.url, aujourdhui=ctx.debut.date())
                    conseils = lire_conseils(contenu, communes, ecoles)
            except Refus as r:
                statut, detail = r.statut, r.detail
            if statut == "ok" and not conseils:
                statut = "vide"
            hote, pages, interdites = site.hote, site.pages_lues, site.pages_interdites
        ctx.conn.execute(
            """INSERT INTO crawl_site (hote, objet_type, objet_id, url_depart, statut, pages_visitees,
                                       pages_interdites, detail, visite_le)
               VALUES (%s, 'federation', %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (objet_type, objet_id, hote) DO UPDATE SET url_depart = EXCLUDED.url_depart,
                 statut = EXCLUDED.statut, pages_visitees = EXCLUDED.pages_visitees,
                 pages_interdites = EXCLUDED.pages_interdites, detail = EXCLUDED.detail,
                 visite_le = EXCLUDED.visite_le""",
            (hote, f"fcpe{dep}", url, statut, pages, interdites, detail, ctx.debut),
        )
        lignes: list[dict[str, Any]] = []
        for c in conseils:
            cle = hashlib.sha1(f"{c.commune}|{normaliser(c.nom)}".encode()).hexdigest()[:16]
            lignes.append({
                "id": f"fcpe{dep}:{cle}",
                "rna": None,
                "siren": None,
                "nom": c.nom,
                "objet": None,
                "siege": None,
                "commune": c.commune,
                "federation": "FCPE",
                "niveau": c.niveau,
                "date_creation": None,
                "site_web": c.site,
                "geom": None,
                **ctx.provenance(url),
            })
        upsert(ctx.conn, "asso_parents", lignes, ["id"])
        compte[f"conseils_{dep}"] = len(lignes)
        compte["avec_site"] += sum(x["site_web"] is not None for x in lignes)
        refuses += statut != "ok"
        if statut == "ok":
            ctx.purger("asso_parents", f"id LIKE 'fcpe{dep}:%%'")
    compte["sites_refuses"] = refuses
    return dict(compte)
