"""Rattachements association ↔ école et accueil ↔ école."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from vi_mapping.calculs import accueils
from vi_mapping.calculs.assos import Asso, Ecole, Lien, alias_commune, confiance, departager, groupe_unique
from vi_mapping.config import config_idf
from vi_mapping.outils.noms import cle_adresse, developper, distinctifs, radical, radicaux
from vi_mapping.outils.texte import normaliser

R = config_idf().rattachements


def ecole(nom: str = "Ecole élémentaire Paul Langevin", **champs: Any) -> Ecole:
    e = Ecole("0930001A", "93048", "elementaire", False, tuple(radical(m) for m in distinctifs(nom)), 0.0, 0.0,
              cle_adresse("12 rue des Lilas"))
    return replace(e, **champs)


def asso(titre: str, objet: str = "", **champs: Any) -> Asso:
    a = Asso("rna:W1", "93048", normaliser(titre), normaliser(objet), radicaux(titre), radicaux(objet),
             "premier_degre", 0.9, None, 50.0, 0.0, False, developper(f"{titre} {objet}"))
    return replace(a, **champs)


def score(a: Asso, e: Ecole, *, unique: bool = False, communale: bool = False) -> Lien:
    return confiance(a, e, commune=alias_commune("93048", "Montreuil"), unique=unique, communale=communale,
                     r=R.asso_ecole)


def test_nom_de_l_ecole_et_commune() -> None:
    fort = score(asso("Parents d'élèves de l'école Paul Langevin de Montreuil"), ecole())
    assert fort.confiance >= 0.9
    assert fort.indices["nom_ecole"] == 1 and fort.indices["commune"]


def test_sans_nom_ni_commune_ni_proximite() -> None:
    loin = asso("Parents d'élèves de l'école Jules Ferry", x=50_000.0)
    assert score(loin, ecole()).confiance < R.asso_ecole.confiance_min


def test_le_nom_dans_l_objet_compte_un_peu_moins_que_dans_le_titre() -> None:
    titre = score(asso("Parents de l'école Paul Langevin"), ecole()).confiance
    objet = score(asso("Les parents", "école Paul Langevin"), ecole()).confiance
    assert 0 < objet < titre


def test_secteur_ou_niveau_different_divise_la_confiance() -> None:
    a = asso("Parents de l'école Paul Langevin de Montreuil")
    assert score(replace(a, federation="APEL"), ecole()).confiance < score(a, ecole()).confiance
    maternelle = asso("Parents de la maternelle Paul Langevin de Montreuil")
    assert score(maternelle, ecole()).confiance < score(maternelle, ecole(type="maternelle")).confiance


def test_adresse_citee() -> None:
    meme = score(asso("Parents de l'école du 12 rue des Lilas"), ecole())
    autre = score(asso("Parents de l'école du 40 rue des Lilas"), ecole())
    assert meme.indices["adresse"] == "meme" and autre.indices["adresse"] == "autre_numero"
    assert meme.confiance > 2 * autre.confiance


def test_numero_voisin_ne_dit_rien() -> None:
    """« Groupe scolaire du 10 » : l'école du 12 en fait souvent partie."""
    assert "adresse" not in score(asso("Parents de l'école du 10 rue des Lilas"), ecole()).indices


def test_objet_vague_exige_le_nom() -> None:
    vague = asso("Amis de Montreuil", confiance=0.5)
    assert score(vague, ecole(), unique=True).confiance == 0


def test_departager_garde_les_ecoles_nommees() -> None:
    nommee = (Lien(0.9, {"nom_ecole": 1.0}), ecole())
    voisine = (Lien(0.5, {"siege_m": 80}), ecole("Ecole Jules Ferry"))
    assert departager([nommee, voisine]) == [nommee]
    assert departager([voisine]) == [voisine]


def test_groupe_unique() -> None:
    assert groupe_unique([ecole()])
    assert not groupe_unique([ecole(), ecole(prive=True)])
    assert not groupe_unique([ecole(), ecole(), ecole()])


@pytest.mark.parametrize(("texte", "reconnu"), [
    ("parents du 12e arrondissement", True), ("ecole paris 12", True), ("75012", True), ("paris 2e", False),
])
def test_alias_arrondissement(texte: str, reconnu: bool) -> None:
    assert bool(alias_commune("75112", "Paris 12e Arrondissement").search(texte)) is reconnu


@pytest.mark.parametrize(("distance", "adresse", "nom", "attendu"), [
    (0, "12 rue des Lilas", [], "adresse"),
    (250, "3 rue du Parc", [], "distance"),
    (900, None, ["paul", "langevin"], "nom"),
    (900, None, ["jules", "ferry"], None),
    (5000, None, ["paul", "langevin"], None),
])
def test_motif_accueil(distance: float, adresse: str | None, nom: list[str], attendu: str | None) -> None:
    assert accueils.motif(distance, adresse, "12 rue des Lilas 93100 Montreuil", nom, ["paul", "langevin"], True,
                          R.accueil_ecole) == attendu


def test_accueil_d_une_autre_commune_seulement_par_distance() -> None:
    args = ("12 rue des Lilas", "12 rue des Lilas", ["paul", "langevin"], ["paul", "langevin"], False, R.accueil_ecole)
    assert accueils.motif(200, *args) == "distance"
    assert accueils.motif(900, *args) is None
