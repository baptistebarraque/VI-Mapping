"""Sites web des associations de parents : date de dernière activité visible.

Seule la date est conservée. Un site partagé (blog de fédération, site de mairie) n'est visité qu'une fois.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urljoin, urlsplit

from psycopg.types.json import Jsonb

from ..outils.http import Cadence
from ..outils.texte import site_web
from ..sources.base import Compteurs, Contexte, connecteur
from .campagne import DELAI_ENTRE_VISITES, plafond
from .page import date_la_plus_recente, extraire, iso
from .robot import Refus, SiteWeb, domaine
from .sites_mairies import urls_sitemap

PAGES_MAX = 4
_FLUX = re.compile(
    r"""<link[^>]+type=["']application/(?:rss|atom)\+xml["'][^>]*href=["']([^"']+)["']""", re.I)
_DATE_FLUX = re.compile(r"<(?:pubDate|updated|published|lastBuildDate|dc:date)>([^<]+)<", re.I)
_ACTU = re.compile(r"\bactu|\bnews\b|\bblog\b|\barticles?\b|\bagenda\b", re.I)
_RFC822 = re.compile(r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w* (20\d{2})\b")
_MOIS_EN = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
# Page d'un hébergeur, d'un annuaire ou d'une mairie : sa date ne dit rien de l'association
_HEBERGEUR = re.compile(r"(^|\.)(assolib|net1901|helloasso|autoyas|pagesjaunes|assoconnect)\.(com|fr|org)$")


@dataclass
class Visite:
    hote: str
    statut: str = "ok"
    detail: str | None = None
    pages: int = 0
    interdites: int = 0
    activite: date | None = None
    url: str | None = None


def dates_flux(xml: str, aujourdhui: date) -> list[date]:
    dates = []
    for brut in _DATE_FLUX.findall(xml):
        m = _RFC822.search(brut)
        if d := iso(f"{m[3]}-{_MOIS_EN[m[2]]:02d}-{int(m[1]):02d}" if m else brut, aujourdhui):
            dates.append(d)
    return dates


def visiter(url: str, cadence: Cadence, aujourdhui: date) -> Visite:
    with SiteWeb(url, cadence=cadence) as site:
        v = Visite(site.hote)
        try:
            page = site.lire(url, premiere=True)
            if page is None:
                v.statut = "vide"
            else:
                contenu = extraire(page.html, page.url, aujourdhui=aujourdhui)
                trouvees = [(d, page.url)] if (d := date_la_plus_recente(page.html, contenu, aujourdhui)) else []
                if m := _FLUX.search(page.html):  # flux RSS annoncé par la page : la date la plus fiable
                    flux = urljoin(page.url, m[1].replace("&amp;", "&"))
                    if (xml := site.lire_xml(flux)) and (dates := dates_flux(xml, aujourdhui)):
                        trouvees.append((max(dates), flux))
                if not trouvees:
                    dates_site = [(d, u) for u, d in urls_sitemap(site, aujourdhui) if d]
                    trouvees += [max(dates_site)] if dates_site else []
                if not trouvees:
                    for lien in dict.fromkeys(u for u, t in contenu.liens if _ACTU.search(t) and site.meme_site(u)):
                        if site.pages_lues >= PAGES_MAX:
                            break
                        if (p := site.lire(lien)) is None:
                            continue
                        c = extraire(p.html, p.url, aujourdhui=aujourdhui)
                        if d := date_la_plus_recente(p.html, c, aujourdhui):
                            trouvees.append((d, p.url))
                if trouvees:
                    v.activite, v.url = max(trouvees)
        except Refus as r:
            v.statut, v.detail = r.statut, r.detail or None
        v.hote, v.pages, v.interdites = site.hote, site.pages_lues, site.pages_interdites
        return v


@connecteur("sites_assos", depend_de=["rna", "fcpe_departements"])
def collecter(ctx: Contexte) -> Compteurs:
    # Les sites des mairies ne disent rien d'une association : écartés.
    mairies = {
        domaine(urlsplit(r["site_web"]).netloc)
        for r in ctx.conn.execute("SELECT site_web FROM commune WHERE site_web IS NOT NULL")
    }
    assos: dict[str, list[str]] = defaultdict(list)
    for r in ctx.conn.execute(
        """SELECT a.id, a.site_web FROM asso_parents a
           LEFT JOIN crawl_site v ON v.objet_type = 'asso_parents' AND v.objet_id = a.id
           WHERE a.site_web IS NOT NULL AND a.niveau <> 'second_degre'
             AND (v.visite_le IS NULL OR v.visite_le < %s OR %s)
           ORDER BY a.id""",
        (ctx.debut - DELAI_ENTRE_VISITES, bool(ctx.options.get("forcer"))),
    ):
        url = site_web(r["site_web"])
        hote = domaine(urlsplit(url).netloc) if url else ""
        if url and hote not in mairies and not _HEBERGEUR.search(hote):
            assos[url.rstrip("/")].append(r["id"])
    cibles = list(assos)
    cibles = cibles[: plafond(ctx, "asso_parents", len(cibles))]
    cadence = Cadence(ctx.idf.scraping.delai_s)
    aujourdhui = ctx.debut.date()
    compte: Counter[str] = Counter(sites=len(cibles))
    with ThreadPoolExecutor(ctx.idf.scraping.sites_en_parallele) as pool:
        taches = {pool.submit(visiter, u, cadence, aujourdhui): u for u in cibles}
        for tache in as_completed(taches):
            url = taches[tache]
            try:
                v = tache.result()
            except Exception as e:  # un site mal formé ne doit pas interrompre la campagne
                v = Visite(urlsplit(url).netloc, "erreur_http", f"{type(e).__name__}: {e}"[:200])
            for id_ in assos[url]:
                enregistrer(ctx, id_, url, v)
            ctx.conn.commit()
            compte[f"site_{v.statut}"] += 1
            compte["datees"] += v.activite is not None
            compte["actives_12_mois"] += v.activite is not None and aujourdhui - v.activite < timedelta(days=366)
    return dict(compte)


def enregistrer(ctx: Contexte, id_: str, url: str, v: Visite) -> None:
    if v.statut in ("ok", "vide"):
        ctx.conn.execute(
            "UPDATE asso_parents SET derniere_activite = NULL, derniere_activite_url = NULL, "
            "provenances = provenances - 'activite' WHERE id = %s", (id_,),
        )
    if v.activite is not None:
        ctx.conn.execute(
            "UPDATE asso_parents SET derniere_activite = %s, derniere_activite_url = %s, "
            "provenances = provenances || jsonb_build_object('activite', %s::jsonb) WHERE id = %s",
            (v.activite, (v.url or url)[:1000], Jsonb(ctx.provenance_json(v.url or url)), id_),
        )
    ctx.conn.execute(
        """INSERT INTO crawl_site (hote, objet_type, objet_id, url_depart, statut, pages_visitees, pages_interdites,
                                   detail, visite_le)
           VALUES (%s, 'asso_parents', %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (objet_type, objet_id, hote) DO UPDATE SET url_depart = EXCLUDED.url_depart,
             statut = EXCLUDED.statut, pages_visitees = EXCLUDED.pages_visitees,
             pages_interdites = EXCLUDED.pages_interdites, detail = EXCLUDED.detail, visite_le = EXCLUDED.visite_le""",
        (v.hote, id_, url, v.statut, v.pages, v.interdites, v.detail, ctx.debut),
    )
