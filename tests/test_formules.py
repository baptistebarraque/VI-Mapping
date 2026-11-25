"""Formules des jauges.

Les vecteurs de tests/vecteurs/jauges.json sont communs avec la carte (web/tests/jauges.test.ts) ; les autres
tests fixent leur propre barème pour ne pas dépendre de config/jauges.yaml.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vi_mapping.calculs import formules
from vi_mapping.calculs.formules import Accueil, AssoLiee
from vi_mapping.config import ConfigJauges, Rayon, config_jauges

VECTEURS: dict[str, Any] = json.loads((Path(__file__).parent / "vecteurs" / "jauges.json").read_text("utf-8"))


@pytest.fixture
def cfg() -> ConfigJauges:
    """Configuration figée : les tests ne dépendent pas des réglages de config/jauges.yaml."""
    c = config_jauges().model_copy(deep=True)
    v = VECTEURS["config_producteurs"]
    c.producteurs.sous_poids = v["sous_poids"]
    c.producteurs.minutes_plein, c.producteurs.km_plein = v["minutes_plein"], v["km_plein"]
    c.producteurs.nombre_plein = v["nombre_plein"]
    c.donnees_insuffisantes.part_min_connue_score = VECTEURS["part_min_score"]
    return c


@pytest.mark.parametrize("v", VECTEURS["producteurs"], ids=lambda v: v["cas"])
def test_producteurs(cfg: ConfigJauges, v: dict[str, Any]) -> None:
    prod = v["prod"]
    distances = None if prod is None else list(zip(prod[::2], prod[1::2], strict=True))
    j = formules.producteurs(cfg, distances, Rayon.model_validate(v["rayon"]))
    assert j.valeur == v["valeur"]
    if distances is not None:
        assert j.criteres[1].detail == v["nombre"]


@pytest.mark.parametrize("v", VECTEURS["score"], ids=lambda v: v["cas"])
def test_score(cfg: ConfigJauges, v: dict[str, Any]) -> None:
    assert formules.score(cfg, v["valeurs"], v["poids"]).valeur == v["score"]


def critere(jauge: formules.Jauge, code: str) -> float | None:
    return next(c.valeur for c in jauge.criteres if c.code == code)


# --------------------------------------------------------------------------- règle commune : inconnu ≠ 0
def test_inconnu_ne_compte_jamais_zero(cfg: ConfigJauges) -> None:
    j = formules.moyenne([formules.Critere("a", 80, 60), formules.Critere("b", None, 40)], 0.5)
    assert j.valeur == 80
    assert j.part_connue == 0.6


def test_part_connue_trop_faible(cfg: ConfigJauges) -> None:
    j = formules.moyenne([formules.Critere("a", 80, 40), formules.Critere("b", None, 60)], 0.5)
    assert j.valeur is None


# --------------------------------------------------------------------------- engagement
def engagement(cfg: ConfigJauges, **k: Any) -> formules.Jauge:
    base: dict[str, Any] = {"pat": "aucun", "pat_nom": None, "pct_bio": None, "annee_bio": None, "themes": None}
    return formules.engagement(cfg, **{**base, **k})


def test_engagement_pat(cfg: ConfigJauges) -> None:
    notes = [critere(engagement(cfg, pat=p), "pat") for p in ("avec_axe_education", "sans_axe_education", "aucun")]
    assert notes == [100, 50, 0]


def test_engagement_bio(cfg: ConfigJauges) -> None:
    plein = cfg.engagement.bio.pct_plein
    assert critere(engagement(cfg, pct_bio=plein / 2), "bio") == 50
    assert critere(engagement(cfg, pct_bio=plein * 2), "bio") == 100
    assert critere(engagement(cfg, pct_bio=0.0), "bio") == 0
    assert critere(engagement(cfg), "bio") is None


def test_engagement_web(cfg: ConfigJauges) -> None:
    cfg.engagement.web.themes_plein, cfg.engagement.web.poids_sans_date = 4, 0.5
    assert critere(engagement(cfg), "web") is None  # site jamais visité
    assert critere(engagement(cfg, themes=[]), "web") == 0  # visité, rien trouvé
    assert critere(engagement(cfg, themes=["bio", "potager"]), "web") == 50
    assert critere(engagement(cfg, themes=["bio"], themes_sans_date=["potager"]), "web") == 37.5
    assert critere(engagement(cfg, themes=["bio"], themes_sans_date=["bio"]), "web") == 25  # pas compté deux fois


# --------------------------------------------------------------------------- périscolaire
def test_periscolaire_sans_accueil_connu(cfg: ConfigJauges) -> None:
    assert formules.periscolaire(cfg, []).valeur is None
    cfg.periscolaire.source_exhaustive = True
    assert formules.periscolaire(cfg, []).valeur == 0


def test_periscolaire_complet(cfg: ConfigJauges) -> None:
    j = formules.periscolaire(cfg, [Accueil(True, True, True, False)])
    assert j.valeur == 100


def test_periscolaire_horaires_inconnus(cfg: ConfigJauges) -> None:
    p = cfg.periscolaire
    j = formules.periscolaire(cfg, [Accueil(None, None, False, True)])
    assert critere(j, "soir") == p.soir.accueil_sans_horaire
    assert critere(j, "mercredi") == p.mercredi.centre_de_loisirs
    assert critere(j, "gestionnaire") == p.gestionnaire.non_identifie


def test_periscolaire_non_explicite(cfg: ConfigJauges) -> None:
    j = formules.periscolaire(cfg, [Accueil(False, False, True, False)])
    assert critere(j, "soir") == 0
    assert critere(j, "mercredi") == 0


def test_periscolaire_annonce_par_la_commune(cfg: ConfigJauges) -> None:
    j = formules.periscolaire(cfg, [], soir_commune=True, mercredi_commune=True)
    assert critere(j, "soir") == cfg.periscolaire.soir.oui_commune
    assert critere(j, "gestionnaire") is None
    assert j.valeur == cfg.periscolaire.soir.oui_commune == cfg.periscolaire.mercredi.oui_commune


# --------------------------------------------------------------------------- parents
def test_parents(cfg: ConfigJauges) -> None:
    assert formules.parents(cfg, []).valeur is None
    j = formules.parents(cfg, [AssoLiee(0.8, None, None), AssoLiee(0.6, "FCPE", True)])
    assert critere(j, "rattachee") == 80
    assert critere(j, "federee") == 100
    assert critere(j, "active") == 100


def test_parents_confiance_trop_faible(cfg: ConfigJauges) -> None:
    cfg.parents.confiance_min = 0.35
    assert formules.parents(cfg, [AssoLiee(0.3, "FCPE", True)]).valeur is None


def test_parents_inactive_ou_inconnue(cfg: ConfigJauges) -> None:
    assert critere(formules.parents(cfg, [AssoLiee(0.5, None, False)]), "active") == 0
    assert critere(formules.parents(cfg, [AssoLiee(0.5, None, None)]), "active") is None


# --------------------------------------------------------------------------- familles
def test_mixite(cfg: ConfigJauges) -> None:
    m = cfg.familles.mixite
    m.ips_reference, m.ips_amplitude, m.part_ips, m.part_qpv, m.qpv_distance_max_m = 100, 40, 70, 30, 300
    assert formules.mixite(cfg, None, 0) is None
    assert formules.mixite(cfg, 100, 0) == 100
    assert formules.mixite(cfg, 100, None) == 70
    assert formules.mixite(cfg, 120, 301) == 35
    assert formules.mixite(cfg, 60, 300) == formules.mixite(cfg, 140, 300) == 30


def test_familles(cfg: ConfigJauges) -> None:
    f = cfg.familles
    f.nb_eleves_plein, f.familles_iris_plein = 300, 800
    j = formules.familles(cfg, nb_eleves=150, familles_iris=800, ips=None, qpv_distance_m=None)
    assert critere(j, "nb_eleves") == 50
    assert critere(j, "familles_iris") == 100
    assert critere(j, "mixite") is None
    assert j.valeur == 75


# ------------------------------------------------------------------ communes (étape 1)
@pytest.fixture
def cfg_communes(cfg: ConfigJauges) -> ConfigJauges:
    """Barème communal figé, indépendant de config/jauges.yaml."""
    c = cfg.model_copy(deep=True)
    v = VECTEURS["communes"]
    c.communes.sous_poids = v["sous_poids"]
    c.donnees_insuffisantes.part_min_connue_jauge = v["part_min"]
    c.communes.pat = c.communes.pat.model_validate(
        {"part_niveau": 60, "part_restauration": 20, "part_education": 20, "niveau_inconnu": 1})
    c.communes.soutiens = c.communes.soutiens.model_validate(
        {"part_departement": 50, "part_interco": 25, "part_aap_mgp": 25})
    c.communes.associations = c.communes.associations.model_validate({"nombre_plein": 5, "densite_plein_10k": 3})
    c.engagement.bio.pct_plein = 40
    return c


@pytest.mark.parametrize("v", VECTEURS["communes"]["score"], ids=lambda v: v["cas"])
def test_score_commune(cfg_communes: ConfigJauges, v: dict[str, Any]) -> None:
    assert formules.commune(cfg_communes, v["valeurs"]).valeur == v["valeur"]


@pytest.mark.parametrize("v", VECTEURS["communes"]["producteurs"], ids=lambda v: v["cas"])
def test_producteurs_commune(v: dict[str, Any]) -> None:
    assert formules.commune_producteurs(v["ecoles"]) == v["valeur"]


def test_pat_commune(cfg_communes: ConfigJauges) -> None:
    P = formules.PatCommune
    assert formules.commune_pat(cfg_communes, []) == (0.0, None)
    assert formules.commune_pat(cfg_communes, [P("A", 2, True, True)]) == (100.0, "A")
    # Meilleur des deux PAT ; niveau inconnu compté 1
    assert formules.commune_pat(cfg_communes, [P("A", 1, False, False), P("B", None, True, None)]) == (50.0, "B")


def test_soutiens_commune(cfg_communes: ConfigJauges) -> None:
    assert formules.commune_soutiens(cfg_communes, departement=2, interco=1, aap_mgp=True) == 87.5
    assert formules.commune_soutiens(cfg_communes, departement=None, interco=None, aap_mgp=False) == 0


def test_cuisine_commune(cfg_communes: ConfigJauges) -> None:
    def note(**k: Any) -> tuple[float | None, str | None]:
        base = {"type_centrale": None, "satellites": None, "sur_place": None, "part_regie": None}
        return formules.commune_cuisine(cfg_communes, **{**base, **k})

    b = cfg_communes.communes.cuisine
    assert note(type_centrale="caisse_des_ecoles", satellites=20) == (b.caisse_des_ecoles, "caisse_des_ecoles")
    assert note(type_centrale="inconnu", satellites=2, sur_place=5, part_regie=1.0) == (b.sur_place_regie,
                                                                                         "sur_place_regie")
    assert note(satellites=0, sur_place=3, part_regie=0.0) == (b.sur_place_concedee, "sur_place_concedee")
    assert note(syndicat=True) == (b.intercommunale, "syndicat")
    assert note() == (None, None)  # aucune cantine déclarée : inconnu, jamais 0


def test_associations_commune(cfg_communes: ConfigJauges) -> None:
    assert formules.commune_associations(cfg_communes, 0, 1000) == 0
    assert formules.commune_associations(cfg_communes, 5, 10_000) == 100
    assert formules.commune_associations(cfg_communes, 1, 100_000) == pytest.approx(10 + 50 / 30)
