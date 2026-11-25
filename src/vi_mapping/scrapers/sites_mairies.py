"""Sites des mairies : signaux d'engagement alimentaire, périscolaire, délégations des élus.

Sont conservés : URL, titre, date, thème. Le contenu des pages ne l'est pas.
"""

from __future__ import annotations

import hashlib
import heapq
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from urllib.parse import unquote, urlsplit

from psycopg.types.json import Jsonb

from ..config import contact
from ..db import point, upsert
from ..outils import motifs
from ..outils.ban import Adresse, geocoder
from ..outils.http import Cadence
from ..outils.texte import normaliser, sans_contact
from ..sources.base import Compteurs, Contexte, connecteur
from . import themes
from .accueils import AccueilTrouve, lire_accueils
from .page import Contenu, extraire, iso
from .robot import Refus, SiteWeb, domaine

DELAI_ENTRE_VISITES = timedelta(days=25)
SITEMAPS_MAX = 5
URLS_MAX = 20_000


@dataclass
class Cible:
    commune: str
    nom: str
    url: str
    elus: dict[str, tuple[str, str]]  # {id: (prénom, nom) normalisés}
    maires: frozenset[str] = frozenset()


@dataclass
class Visite:
    hote: str
    statut: str = "ok"
    detail: str = ""
    pages: int = 0
    interdites: int = 0
    signaux: list[dict[str, Any]] = field(default_factory=list)
    delegations: dict[str, tuple[str, list[str], str]] = field(default_factory=dict)
    accueils: list[AccueilTrouve] = field(default_factory=list)
    pages_elus: int = 0


@connecteur("sites_mairies", depend_de=["annuaire_administration", "annuaire_education", "rne"])
def collecter(ctx: Contexte) -> Compteurs:
    cibles = a_visiter(ctx)
    maximum = ctx.limite or len(cibles)
    if contact() is None:
        maximum = min(maximum, ctx.idf.scraping.echantillon_sans_contact)
        ctx.note(f"VI_CONTACT absent : échantillon de {maximum} sites au plus")
    cibles = cibles[:maximum]
    compte: Counter[str] = Counter(sites=len(cibles))
    cadence = Cadence(ctx.idf.scraping.delai_s)
    aujourdhui = ctx.debut.date()
    with ThreadPoolExecutor(ctx.idf.scraping.sites_en_parallele) as pool:
        taches = {pool.submit(visiter, c, cadence, aujourdhui): c for c in cibles}
        for i, tache in enumerate(as_completed(taches), 1):
            cible = taches[tache]
            try:
                visite = tache.result()
            except Exception as e:  # un site mal formé ne doit pas interrompre la campagne
                visite = Visite(urlsplit(cible.url).netloc, "erreur_http", f"{type(e).__name__}: {e}"[:200])
            compte["accueils"] += enregistrer(ctx, cible, visite)
            ctx.conn.commit()  # reprise possible après interruption
            compte[f"site_{visite.statut}"] += 1
            compte["pages"] += visite.pages
            compte["signaux"] += len(visite.signaux)
            compte["delegations"] += len(visite.delegations)
            if i % 20 == 0:
                ctx.note(f"{i}/{len(cibles)} sites, {compte['signaux']} signaux")
    return dict(compte)


def a_visiter(ctx: Contexte) -> list[Cible]:
    """Sites non visités récemment, en commençant par les communes qui ont le plus d'élèves."""
    lignes = ctx.conn.execute(
        """
        SELECT c.code_insee, c.nom, c.site_web, coalesce(sum(e.nb_eleves), 0) AS eleves
        FROM commune c
        LEFT JOIN ecole e ON e.commune = c.code_insee OR (c.code_insee = '75056' AND e.departement = '75')
        LEFT JOIN crawl_site v ON v.objet_type = 'commune' AND v.objet_id = c.code_insee
        WHERE c.site_web IS NOT NULL AND (v.visite_le IS NULL OR v.visite_le < %s OR %s)
        GROUP BY 1, 2, 3 ORDER BY eleves DESC, c.code_insee
        """,
        (ctx.debut - DELAI_ENTRE_VISITES, bool(ctx.options.get("forcer"))),
    ).fetchall()
    cibles, vus = [], set()
    for r in lignes:
        p = urlsplit(r["site_web"])
        cle = (domaine(p.netloc), p.path.rstrip("/"))
        if cle in vus:  # Paris Centre : un site pour quatre arrondissements
            continue
        vus.add(cle)
        elus = ctx.conn.execute(
            "SELECT id, prenom, nom, fonction LIKE 'Maire%%' AS maire FROM elu WHERE commune = %s", (r["code_insee"],)
        ).fetchall()
        cibles.append(Cible(
            r["code_insee"], r["nom"], r["site_web"],
            {e["id"]: (normaliser(e["prenom"]), normaliser(e["nom"])) for e in elus},
            frozenset(e["id"] for e in elus if e["maire"]),  # un maire n'a pas de délégation
        ))
    return cibles


