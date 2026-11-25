"""Reconnaissance des noms : écoles, adresses, accueils, relais, fédérations."""

from __future__ import annotations

import pytest

from vi_mapping.outils import motifs, noms
from vi_mapping.outils.texte import normaliser


@pytest.mark.parametrize(("nom", "attendu"), [
    ("Ecole maternelle Paul Bert", "Paul Bert"),
    ("Ecole élémentaire publique Jules Ferry", "Jules Ferry"),
    ("Ecole primaire", ""),
])
def test_nom_propre(nom: str, attendu: str) -> None:
    assert motifs.nom_propre(nom) == attendu


@pytest.mark.parametrize(("a", "b", "meme"), [
    ("7 B Av. du Gal de Gaulle 94220 Charenton", "7 avenue du Général de Gaulle", True),
    ("12 rue des Lilas", "12, rue des Lilas 93100 Montreuil", True),
    ("12 rue des Lilas", "14 rue des Lilas", False),
    ("rue des Lilas", "rue des Lilas", False),  # sans numéro, on ne sait pas
])
def test_meme_adresse(a: str, b: str, meme: bool) -> None:
    assert noms.meme_adresse(noms.cle_adresse(a), noms.cle_adresse(b)) is meme


@pytest.mark.parametrize(("texte", "voie", "attendu"), [
    ("Parents d'élèves des écoles du 3 et 3 bis rue d'Alésia", "rue alesia", {3}),
    ("École du 15 et 17 rue de Monceau", "rue monceau", {15, 17}),
    ("École du 15 rue de Monceau", "rue alesia", set()),
    ("Groupe scolaire 12 bd Davout", "boulevard davout", {12}),
    ("École de la rue d'Alésia, 2024", "rue alesia", set()),
])
def test_numeros_cites(texte: str, voie: str, attendu: set[int]) -> None:
    assert noms.numeros_cites(noms.developper(texte), voie) == attendu


def test_similarite() -> None:
    assert noms.similarite(["paul", "bert"], ["paul", "bert"]) == 1
    assert noms.similarite(["cottereau"], ["baudoin", "cottereau"]) >= 0.85
    assert noms.similarite(["paul", "bert"], ["jules", "ferry"]) < 0.6
    assert noms.similarite([], ["ferry"]) == 0


@pytest.mark.parametrize(("nom", "attendu"), [
    ("Centre de loisirs Jean Jaurès", True),
    ("Accueil périscolaire du soir", True),
    ("ALSH Les Petits Loups", True),
    ("Base de loisirs de Cergy", False),
    ("Centre équestre et de loisirs", False),
    ("Crèche Les Lutins", False),
    ("Centre de loisirs des seniors", False),
])
def test_est_accueil(nom: str, attendu: bool) -> None:
    assert motifs.est_accueil(normaliser(nom)) is attendu


def test_soir_et_mercredi_jamais_faux() -> None:
    """L'absence d'un mot dans un nom n'est pas une absence d'accueil."""
    assert motifs.accueil_soir(normaliser("Accueil périscolaire")) is True
    assert motifs.accueil_soir(normaliser("Centre de loisirs")) is None
    assert motifs.accueil_mercredi(normaliser("Centre de loisirs du mercredi")) is True
    assert motifs.accueil_mercredi(normaliser("Centre de loisirs")) is None


@pytest.mark.parametrize(("nom", "attendu"), [
    ("AMAP des Lilas", "distribution_amap"),
    ("Réseau des AMAP d'Île-de-France", None),
    ("Épicerie sociale et solidaire", "epicerie_solidaire"),
    ("Ferme pédagogique du Piqueur", "ferme_pedagogique"),
    ("Centre socioculturel des Amandiers", "centre_social"),
    ("Centre communal d'action sociale", None),
    ("Boulangerie", None),
])
def test_type_relais(nom: str, attendu: str | None) -> None:
    assert motifs.type_relais(normaliser(nom)) == attendu


@pytest.mark.parametrize(("nom", "attendu"), [
    ("Maison de quartier du Parc", True),
    ("Espace de vie sociale", True),
    ("CCAS", False),
    ("Foyer des anciens", False),
    ("Formation socioculturelle", False),
])
def test_centre_social_osm(nom: str, attendu: bool) -> None:
    assert motifs.centre_social_osm(normaliser(nom)) is attendu


@pytest.mark.parametrize(("titre", "objet", "attendu"), [
    ("FCPE Jules Ferry", "", "FCPE"),
    ("PEEP des écoles", "", "PEEP"),
    ("APEL Sainte-Marie", "", "APEL"),
    ("Association autonome de parents d'élèves", "indépendante de la FCPE", None),
    ("Parents d'élèves du Centre", "", None),
])
def test_federation(titre: str, objet: str, attendu: str | None) -> None:
    assert motifs.federation(normaliser(titre), normaliser(objet)) == attendu


@pytest.mark.parametrize(("titre", "objet", "attendu"), [
    ("Parents d'élèves de l'école Jules Ferry", "", "premier_degre"),
    ("Parents d'élèves du collège Pasteur", "", "second_degre"),
    ("Parents d'élèves", "élèves des écoles maternelles", "premier_degre"),
    ("Parents d'élèves", "représenter les familles", "indetermine"),
])
def test_niveau_scolaire(titre: str, objet: str, attendu: str) -> None:
    assert motifs.niveau_scolaire(normaliser(titre), normaliser(objet)) == attendu
