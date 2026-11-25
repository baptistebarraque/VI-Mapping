"""Politique du robot : robots.txt, réserve TDM, anti-robot, hôtes verrouillés, cadence. Serveur local, sans réseau."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from vi_mapping.config import config_idf, config_sources, hotes_verrouilles
from vi_mapping.outils.http import Cadence, user_agent
from vi_mapping.scrapers.robot import Refus, SiteWeb, hote_public

HTML = {"Content-Type": "text/html; charset=utf-8"}
Reponse = tuple[int, dict[str, str], str]


class Serveur:
    """Réponses par chemin ; garde les requêtes reçues."""

    def __init__(self) -> None:
        self.reponses: dict[str, Reponse] = {"/robots.txt": (404, HTML, "")}
        self.recues: list[tuple[str, str]] = []
        serveur = self

        class Gestionnaire(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                serveur.recues.append((self.path, self.headers.get("User-Agent", "")))
                code, entetes, corps = serveur.reponses.get(self.path, (404, HTML, "absent"))
                self.send_response(code)
                for k, v in entetes.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(corps.encode())

            def log_message(self, *_: Any) -> None:
                pass

        self._http = ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        self.url = f"http://127.0.0.1:{self._http.server_address[1]}"
        threading.Thread(target=self._http.serve_forever, args=(0.01,), daemon=True).start()

    def page(self, chemin: str, corps: str = "<html><p>Bonjour</p></html>", code: int = 200, **entetes: str) -> None:
        self.reponses[chemin] = (code, HTML | {k.replace("_", "-"): v for k, v in entetes.items()}, corps)

    def robots(self, texte: str) -> None:
        self.reponses["/robots.txt"] = (200, {"Content-Type": "text/plain"}, texte)

    def chemins(self) -> list[str]:
        return [c for c, _ in self.recues]

    def fermer(self) -> None:
        self._http.shutdown()
        self._http.server_close()


@pytest.fixture
def serveur() -> Iterator[Serveur]:
    s = Serveur()
    s.page("/")
    yield s
    s.fermer()


@pytest.fixture
def site(serveur: Serveur) -> Iterator[SiteWeb]:
    scraping = config_idf().scraping.model_copy(update={"delai_s": 0.0, "timeout_s": 5})
    with SiteWeb(serveur.url, cadence=Cadence(0), scraping=scraping, verifier_hote=False) as s:
        yield s


def refus(site: SiteWeb, url: str) -> str:
    with pytest.raises(Refus) as e:
        site.lire(url, premiere=True)
    return e.value.statut


def test_lit_robots_avant_la_page_avec_un_user_agent_identifie(serveur: Serveur, site: SiteWeb) -> None:
    assert site.lire(f"{serveur.url}/", premiere=True) is not None
    assert serveur.chemins()[0] == "/robots.txt"
    nom = config_idf().http.nom_robot
    assert all(ua.startswith(f"{nom}/") for _, ua in serveur.recues)
    assert "Mozilla" not in user_agent()


def test_page_interdite_jamais_demandee(serveur: Serveur, site: SiteWeb) -> None:
    serveur.robots("User-agent: *\nDisallow: /prive/\n")
    serveur.page("/prive/page")
    assert site.lire(f"{serveur.url}/prive/page") is None
    assert "/prive/page" not in serveur.chemins()
    assert site.pages_interdites == 1


def test_accueil_interdit(serveur: Serveur, site: SiteWeb) -> None:
    serveur.robots("User-agent: *\nDisallow: /\n")
    assert refus(site, f"{serveur.url}/") == "robots_interdit"


def test_regle_propre_au_robot(serveur: Serveur, site: SiteWeb) -> None:
    serveur.robots(f"User-agent: {config_idf().http.nom_robot}\nDisallow: /\n\nUser-agent: *\nAllow: /\n")
    assert refus(site, f"{serveur.url}/") == "robots_interdit"


@pytest.mark.parametrize("code", [401, 403, 429, 500, 503])
def test_robots_illisible_vaut_refus(serveur: Serveur, site: SiteWeb, code: int) -> None:
    serveur.reponses["/robots.txt"] = (code, HTML, "")
    assert refus(site, f"{serveur.url}/") == "robots_interdit"
    assert "/" not in serveur.chemins()


@pytest.mark.parametrize(("page", "statut"), [
    ({"corps": "<title>Just a moment...</title>"}, "anti_robot"),
    ({"corps": "<p>Are you a robot?</p>"}, "anti_robot"),
    ({"code": 403, "corps": "interdit"}, "anti_robot"),
    ({"code": 429, "corps": ""}, "anti_robot"),
    ({"code": 500, "corps": ""}, "erreur_http"),
    ({"tdm_reservation": "1"}, "tdm_reserve"),
    ({"corps": '<meta name="tdm-reservation" content="1">'}, "tdm_reserve"),
])
def test_refus_du_site(serveur: Serveur, site: SiteWeb, page: dict[str, Any], statut: str) -> None:
    serveur.page("/", **page)
    assert refus(site, f"{serveur.url}/") == statut
    assert serveur.chemins().count("/") == 1  # ni reprise ni contournement


def test_tdmrep_reserve_un_chemin(serveur: Serveur, site: SiteWeb) -> None:
    serveur.reponses["/.well-known/tdmrep.json"] = (
        200, {"Content-Type": "application/json"}, '[{"location": "/actu*", "tdm-reservation": 1}]')
    assert site.lire(f"{serveur.url}/", premiere=True) is not None
    with pytest.raises(Refus) as e:
        site.lire(f"{serveur.url}/actu/1")
    assert e.value.statut == "tdm_reserve"


def test_ne_sort_pas_du_site(serveur: Serveur, site: SiteWeb) -> None:
    serveur.page("/ailleurs", code=302, Location="https://exemple.org/")
    assert site.lire(f"{serveur.url}/ailleurs") is None
    assert not site.meme_site("https://exemple.org/")


def test_crawl_delay_respecte(serveur: Serveur, site: SiteWeb) -> None:
    serveur.robots("User-agent: *\nCrawl-delay: 7\n")
    assert site.autorise(f"{serveur.url}/")
    assert site._delai_s == 7


def test_page_tronquee(serveur: Serveur, site: SiteWeb) -> None:
    serveur.page("/", "<html>" + "x" * (site.c.octets_max + 50_000))
    page = site.lire(f"{serveur.url}/", premiere=True)
    assert page is not None and len(page.html) <= site.c.octets_max


def test_hote_local_refuse() -> None:
    assert not hote_public("127.0.0.1") and not hote_public("localhost") and not hote_public("10.0.0.1")
    with SiteWeb("http://127.0.0.1/") as site, pytest.raises(Refus):
        site.lire("http://127.0.0.1/", premiere=True)


def test_hote_verrouille_jamais_contacte() -> None:
    assert {"monenfant.fr", "amap-idf.org", "fcpe75.org"} <= hotes_verrouilles()
    for hote in hotes_verrouilles():
        with SiteWeb(f"https://www.{hote}/") as site:
            assert refus(site, f"https://www.{hote}/") == "cgu_interdit"


def test_source_verrouillee_documentee() -> None:
    for code, s in config_sources().items():
        if s.verrouillee:
            assert s.verification is not None and s.verification.constat, code


def test_cadence() -> None:
    c = Cadence(0.1)
    t = time.monotonic()
    for hote in ("a", "a", "b"):
        c.attendre(hote)
    ecoule = time.monotonic() - t
    assert 0.1 <= ecoule < 0.2  # un délai entre les deux visites de « a », aucun pour « b »


def test_delai_par_defaut_mesure() -> None:
    s = config_idf().scraping
    assert s.delai_s >= 1 and s.pages_max_par_site <= 50 and s.sites_en_parallele <= 8