# --------------------------------------------------------------------------- visite d'un site
def visiter(cible: Cible, cadence: Cadence, aujourdhui: date) -> Visite:
    with SiteWeb(cible.url, cadence=cadence) as site:
        visite = Visite(site.hote)
        pages: list[tuple[str, Contenu]] = []
        try:
            parcourir(site, cible, visite, pages, aujourdhui)
        except Refus as r:
            visite.statut, visite.detail = r.statut, r.detail
        visite.hote = site.hote
        visite.pages, visite.interdites = site.pages_lues, site.pages_interdites
        if visite.statut == "ok" and not pages:
            visite.statut = "vide"
        visite.signaux = signaux(cible, pages)
        return visite


def canonique(url: str) -> str:
    p = urlsplit(url)
    return f"{domaine(p.netloc)}{p.path.rstrip('/')}{'?' + p.query if p.query else ''}".lower()


def parcourir(
    site: SiteWeb, cible: Cible, visite: Visite, pages: list[tuple[str, Contenu]], aujourdhui: date
) -> None:
    file: list[tuple[int, int, str, str]] = []   # (-priorité, ordre, url, catégorie)
    vues: set[str] = set()
    restant = {nom: maxi for nom, _, _, maxi in themes.CATEGORIES}
    dates_sitemap: dict[str, date] = {}

    def proposer(url: str, libelle: str, bonus: int = 0) -> None:
        cle = canonique(url)
        if cle in vues or not site.meme_site(url) or not themes.visitable(url):
            return
        if choix := themes.classer(url, libelle):
            vues.add(cle)
            heapq.heappush(file, (-(choix[1] * 10 + bonus), len(vues), url, choix[0]))

    accueil = site.lire(cible.url, premiere=True)
    if accueil is None:
        return
    vues.add(canonique(accueil.url))
    traiter(accueil.url, accueil.html, accueil.modifiee_http, cible, visite, pages, dates_sitemap, aujourdhui, proposer)
    for url, jour in urls_sitemap(site, aujourdhui):
        if jour:
            dates_sitemap[canonique(url)] = jour
        recent = jour is not None and (aujourdhui - jour).days < 730
        proposer(url, "", bonus=3 if recent else -3 if jour else 0)

    while file and site.pages_lues < site.c.pages_max_par_site:
        _, _, url, categorie = heapq.heappop(file)
        if restant[categorie] <= 0:
            continue
        restant[categorie] -= 1
        page = site.lire(url)
        if page is None:
            continue
        visite.pages_elus += categorie == "elus"
        traiter(page.url, page.html, page.modifiee_http, cible, visite, pages, dates_sitemap, aujourdhui, proposer)


def traiter(
    url: str, html: str, modifiee_http: date | None, cible: Cible, visite: Visite,
    pages: list[tuple[str, Contenu]], dates_sitemap: dict[str, date], aujourdhui: date, proposer: Any,
) -> None:
    contenu = extraire(html, url, aujourdhui=aujourdhui)
    if contenu.date is None:
        jour, origine = dates_sitemap.get(canonique(url)), "sitemap"
        if jour is None:
            jour, origine = modifiee_http, "http"
        if jour is not None:
            contenu = Contenu(**{**contenu.__dict__, "date": jour, "date_origine": origine})
    for lien, libelle in contenu.liens:
        proposer(lien, libelle, bonus=4)  # lien choisi par le site, préféré à une adresse du sitemap
    if contenu.noindex:  # la page demande à ne pas être référencée : liens suivis, rien de conservé
        return
    pages.append((url, contenu))
    visite.accueils.extend(lire_accueils(contenu, url))
    if re.search(r"\belus?\b|\bconseil municipal\b|\badjoint|\bmaire\b|\bequipe municipale\b|\bdelegation",
                 f"{contenu.titres} {themes.mots_url(url)}"):
        for id_, (texte, themes_elu) in themes.lire_delegations(contenu.lignes, cible.elus).items():
            if id_ not in cible.maires:
                visite.delegations.setdefault(id_, (texte, themes_elu, url))


