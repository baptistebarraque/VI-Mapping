"""Lecture des pages : dates, thèmes, délégations. Aucune donnée personnelle hors élus, aucune étiquette politique."""

from __future__ import annotations

from datetime import date

import pytest

from vi_mapping.outils.texte import contient_contact, normaliser
from vi_mapping.scrapers import themes
from vi_mapping.scrapers.page import date_dans_texte, extraire

JOUR = date(2026, 11, 25)
URL = "https://www.exemple.fr/actualites/cantine"


def test_extraire() -> None:
    c = extraire(
        """<html><head><title>Cantine bio</title><meta property="article:modified_time" content="2026-03-12T10:00:00">
        </head><body><nav>Menu bio</nav><h1>La cantine</h1><p>Repas <b>bio</b></p><a href="/suite#x">Suite</a>
        <script>var potager = 1</script></body></html>""", URL, aujourdhui=JOUR)
    assert c.titre == "Cantine bio"
    assert c.date == date(2026, 3, 12) and c.date_origine == "meta"
    assert "repas bio" in c.texte and "potager" not in c.texte
    assert ("https://www.exemple.fr/suite", "Suite") in c.liens
    assert not c.noindex


def test_noindex() -> None:
    assert extraire('<meta name="robots" content="noindex, nofollow"><p>x</p>', URL, aujourdhui=JOUR).noindex


@pytest.mark.parametrize(("texte", "attendu"), [
    ("publié le 12 mars 2026", date(2026, 3, 12)),
    ("mis à jour le mardi 1er septembre 2026", date(2026, 9, 1)),
    ("dernière modification le 3/04/2026", date(2026, 4, 3)),
    ("publié le 12 mars 2027", None),  # futur
    ("publié le 31 février 2026", None),
    ("conseil municipal du 12 mars 2026", None),  # date d'un événement, pas de la page
])
def test_date_dans_texte(texte: str, attendu: date | None) -> None:
    assert date_dans_texte(normaliser(texte), JOUR) == attendu


@pytest.mark.parametrize(("texte", "theme"), [
    ("Des repas 100 % bio à la cantine", "bio"),
    ("Lutter contre le gaspillage alimentaire", "anti_gaspi"),
    ("Un potager à l'école", "potager"),
    ("Semaine du goût dans les écoles", "education_gout"),
])
def test_themes(texte: str, theme: str) -> None:
    assert theme in themes.themes_de(normaliser(texte))


@pytest.mark.parametrize("texte", ["La biodiversité au parc", "Biographie du maire", "Vide-grenier dimanche"])
def test_sans_theme(texte: str) -> None:
    assert not themes.themes_de(normaliser(texte))


ELUS = {"1": ("camille", "dubois"), "2": ("dominique", "martin")}


def test_delegations() -> None:
    lignes = ("Camille DUBOIS", "2e adjointe au maire, déléguée aux affaires scolaires", "Dominique MARTIN",
              "Adjoint à la transition écologique")
    lues = themes.lire_delegations(lignes, ELUS)
    assert lues["1"][1] == ["scolaire"] and lues["2"][1] == ["transition_ecologique"]
    assert "dubois" not in normaliser(lues["1"][0])


def test_delegation_sans_attribution_possible() -> None:
    """Deux élus sur la même ligne : on ne sait pas à qui revient la délégation."""
    assert themes.lire_delegations(("Camille DUBOIS et Dominique MARTIN, adjoints aux écoles",), ELUS) == {}


def test_personne_inconnue_ignoree() -> None:
    assert themes.lire_delegations(("Alex PETIT", "Adjointe aux affaires scolaires"), ELUS) == {}


@pytest.mark.parametrize("texte", [
    "Camille DUBOIS 2e adjointe aux affaires scolaires camille.dubois@exemple.fr 01 23 45 67 89",
    "Camille DUBOIS Adjointe aux affaires scolaires Groupe Les Écologistes",
    "Camille DUBOIS Adjointe aux affaires scolaires – Parti socialiste",
    "Camille DUBOIS Adjointe aux affaires scolaires (DVG)",
    "Camille DUBOIS Élue de la majorité municipale, adjointe aux affaires scolaires",
])
def test_delegation_sans_contact_ni_etiquette(texte: str) -> None:
    propre = themes.delegation_propre(texte, ELUS["1"])
    assert "affaires scolaires" in propre and not contient_contact(propre)
    n = normaliser(propre)
    for interdit in ("dubois", "exemple", "ecologistes", "socialiste", "dvg", "majorite"):
        assert interdit not in n.split()
