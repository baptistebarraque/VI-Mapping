"""Étape « communes » : nature des cuisines centrales, cantines par commune, contacts, associations d'alimentation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from vi_mapping.config import config_idf, config_sources
from vi_mapping.outils.motifs import categorie_alimentation
from vi_mapping.outils.texte import normaliser, premier_email
from vi_mapping.sources.annuaire_administration import premier_telephone
from vi_mapping.sources.annuaire_education import contacts
from vi_mapping.sources.base import Contexte
from vi_mapping.sources.ma_cantine import ligne_commune
from vi_mapping.sources.sirene_unites import type_cuisine


@pytest.mark.parametrize(("categorie", "type_"), [
    ("7210", "municipale"), ("7362", "caisse_des_ecoles"), ("7354", "intercommunale"), ("7348", "intercommunale"),
    ("7220", "autre_public"), ("5710", "privee"), ("9220", "privee"), (None, "inconnu"),
])
def test_type_cuisine(categorie: str | None, type_: str) -> None:
    assert type_cuisine(categorie) == type_


def test_contacts_ecole() -> None:
    assert contacts(142601142, "ce.0752401C@ac-paris.fr") == ("01 42 60 11 42", "ce.0752401c@ac-paris.fr")
    # Adresse nominative (école privée) gardée, mobile écarté
    assert contacts(661949242, "Prenom.Nom@exemple.fr") == (None, "prenom.nom@exemple.fr")
    assert contacts("01 34 00 00 00", None) == ("01 34 00 00 00", None)
    assert contacts(None, "non communiqué") == (None, None)


def test_contacts_mairie() -> None:
    assert premier_telephone('[{"valeur": "+33 1 34 33 44 00"}]') == "01 34 33 44 00"
    assert premier_telephone('[{"valeur": "39 75"}]') == "39 75"
    assert premier_telephone('[{"valeur": "poste 12"}]') is None
    assert premier_email("contact@cergy.fr ; autre@cergy.fr") == "contact@cergy.fr"
    assert premier_email("prenom.nom@cergy.fr") == "prenom.nom@cergy.fr"
    assert premier_email("pas une adresse") is None


@pytest.mark.parametrize(("titre", "objet", "attendu"), [
    ("AMAP des Lilas", "", ("amap_circuits_courts", 0.7)),
    ("Les Jardins partagés du canal", "", ("jardins_agriculture_urbaine", 0.7)),
    ("Association Bonjour", "lutter contre le gaspillage alimentaire", ("solidarite_anti_gaspi", 0.5)),
    ("Les Petits Gourmets", "promouvoir l'éducation au goût des enfants", ("education_alimentaire", 0.5)),
    ("Jardin d'enfants Les Lutins", "", None),
    ("Club de loisirs", "ateliers de cuisine, danse et théâtre", None),
])
def test_categorie_alimentation(titre: str, objet: str, attendu: tuple[str, float] | None) -> None:
    assert categorie_alimentation(normaliser(titre), normaliser(objet)) == attendu


def cantine(**k: Any) -> dict[str, Any]:
    return {"gestion": "regie", "repas": 100.0, "repas_connus": 100.0, "bio": None, "egalim_hors_bio": None,
            "production": "site_cooked_elsewhere", "centrale": "11111111100011", "pat": [], **k}


def test_ligne_commune() -> None:
    ctx = Contexte("ma_cantine", None, None, config_idf(), config_sources()["ma_cantine"],  # type: ignore[arg-type]
                   datetime(2026, 1, 1, tzinfo=UTC))
    liste = [
        cantine(bio=0.5, pat=["pat:1"]),
        cantine(repas=300.0, repas_connus=300.0, centrale="22222222200022", gestion="concedee"),
        cantine(production="site", centrale=None, repas_connus=None, pat=["pat:1", "pat:2"]),
    ]
    c = ligne_commune(ctx, "93048", liste, 2024, "https://td.csv")
    assert (c["cantine_nb_satellites"], c["cantine_nb_sur_place"], c["cantine_repas_jour"]) == (2, 1, 400)
    assert c["cantine_part_regie"] == pytest.approx(2 / 3, abs=1e-3)
    assert c["cuisine_centrale_siret"] == "22222222200022"  # celle qui livre le plus de repas
    assert c["cantine_pat"] == ["pat:1", "pat:2"]
    assert (c["cantine_gestion"], c["cantine_pct_bio"]) == ("mixte", 50.0)