def urls_sitemap(site: SiteWeb, aujourdhui: date) -> list[tuple[str, date | None]]:
    """Adresses publiées dans le sitemap, avec leur date de dernière modification."""
    a_lire = site.sitemaps()[:SITEMAPS_MAX]
    lus = 0
    urls: list[tuple[str, date | None]] = []
    while a_lire and lus < SITEMAPS_MAX and len(urls) < URLS_MAX:
        xml = site.lire_xml(a_lire.pop(0))
        lus += 1
        if xml is None:
            continue
        for bloc in re.findall(r"<(?:url|sitemap)>(.*?)</(?:url|sitemap)>", xml, re.S):
            loc = re.search(r"<loc>\s*(?:<!\[CDATA\[)?\s*(\S+?)\s*(?:\]\]>)?\s*</loc>", bloc)
            if not loc:
                continue
            url = loc[1].replace("&amp;", "&")
            if url.endswith((".xml", ".xml.gz")):
                # articles et pages d'abord ; les index d'images, d'auteurs ou d'étiquettes sont inutiles
                if url.endswith(".xml") and not re.search(r"author|tag|categor|image|media|attachment|user", url, re.I):
                    a_lire.append(url)
                continue
            lastmod = re.search(r"<lastmod>\s*([^<\s]+)", bloc)
            urls.append((url, iso(lastmod[1], aujourdhui) if lastmod else None))
    return urls[:URLS_MAX]


def signaux(cible: Cible, pages: list[tuple[str, Contenu]]) -> list[dict[str, Any]]:
    """Thèmes attestés, page par page. Un thème présent partout dans le texte est un habillage : écarté."""
    presence: Counter[str] = Counter()
    analyses = []
    for url, c in pages:
        corps = themes.themes_de(c.texte)
        entete = themes.themes_de(f"{c.titres} {themes.mots_url(url)}")
        presence.update(corps.keys())
        analyses.append((url, c, corps, entete))
    habillage = {t for t, n in presence.items() if len(pages) >= 6 and n > 0.6 * len(pages)}

    trouves: dict[tuple[str, str], dict[str, Any]] = {}
    for url, c, corps, entete in analyses:
        for theme in corps.keys() | entete.keys():
            dans_titre, n = theme in entete, corps.get(theme, 0)
            if not dans_titre and (theme in habillage or n < (1 if theme.startswith("periscolaire") else 2)):
                continue
            confiance = 0.5 + 0.2 * dans_titre + 0.1 * (n >= 3) + 0.1 * (c.date is not None)
            trouves[url, theme] = ligne(cible, url, theme, c.titre, themes.type_page(url, c.titres), max(n, 1),
                                        min(confiance, 0.9), c.date, c.date_origine)
        for lien, libelle in c.liens:  # documents PDF : seulement leur intitulé, jamais téléchargés
            if themes.est_document(lien) and lien.startswith("http"):
                for theme in themes.themes_de(f"{normaliser(libelle)} {themes.mots_url(lien)}"):
                    trouves.setdefault((lien, theme), ligne(
                        cible, lien, theme, titre_document(libelle, lien), "document", 1, 0.5, None, None))
    return list(trouves.values())


def titre_document(libelle: str, lien: str) -> str:
    """Libellé du lien, ou nom du fichier quand le libellé ne dit rien (« Télécharger »)."""
    if re.fullmatch(r"|(telecharger|consulter|voir|lire|ouvrir|document|pdf|ici|le|la|les|cliquez|fichier|\s)+",
                    normaliser(libelle)):
        return re.sub(r"[-_%\s]+", " ", unquote(urlsplit(lien).path).rsplit("/", 1)[-1].rsplit(".", 1)[0]).strip()
    return libelle


def titre_court(titre: str) -> str:
    """Titre de la page sans la signature du site (« L'été des potagers - Mairie de X | Site officiel »)."""
    return re.split(r"\s+[|–—-]\s+(?=(?:mairie|ville|site|commune|accueil|portail|la ville)\b)", titre, flags=re.I)[0]


def ligne(
    cible: Cible, url: str, theme: str, titre: str, type_page: str, n: int, confiance: float,
    jour: date | None, origine: str | None,
) -> dict[str, Any]:
    url = url[:1000]
    return {
        "id": "web:" + hashlib.sha1(f"{url}|{theme}".encode()).hexdigest()[:20],
        "commune": cible.commune,
        "titre": titre_court(sans_contact(titre) or "")[:200] or None,
        "date_page": jour,
        "date_origine": origine,
        "type_page": type_page,
        "theme": theme,
        "occurrences": n,
        "_url": url,
        "_confiance": round(confiance, 2),
    }


