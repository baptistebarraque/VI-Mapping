"""Visite polie d'un site public : robots.txt, réserve TDM, cadence, limites, arrêt devant un anti-robot.

Jamais de contournement : un refus (robots, TDM, captcha, 403, 429) met fin à la visite et il est journalisé.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

import httpx
from protego import Protego

from ..config import Scraping, config_idf, hotes_verrouilles
from ..outils.http import Cadence, user_agent

ANTI_ROBOT = re.compile(
    r"perfdrive\.com|captcha-delivery\.com|datadome|/cdn-cgi/challenge-platform|cf-chl-|just a moment\.\.\.|_incapsula_"
    r"|radware|validate\.perf|are you a (robot|human)|verify you are human|request unsuccessful\. incapsula"
    r"|attention required! \| cloudflare|anubis_challenge|checking your browser|/_challenge\b|pas un robot"
    r"|not a robot|sucuri website firewall|proof.of.work",
    re.I,
)
DUREE_MAX_S = 420  # garde-fou : temps total passé sur un site


class Refus(Exception):
    """Le site ne veut pas, ou ne peut pas, être visité. `statut` : valeur de crawl_site.statut."""

    def __init__(self, statut: str, detail: str = "") -> None:
        super().__init__(f"{statut} {detail}".strip())
        self.statut, self.detail = statut, detail


@dataclass(frozen=True)
class Page:
    url: str
    html: str
    modifiee_http: date | None


def hote_public(hote: str) -> bool:
    """Vrai si toutes les adresses de l'hôte sont publiques (pas de réseau local ni de boucle locale)."""
    try:
        infos = socket.getaddrinfo(hote, None, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


def domaine(hote: str) -> str:
    return hote.lower().removeprefix("www.")


class SiteWeb:
    """Un site et sa politique d'accès. À utiliser dans un seul thread."""

    def __init__(
        self, url: str, *, cadence: Cadence | None = None, scraping: Scraping | None = None, verifier_hote: bool = True
    ) -> None:
        self.c = scraping or config_idf().scraping
        self.url_depart = url
        self.hote = urlsplit(url).netloc.lower()
        self.pages_lues = 0
        self.pages_interdites = 0
        self._verifier_hote = verifier_hote
        self._robots: dict[str, Protego | None] = {}
        self._publics: dict[str, bool] = {}
        self._tdm: list[re.Pattern[str]] = []
        self._debut = time.monotonic()
        self._cadence = cadence or Cadence(self.c.delai_s)  # partagée entre sites d'un même hébergement
        self._delai_s = self.c.delai_s
        self._client = httpx.Client(
            headers={"User-Agent": user_agent(), "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                     "Accept-Language": "fr", "Accept-Encoding": "gzip, deflate"},
            timeout=httpx.Timeout(self.c.timeout_s, connect=10),
            follow_redirects=False,
        )

    def __enter__(self) -> SiteWeb:
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()

    # ------------------------------------------------------------------ politique d'accès
    def _robots_de(self, origine: str) -> Protego | None:
        """Règles robots.txt d'une origine (schéma + hôte) ; None = aucune règle."""
        if origine in self._robots:
            return self._robots[origine]
        hote = urlsplit(origine).netloc
        self._exiger_public(hote)
        regles: Protego | None = None
        try:
            r = self._brut(f"{origine}/robots.txt", suivre=3)
        except httpx.HTTPError as e:
            raise Refus("injoignable", f"robots.txt : {type(e).__name__}") from e
        if r.status_code in (401, 403, 429) or r.status_code >= 500:
            # RFC 9309 : 5xx = tout est interdit. 401/403/429 : refus traité comme tel, par prudence.
            raise Refus("robots_interdit", f"robots.txt : HTTP {r.status_code}")
        if r.status_code < 300 and "html" not in r.headers.get("content-type", ""):
            regles = Protego.parse(r.text[:512_000])
            attente = regles.crawl_delay(self.nom_robot) or 0
            debit = regles.request_rate(self.nom_robot)
            if debit and debit.requests:
                attente = max(attente, debit.seconds / debit.requests)
            self._delai_s = min(max(self._delai_s, float(attente)), 60)
        self._robots[origine] = regles
        self._lire_tdm(origine)
        return regles

    @property
    def nom_robot(self) -> str:
        return config_idf().http.nom_robot

    def _lire_tdm(self, origine: str) -> None:
        """Protocole TDMRep : /.well-known/tdmrep.json peut réserver des chemins."""
        try:
            r = self._brut(f"{origine}/.well-known/tdmrep.json")
        except httpx.HTTPError:
            return
        if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
            return
        try:
            regles = json.loads(r.text[:200_000])
        except ValueError:
            return
        for regle in regles if isinstance(regles, list) else []:
            if isinstance(regle, dict) and str(regle.get("tdm-reservation")) == "1":
                motif = re.escape(str(regle.get("location", "/"))).replace(r"\*", ".*").replace(r"\$", "$")
                self._tdm.append(re.compile(f"{re.escape(origine)}{motif}"))

    def _exiger_public(self, hote: str) -> None:
        nu = hote.split(":")[0]
        if any(nu == h or nu.endswith(f".{h}") for h in hotes_verrouilles()):
            raise Refus("cgu_interdit", f"{nu} : source verrouillée (config/sources.yaml)")
        if self._verifier_hote and nu not in self._publics:
            self._publics[nu] = hote_public(nu)
        if self._verifier_hote and not self._publics[nu]:
            raise Refus("injoignable", f"hôte introuvable ou non public : {nu}")

    def autorise(self, url: str) -> bool:
        p = urlsplit(url)
        regles = self._robots_de(f"{p.scheme}://{p.netloc}")
        if any(m.match(url) for m in self._tdm):
            raise Refus("tdm_reserve", "tdmrep.json")
        return regles is None or regles.can_fetch(url, self.nom_robot)

    def sitemaps(self) -> list[str]:
        p = urlsplit(self.url_depart)
        regles = self._robots_de(f"{p.scheme}://{self.hote}")
        declares = [u for u in (regles.sitemaps if regles else []) if self.meme_site(u)]
        return declares or [f"{p.scheme}://{self.hote}/sitemap.xml"]

    def meme_site(self, url: str) -> bool:
        p = urlsplit(url)
        return p.scheme in ("http", "https") and domaine(p.netloc) == domaine(self.hote)

    # ------------------------------------------------------------------ lecture
    def _brut(self, url: str, *, suivre: int = 0) -> httpx.Response:
        """Réponse tronquée à octets_max, avec cadence ; suit `suivre` redirections du même site."""
        if time.monotonic() - self._debut > DUREE_MAX_S:
            raise Refus("ok", "durée maximale atteinte")
        self._cadence.attendre(domaine(urlsplit(url).netloc), self._delai_s)
        with self._client.stream("GET", url) as r:
            corps = bytearray()
            for bloc in r.iter_bytes():
                corps += bloc
                if len(corps) > self.c.octets_max:
                    break
            r._content = bytes(corps[: self.c.octets_max])
        if suivre and r.is_redirect and "location" in r.headers:
            cible = urljoin(url, r.headers["location"])
            if domaine(urlsplit(cible).netloc) == domaine(urlsplit(url).netloc):
                return self._brut(cible, suivre=suivre - 1)
        return r

    def lire(self, url: str, *, premiere: bool = False) -> Page | None:
        """Page HTML, ou None si elle est interdite, absente, trop lourde ou d'un autre type.

        Une redirection de la page d'accueil vers un autre domaine (site déménagé) est suivie ;
        ailleurs, on ne sort jamais du site.
        """
        for _ in range(5):
            if not self.autorise(url):
                self.pages_interdites += 1
                if premiere:
                    raise Refus("robots_interdit", "page d'accueil exclue par robots.txt")
                return None
            try:
                r = self._brut(url)
            except httpx.HTTPError as e:
                if premiere:
                    raise Refus("injoignable", type(e).__name__) from e
                return None
            if r.is_redirect and "location" in r.headers:
                cible = urljoin(url, r.headers["location"])
                if not self.meme_site(cible):
                    if not premiere or urlsplit(cible).scheme not in ("http", "https"):
                        return None
                    if ANTI_ROBOT.search(cible):
                        raise Refus("anti_robot", "redirection vers un contrôle anti-robot")
                    self.hote = urlsplit(cible).netloc.lower()
                url = cible
                continue
            break
        else:
            return None
        texte = r.text
        if r.status_code in (403, 429, 503):
            controle = bool(ANTI_ROBOT.search(texte[:20_000]))
            if premiere or r.status_code == 429 or controle:
                statut = "anti_robot" if controle or r.status_code != 503 else "erreur_http"
                raise Refus(statut, f"HTTP {r.status_code}")
            return None
        if r.status_code >= 400:
            if premiere:
                raise Refus("erreur_http", f"HTTP {r.status_code}")
            return None
        if r.headers.get("tdm-reservation", "").strip() == "1":
            raise Refus("tdm_reserve", "en-tête tdm-reservation")
        if "html" not in r.headers.get("content-type", "html"):
            return None
        if len(texte) < 30_000 and ANTI_ROBOT.search(texte):
            raise Refus("anti_robot", "page de contrôle")
        if re.search(r"""<meta[^>]+name=["']tdm-reservation["'][^>]+content=["']1["']""", texte[:50_000], re.I):
            raise Refus("tdm_reserve", "balise tdm-reservation")
        self.pages_lues += 1
        return Page(url, texte, date_http(r.headers.get("last-modified")))

    def lire_xml(self, url: str) -> str | None:
        """Sitemap (texte), sous les mêmes règles ; None s'il est absent."""
        if not self.meme_site(url) or not self.autorise(url):
            return None
        try:
            r = self._brut(url, suivre=2)
        except httpx.HTTPError:
            return None
        if r.status_code != 200 or "<html" in r.text[:500].lower():
            return None
        return r.text


def date_http(entete: str | None) -> date | None:
    """Date d'un Last-Modified, ignorée si elle date d'aujourd'hui (pages générées à la volée)."""
    if not entete:
        return None
    try:
        d = parsedate_to_datetime(entete)
    except (TypeError, ValueError):
        return None
    return d.date() if (datetime.now(UTC).date() - d.date()).days >= 2 else None
