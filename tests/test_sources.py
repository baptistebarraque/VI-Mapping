"""Connecteurs : anonymisation des producteurs, registre, configuration."""

from __future__ import annotations

from typing import Any

import pytest

from vi_mapping.config import config_idf, config_jauges, config_sources
from vi_mapping.sources import agence_bio, charger
from vi_mapping.sources.base import CALCULS, REGISTRE, a_collecter, ordre

charger()


@pytest.mark.parametrize(("operateur", "attendu"), [
    ({"raisonSociale": "EARL FERME DES LILAS", "gerant": "Camille DUBOIS"}, "Earl Ferme des Lilas"),
    ({"denominationcourante": "Les Jardins de Cocagne", "gerant": "Alex PETIT"}, "Les Jardins de Cocagne"),
    ({"raisonSociale": "DUBOIS Camille", "gerant": "Camille DUBOIS"}, None),
    ({"raisonSociale": "Mme DUBOIS Camille", "gerant": ""}, None),
    ({"denominationcourante": "Camille Dubois", "gerant": "Camille DUBOIS"}, None),
    ({"raisonSociale": "", "gerant": "Camille DUBOIS"}, None),
])
def test_nom_de_producteur_sans_personne(operateur: dict[str, Any], attendu: str | None) -> None:
    assert agence_bio.nom_public(operateur) == attendu


def test_adresse_la_plus_proche_du_lieu_de_production() -> None:
    def adresse(type_: str, commune: str = "77001") -> dict[str, Any]:
        return {"typeAdresseOperateurs": [type_], "codeCommune": commune}

    siege, vente, lieu = adresse("Siège social"), adresse("Lieux de vente"), adresse("Lieux d'activité")
    assert agence_bio.meilleure_adresse({"adressesOperateurs": [siege, vente, lieu]}, {"77001"}) == \
        ("lieu_activite", lieu)
    assert agence_bio.meilleure_adresse({"adressesOperateurs": [siege]}, {"77001"}) == ("siege", siege)
    assert agence_bio.meilleure_adresse({"adressesOperateurs": [adresse("Siège social", "45001")]}, {"77001"}) is None


def test_chaque_source_ouverte_a_un_connecteur() -> None:
    internes = {"ban"}  # géocodage, appelé par les autres
    for code, s in config_sources().items():
        if s.verrouillee:
            assert code not in REGISTRE, f"{code} est verrouillée : aucun connecteur ne doit la collecter"
        elif code not in internes:
            assert code in REGISTRE, code


def test_ordre_respecte_les_dependances() -> None:
    codes = ordre(a_collecter())
    for c in codes:
        for d in REGISTRE[c].depend_de:
            if d in codes:
                assert codes.index(d) < codes.index(c), f"{d} avant {c}"
    assert not set(codes) & set(CALCULS)


def test_frequences() -> None:
    """Mensuelle pour le scraping, annuelle pour l'open data."""
    for code, s in config_sources().items():
        if not s.verrouillee and s.methode != "calcul":
            assert s.frequence == ("mensuelle" if s.methode == "scraping" else "annuelle"), code


def test_perimetre() -> None:
    assert set(config_idf().departements) == {"75", "77", "78", "91", "92", "93", "94", "95"}


def test_reglages_par_defaut_des_jauges() -> None:
    c = config_jauges()
    assert dict(c.poids) == {"engagement": 25, "periscolaire": 25, "parents": 15, "producteurs": 20, "familles": 15}
    assert (c.rayon.km, c.rayon.minutes) == (30, 45)
    assert sorted(c.producteurs.sous_poids.values()) == [40, 60]
    assert (c.producteurs.minutes_plein, c.producteurs.nombre_plein) == (15, 5)
    assert c.engagement.web.fenetre_mois == 24 and c.parents.fenetre_activite_mois == 12
    assert c.periscolaire.distance_max_m == 300