# --------------------------------------------------------------------------- écriture
def enregistrer(ctx: Contexte, cible: Cible, v: Visite) -> int:
    """Écrit les trouvailles d'une visite ; retourne le nombre d'accueils localisés."""
    lignes = [
        {**{k: x for k, x in s.items() if not k.startswith("_")},
         **ctx.provenance(s["_url"], confiance=s["_confiance"])}
        for s in v.signaux
    ]
    upsert(ctx.conn, "signal_web", lignes, ["id"])
    if v.statut == "ok":
        ctx.conn.execute(
            "DELETE FROM signal_web WHERE commune = %s AND source = %s AND collecte_le < %s",
            (cible.commune, ctx.code, ctx.debut),
        )
        if v.pages_elus:
            ctx.conn.execute(
                "UPDATE elu SET delegation = NULL, delegation_themes = '{}', provenances = provenances - 'delegation' "
                "WHERE commune = %s AND provenances ? 'delegation'", (cible.commune,),
            )
    for id_, (texte, themes_elu, url) in v.delegations.items():
        ctx.conn.execute(
            "UPDATE elu SET delegation = %s, delegation_themes = %s, "
            "provenances = provenances || jsonb_build_object('delegation', %s::jsonb) WHERE id = %s",
            (texte, themes_elu, Jsonb(ctx.provenance_json(url, confiance=0.6)), id_),
        )
    ctx.conn.execute(
        """INSERT INTO crawl_site (hote, objet_type, objet_id, url_depart, statut, pages_visitees, pages_interdites,
                                   detail, visite_le)
           VALUES (%s, 'commune', %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (objet_type, objet_id, hote) DO UPDATE SET url_depart = EXCLUDED.url_depart,
             statut = EXCLUDED.statut, pages_visitees = EXCLUDED.pages_visitees,
             pages_interdites = EXCLUDED.pages_interdites, detail = EXCLUDED.detail, visite_le = EXCLUDED.visite_le""",
        (v.hote, cible.commune, cible.url, v.statut, v.pages, v.interdites, v.detail or None, ctx.debut),
    )
    return enregistrer_accueils(ctx, cible, v)


def enregistrer_accueils(ctx: Contexte, cible: Cible, v: Visite) -> int:
    adresses = {a: Adresse(a.adresse, "", cible.commune) for a in v.accueils}
    positions = geocoder(ctx.conn, ctx.http, adresses.values())
    lignes: dict[str, dict[str, Any]] = {}
    for a in v.accueils:
        pos = positions.get(adresses[a])
        dans_commune = pos is not None and (
            pos.code_insee == cible.commune or (cible.commune == "75056" and pos.code_insee.startswith("751")))
        if pos is None or not dans_commune or pos.type not in ("housenumber", "street") or pos.score < 0.55:
            continue
        cle = hashlib.sha1(f"{cible.commune}|{normaliser(a.nom)}|{pos.libelle}".encode()).hexdigest()[:20]
        deja = lignes.get(cle, {})  # même lieu vu sur plusieurs pages : les « oui » se cumulent
        nom = normaliser(a.nom)
        lignes[cle] = {
            "id": f"web:{cle}",
            "nom": a.nom,
            "adresse": pos.libelle,
            "commune": pos.code_insee,
            "accueil_soir": deja.get("accueil_soir") or a.soir or motifs.accueil_soir(nom),
            "accueil_mercredi": deja.get("accueil_mercredi") or a.mercredi or motifs.accueil_mercredi(nom),
            "horaires": None,
            "exploitant": f"Commune de {cible.nom}" if a.municipal or deja.get("exploitant") else None,
            "geom": point(pos.lon, pos.lat),
            **ctx.provenance(a.url[:1000], confiance=0.6 * pos.confiance + 0.1),
        }
    upsert(ctx.conn, "accueil_periscolaire", lignes.values(), ["id"])
    if v.statut == "ok":
        ctx.conn.execute(
            "DELETE FROM accueil_periscolaire WHERE source = %s AND collecte_le < %s AND (commune = %s OR "
            "(%s = '75056' AND commune LIKE '751%%'))",
            (ctx.code, ctx.debut, cible.commune, cible.commune),
        )
    return len(lignes)
