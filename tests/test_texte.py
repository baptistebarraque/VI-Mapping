"""Normalisation, adresses et retrait des données personnelles."""

from __future__ import annotations

import pytest

from vi_mapping.outils import texte as t


@pytest.mark.parametrize(("brut", "attendu"), [
    ("  École  Élémentaire d'Application ", "ecole elementaire d application"),
    ("Sacré-Cœur", "sacre coeur"),
    ("Association de parents d\x92élèves", "association de parents d eleves"),
    (None, ""),
])
def test_normaliser(brut: str | None, attendu: str) -> None:
    assert t.normaliser(brut) == attendu


@pytest.mark.parametrize("contact", [
    "prenom.nom@exemple.fr", "contact [at] exemple.fr", "contact(at)exemple.fr", "01 23 45 67 89", "0123456789",
    "+33 1 23 45 67 89", "0033123456789", "01.23.45.67.89", "+33 (0)1 23 45 67 89",
])
def test_sans_contact(contact: str) -> None:
    assert t.contient_contact(f"Accueil {contact} le soir")
    nettoye = t.sans_contact(f"Accueil {contact} le soir")
    assert nettoye == "Accueil le soir"
    assert not t.contient_contact(nettoye)


@pytest.mark.parametrize("numero", ["Siret 12345678900012", "Siren 012345678", "75001 Paris", "W751234567"])
def test_un_identifiant_n_est_pas_un_telephone(numero: str) -> None:
    assert not t.contient_contact(numero)


@pytest.mark.parametrize(("brut", "attendu"), [
    ("chez Mme Dupont, 3 rue des Lilas", "3 rue des Lilas"),
    ("c/o M. Martin, 12 avenue Foch", "12 avenue Foch"),
    ("3 rue des Lilas, Monsieur Durand", "3 rue des Lilas"),
    ("Mairie, 1 place de l'Église", "Mairie, 1 place de l'Église"),
    ("chez Mme Dupont", None),
])
def test_adresse_sans_personne(brut: str, attendu: str | None) -> None:
    assert t.adresse_sans_personne(brut) == attendu


@pytest.mark.parametrize(("brut", "attendu"), [
    ("ECOLE D'APPLICATION", "Ecole d'Application"),
    ("SAINT-GERMAIN-EN-LAYE", "Saint-Germain-en-Laye"),
    ("CENTRE SOCIAL/MAISON DE QUARTIER", "Centre Social/Maison de Quartier"),
    ("Déjà en casse mixte", "Déjà en casse mixte"),
    ("", None),
])
def test_titre(brut: str, attendu: str | None) -> None:
    assert t.titre(brut) == attendu


@pytest.mark.parametrize(("type_", "libelle", "attendu"), [
    ("RUE", "DE LA SABLIERE", "rue de la Sabliere"),
    ("AV", "DU GENERAL LECLERC", "avenue du General Leclerc"),
    ("CHE", "L'ORME", "chemin l'Orme"),
    (None, "LE BOURG", "Le Bourg"),
    ("RUE", None, "rue"),
])
def test_nom_voie(type_: str | None, libelle: str | None, attendu: str) -> None:
    assert t.nom_voie(type_, libelle) == attendu


@pytest.mark.parametrize(("brut", "attendu"), [
    ("www.Exemple.fr/Page", "https://www.exemple.fr/Page"),
    ("http://exemple.fr", "http://exemple.fr"),
    ("contact@exemple.fr", None),
    ("pas de site", None),
    ("https://www.facebook.com/asso", None),
    ("javascript://exemple.fr", None),
    ("https://localhost/admin", None),
    (None, None),
])
def test_site_web(brut: str | None, attendu: str | None) -> None:
    assert t.site_web(brut) == attendu
