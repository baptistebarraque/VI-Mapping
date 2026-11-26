"""Contacts : lecture des champs publiés, rattachement des collectivités, carnet exporté avec ses provenances."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from test_base import commune, constats, contexte, ecole, prov
from vi_mapping.config import config_idf, config_jauges
from vi_mapping.db import enrichir, point, upsert
from vi_mapping.export.acteurs import Acteurs, cle_nom, contact
from vi_mapping.outils.texte import email_de_contact, telephone
from vi_mapping.sources import agence_bio, banatic, osm
from vi_mapping.sources.base import communes_actuelles
from vi_mapping.sources.ma_cantine import siret_valide

Conn = psycopg.Connection[dict[str, Any]]


@pytest.mark.parametrize(("texte", "attendu"), [
    ("01.34.33.44.00", "01 34 33 44 00"), ("+33 (0)1 34 33 44 00", "01 34 33 44 00"),
    ("0033134334400", "01 34 33 44 00"), ("01 34 33 44 00 / 01 34 33 44 01", "01 34 33 44 00"),
    ("3975", "39 75"), ("inconnu", None), ("", None), (None, None),
    ("12 rue des Lilas", None),
])
def test_telephone(texte: str | None, attendu: str | None) -> None:
    assert telephone(texte) == attendu


@pytest.mark.parametrize(("texte", "attendu"), [
    ("dpo@agglo.fr; Accueil@Agglo.fr", "accueil@agglo.fr"), ("rgpd@ville.fr", None), ("a@x.fr et b@x.fr", "a@x.fr"),
    ("mail.dpo@ville.fr", None), ("www.ville.fr", None), (None, None),
])
def test_email_de_contact(texte: str | None, attendu: str | None) -> None:
    assert email_de_contact(texte) == attendu


@pytest.mark.parametrize(("nom", "attendu"), [
    ("SI pour la restauration collective", True), ("SIVU cuisine centrale", True),
    ("Syndicat de restauration des rivières", False), ("Syndicat des eaux", False),
])
def test_syndicats_de_restauration(nom: str, attendu: bool) -> None:
    assert banatic.est_restauration(nom) is attendu


def test_contact_banatic_prefere_le_siege() -> None:
    champs = {"Téléphone du siège": None, "Téléphone administrative": "0134334400",
              "Courriel du siège": "a@x.fr et b@x.fr", "Site internet du siège": "www.agglo.fr"}
    c = banatic.contact(champs)
    assert (c["telephone"], c["email"]) == ("01 34 33 44 00", "a@x.fr")
    assert "agglo.fr" in str(c["site_web"])


def test_contact_agence_bio_ligne_commerciale_et_vrai_site() -> None:
    c = agence_bio.contact({
        "telephone": "0611223344", "telephoneCommerciale": "0134334400", "email": "ferme@exemple.fr",
        "siteWebs": [{"url": "https://www.facebook.com/ferme"}, {"url": "https://ancien.fr", "active": False},
                     {"url": "https://ferme.fr"}]})
    assert c["telephone"] == "01 34 33 44 00" and c["email"] == "ferme@exemple.fr"
    assert str(c["site_web"]).startswith("https://ferme.fr")


def test_contact_osm() -> None:
    assert osm.contact({"contact:phone": "+33 1 34 33 44 00", "contact:email": "amap@exemple.fr"}) == {
        "telephone": "01 34 33 44 00", "email": "amap@exemple.fr", "site_web": None}


@pytest.mark.parametrize(("siret", "valide"), [
    ("22222222200022", True), ("00000000000000", False), ("2222222220002", False), ("", False), (None, False),
])
def test_siret_de_cuisine(siret: str | None, valide: bool) -> None:
    assert siret_valide(siret) == (siret if valide else None)


def test_commune_fusionnee() -> None:
    assert communes_actuelles(["93066", "93059", "75112"]) == ["75112", "93066"]


def test_cle_de_nom_sans_la_forme_juridique() -> None:
    assert cle_nom("CC Entre Juine et Renarde (CCEJR)") == cle_nom("Communauté de communes entre Juine et Renarde")


def test_contact_repris_d_un_doublon_avec_sa_source() -> None:
    sans = {"telephone": None, "email": None, "site_web": None, **prov("osm")}
    avec = {"telephone": None, "email": "a@x.fr", "site_web": None, **prov("agence_bio")}
    c = contact(sans, avec)
    assert c is not None and c["email"] == "a@x.fr" and c["p"]["s"] == "agence_bio"
    assert contact(sans) is None


def preparer(conn: Conn) -> None:
    commune(conn)
    enrichir(conn, "commune", [{
        "code_insee": "93048", "mairie_email": "mairie@montreuil.fr",
        "provenance": contexte(conn, "annuaire_administration").provenance_json("https://exemple.fr/mairie"),
    }], "code_insee", "contact_mairie")
    upsert(conn, "ecole", [ecole(email="ce.0930001a@ac-creteil.fr"), ecole("0930002B", email=None)], ["uai"])
    upsert(conn, "organisme", [{
        "siren": "200000000", "nom": "Agglo de test", "type": "epci", "communes": ["93048"], "email": "a@agglo.fr",
        **prov("banatic")}], ["siren"])
    upsert(conn, "dispositif", [{
        "id": "pat:1", "type": "pat", "nom": "PAT de test", "communes": ["93048"], "porteur": "CA Agglo de test",
        "telephone": "01 34 33 44 00", **prov("france_pat")}], ["id"])


def test_carnet_chaque_contact_garde_sa_provenance(conn: Conn) -> None:
    preparer(conn)
    acteurs = Acteurs(conn, config_jauges(), config_idf().region.departements)
    lignes = {(x["n"], x["id"]): x for x in acteurs.carnet(acteurs.fiches())}
    assert set(lignes) == {("commune", "93048"), ("ecole", "0930001A"), ("organisme", "200000000"), ("pat", "pat:1")}
    assert lignes["commune", "93048"]["p"]["s"] == "annuaire_administration"
    assert lignes["organisme", "200000000"]["communes"] == ["93048"]
    assert all(x["p"]["s"] and x["p"]["u"] and x["p"]["d"] for x in lignes.values())
    assert acteurs.porteurs["pat:1"] == {"organisme": "200000000"}


@pytest.mark.parametrize("champ", ["email", "telephone"])
def test_controle_des_contacts_mal_formes(conn: Conn, champ: str) -> None:
    preparer(conn)
    assert constats(conn)["Contacts mal formés"].conforme
    conn.execute(f"UPDATE organisme SET {champ} = 'voir le site'")  # type: ignore[call-overload]
    c = constats(conn)["Contacts mal formés"]
    assert c.nombre == 1 and "voir le site" not in " ".join(c.exemples)


def test_point_de_production_dans_les_fiches(conn: Conn) -> None:
    preparer(conn)
    upsert(conn, "producteur", [{
        "id": "agencebio:1", "nom": "Ferme de test", "commune": "93048", "adresse_type": "lieu_activite",
        "geom": point(2.44, 48.86), "maraichage": True, "fruits": False, "etat_bio": "bio", "eligible": True,
        "email": "ferme@exemple.fr", **prov("agence_bio")}], ["id"])
    acteurs = Acteurs(conn, config_jauges(), config_idf().region.departements)
    f = acteurs.fiches()["producteur"]["agencebio:1"]
    assert f["xy"] == [2.44, 48.86] and f["contact"]["email"] == "ferme@exemple.fr"
    assert f["contact"]["p"]["s"] == f["p"]["s"] == "agence_bio"
