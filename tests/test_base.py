"""Base : migrations, écriture idempotente, garde-fous de purge, contrôles, rapport de couverture, calculs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from vi_mapping import verifications
from vi_mapping.calculs.doublons import Groupes
from vi_mapping.calculs.jauges import calculer as calculer_jauges
from vi_mapping.calculs.rattachements import rattacher
from vi_mapping.config import config_idf, config_sources
from vi_mapping.couverture import mesurer, rendu
from vi_mapping.couverture.champs import TABLES
from vi_mapping.db import ChuteAnormale, enrichir, migrer, point, purger_absents, upsert
from vi_mapping.sauvegarde import TABLES as TABLES_SAUVEES
from vi_mapping.scrapers.campagne import plafond
from vi_mapping.sources.base import Contexte, sources_dues

Conn = psycopg.Connection[dict[str, Any]]
T0 = datetime(2026, 1, 1, tzinfo=UTC)
CARRE = "SRID=4326;MULTIPOLYGON(((2.40 48.85,2.50 48.85,2.50 48.90,2.40 48.90,2.40 48.85)))"


def prov(source: str, quand: datetime = T0, **reste: Any) -> dict[str, Any]:
    return {"source": source, "url": "https://exemple.fr/", "methode": config_sources()[source].methode,
            "collecte_le": quand, "confiance": 0.9, **reste}


def commune(conn: Conn) -> None:
    upsert(conn, "commune", [{
        "code_insee": "93048", "nom": "Montreuil", "departement": "93", "geom": CARRE, "population": 100_000,
        "superficie_km2": 9.0, **prov("ign_admin_express")}], ["code_insee"])


def ecole(uai: str = "0930001A", **champs: Any) -> dict[str, Any]:
    return {"uai": uai, "nom": "Ecole élémentaire Paul Langevin", "commune": "93048", "departement": "93",
            "type": "elementaire", "secteur": "public", "adresse": "12 rue des Lilas", "nb_eleves": 200,
            "geom": point(2.44, 48.86), **prov("annuaire_education"), **champs}


def asso(id_: str = "rna:W1", **champs: Any) -> dict[str, Any]:
    return {"id": id_, "nom": "Parents d'élèves de l'école Paul Langevin de Montreuil", "objet": "Parents d'élèves",
            "commune": "93048", "niveau": "premier_degre", "federation": "FCPE", "siege": "14 rue des Lilas",
            "geom": point(2.4401, 48.86), **prov("rna"), **champs}


def contexte(conn: Conn, code: str, quand: datetime = T0, **options: Any) -> Contexte:
    return Contexte(code, conn, None, config_idf(), config_sources()[code], quand, options=options)  # type: ignore[arg-type]


def compter(conn: Conn, table: str) -> int:
    r = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()  # type: ignore[arg-type]
    assert r is not None
    return int(r["n"])


# ------------------------------------------------------------------ écriture
def test_migrations_rejouables(conn: Conn) -> None:
    assert migrer(conn) == []


def test_upsert_idempotent(conn: Conn) -> None:
    commune(conn)
    for nom in ("Ecole A", "Ecole B"):
        upsert(conn, "ecole", [ecole(nom=nom)], ["uai"])
    assert compter(conn, "ecole") == 1
    assert conn.execute("SELECT nom FROM ecole").fetchone() == {"nom": "Ecole B"}


@pytest.mark.parametrize("colonne", ["source", "url", "methode", "collecte_le", "confiance"])
def test_provenance_obligatoire(conn: Conn, colonne: str) -> None:
    commune(conn)
    with pytest.raises(psycopg.errors.NotNullViolation):
        upsert(conn, "ecole", [ecole(**{colonne: None})], ["uai"])


@pytest.mark.parametrize("confiance", [-0.1, 1.1])
def test_confiance_entre_0_et_1(conn: Conn, confiance: float) -> None:
    commune(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        upsert(conn, "ecole", [ecole(confiance=confiance)], ["uai"])


def test_purge_des_lignes_disparues(conn: Conn) -> None:
    commune(conn)
    upsert(conn, "ecole", [ecole(f"09300{i:02d}A") for i in range(30)], ["uai"])
    apres = T0 + timedelta(days=1)
    upsert(conn, "ecole", [ecole(f"09300{i:02d}A", collecte_le=apres) for i in range(25)], ["uai"])
    assert purger_absents(conn, "ecole", "annuaire_education", apres) == 5
    assert compter(conn, "ecole") == 25


def test_purge_refusee_si_la_source_s_effondre(conn: Conn) -> None:
    commune(conn)
    upsert(conn, "ecole", [ecole(f"09300{i:02d}A") for i in range(30)], ["uai"])
    with pytest.raises(ChuteAnormale):
        purger_absents(conn, "ecole", "annuaire_education", T0 + timedelta(days=1))
    assert compter(conn, "ecole") == 30


def test_enrichir_retire_les_valeurs_perimees(conn: Conn) -> None:
    commune(conn)
    upsert(conn, "ecole", [ecole("0930001A"), ecole("0930002B")], ["uai"])
    p = {"source": "ips_ecoles"}
    enrichir(conn, "ecole", [{"uai": u, "ips": 100, "provenance": p} for u in ("0930001A", "0930002B")], "uai", "ips")
    enrichir(conn, "ecole", [{"uai": "0930001A", "ips": 105, "provenance": p}], "uai", "ips")
    lues = {r["uai"]: (r["ips"], "ips" in r["provenances"]) for r in conn.execute("SELECT * FROM ecole")}
    assert lues == {"0930001A": (105, True), "0930002B": (None, False)}


# ------------------------------------------------------------------ calculs
def test_rattachements_et_jauges_idempotents(conn: Conn) -> None:
    commune(conn)
    upsert(conn, "ecole", [ecole(), ecole("0930002B", nom="Ecole Jules Ferry", geom=point(2.48, 48.89),
                                         adresse="1 rue Haute")], ["uai"])
    upsert(conn, "asso_parents", [asso()], ["id"])
    upsert(conn, "accueil_periscolaire", [{
        "id": "osm:1", "nom": "Centre de loisirs Paul Langevin", "adresse": "12 rue des Lilas", "commune": "93048",
        "geom": point(2.4402, 48.8601), **prov("osm")}], ["id"])
    etats = []
    for jour in range(2):
        quand = T0 + timedelta(days=jour)
        rattacher(contexte(conn, "rattachements", quand))
        calculer_jauges(contexte(conn, "jauges", quand))
        etats.append([
            conn.execute("SELECT accueil_id, ecole_uai, motif, distance_m FROM accueil_ecole ORDER BY 1, 2").fetchall(),
            conn.execute("SELECT asso_id, ecole_uai, confiance FROM asso_ecole ORDER BY 1, 2").fetchall(),
            conn.execute("SELECT ecole_uai, periscolaire, parents, producteurs, score FROM jauge_ecole ORDER BY 1")
            .fetchall(),
        ])
    assert etats[0] == etats[1]
    accueils, assos, jauges = etats[0]
    assert [(a["ecole_uai"], a["motif"]) for a in accueils] == [("0930001A", "adresse")]
    assert [a["ecole_uai"] for a in assos] == ["0930001A"]
    # Aucune proximité calculée : jauge Producteurs inconnue, pas 0.
    assert all(j["producteurs"] is None for j in jauges)
    assert jauges[1]["parents"] is None and jauges[1]["periscolaire"] is None


def test_groupes_de_doublons() -> None:
    g = Groupes()
    for a, b in (("a", "b"), ("c", "d"), ("b", "c"), ("x", "y")):
        g.unir(a, b)
    assert sorted(g.listes()) == [["a", "b", "c", "d"], ["x", "y"]]


# ------------------------------------------------------------------ contrôles et rapport
def constats(conn: Conn) -> dict[str, verifications.Constat]:
    return {c.nom: c for c in verifications.verifier(conn)}


def test_controles_d_une_base_saine(conn: Conn) -> None:
    commune(conn)
    upsert(conn, "ecole", [ecole()], ["uai"])
    calculer_jauges(contexte(conn, "jauges"))
    assert [c.nom for c in constats(conn).values() if not c.conforme and c.gravite == "erreur"] == []


@pytest.mark.parametrize(("champ", "valeur", "nom"), [
    ("objet", "Écrire à prenom.nom@exemple.fr", "E-mails dans la base"),
    ("objet", "Appeler le 01 23 45 67 89", "Numéros de téléphone dans la base"),
    ("objet", "Appeler le +33 1 23 45 67 89", "Numéros de téléphone dans la base"),
    ("siege", "chez Mme X, 3 rue des Lilas", "Adresses qui nomment une personne"),
    ("geom", point(6.6, 43.2), "Positions hors Île-de-France"),
])
def test_controles_reperent_les_fautes(conn: Conn, champ: str, valeur: str, nom: str) -> None:
    commune(conn)
    upsert(conn, "asso_parents", [asso(**{champ: valeur})], ["id"])
    c = constats(conn)[nom]
    assert c.nombre == 1 and c.gravite == "erreur"
    assert valeur not in " ".join(c.exemples)  # jamais le contenu


def test_un_siret_n_est_pas_un_telephone(conn: Conn) -> None:
    commune(conn)
    upsert(conn, "asso_parents", [asso(objet="Siret 01234567800012, agrément 0123456789012")], ["id"])
    assert constats(conn)["Numéros de téléphone dans la base"].conforme


def test_couverture(conn: Conn) -> None:
    commune(conn)
    upsert(conn, "ecole", [ecole(ips=110), ecole("0930002B", type="maternelle", ips=None),
                           ecole("0930003C", ips=None)], ["uai"])
    r = mesurer(conn)
    m = next(m for m in r.mesures if m.table.nom == "ecole")
    taux = {c.code: m.taux(c, "93") for c in m.table.champs}
    assert m.total == {"IdF": 3, "93": 3}
    assert taux["ips"] == 0.5  # la maternelle n'est pas concernée
    assert taux["nb_eleves"] == 1 and taux["nb_classes"] == 0
    assert m.taux(m.table.champs[0], "75") is None
    assert rendu.markdown(r).count("\n## ") >= len(TABLES)
    assert len(rendu.csv_long(r).splitlines()) == 1 + 9 * sum(len(t.champs) for t in TABLES)
    assert len(rendu.pour_carte(r)["tables"]) == len(TABLES)


def test_dispositif_sur_deux_departements_compte_une_fois_en_region(conn: Conn) -> None:
    commune(conn)
    upsert(conn, "commune", [{
        "code_insee": "94080", "nom": "Vincennes", "departement": "94", "geom": CARRE, "population": 1,
        "superficie_km2": 1.0, **prov("ign_admin_express")}], ["code_insee"])
    upsert(conn, "dispositif", [{
        "id": "pat:1", "type": "pat", "nom": "PAT", "communes": ["93048", "94080"], "annee": 2024,
        "axe_education_alimentaire": True, **prov("france_pat")}], ["id"])
    m = next(m for m in mesurer(conn).mesures if m.table.nom == "dispositif")
    assert m.total == {"IdF": 1, "93": 1, "94": 1}


@pytest.mark.parametrize(("taux", "attendu"), [
    (None, "–"), (0, "0 %"), (0.001, "< 1 %"), (0.126, "13 %"), (0.9996, "> 99 %"), (1, "100 %"),
])
def test_pourcent(taux: float | None, attendu: str) -> None:
    assert rendu.pourcent(taux) == attendu


# ------------------------------------------------------------------ planification
def test_sources_dues(conn: Conn) -> None:
    from vi_mapping.sources import charger

    charger()
    toutes = sources_dues(conn)
    assert "rna" in toutes and "sites_mairies" in toutes and "monenfant" not in toutes
    conn.execute("""INSERT INTO collecte_run (source, debut, fin, statut)
                    SELECT code, now() - interval '29 days', now() - interval '28 days', 'succes'
                    FROM source_donnees""")
    dues = sources_dues(conn)
    assert "sites_mairies" in dues and "rna" not in dues


def test_echantillon_sans_contact(conn: Conn, monkeypatch: pytest.MonkeyPatch) -> None:
    """L'échantillon vaut pour le mois entier : relancer la collecte ne l'agrandit pas."""
    maximum = config_idf().scraping.echantillon_sans_contact
    monkeypatch.delenv("VI_CONTACT", raising=False)
    ctx = contexte(conn, "sites_mairies")
    assert plafond(ctx, "commune", 1000) == maximum
    conn.execute("""INSERT INTO crawl_site (hote, objet_type, objet_id, url_depart, statut, visite_le)
                    SELECT 'h' || i, 'commune', i::text, 'https://h' || i || '.fr/', 'ok', %s
                    FROM generate_series(1, 100) i""", (T0 - timedelta(days=3),))
    assert plafond(ctx, "commune", 1000) == maximum - 100
    assert plafond(ctx, "asso_parents", 1000) == maximum
    monkeypatch.setenv("VI_CONTACT", "https://exemple.fr/robot")
    assert plafond(ctx, "commune", 1000) == 1000


def test_sauvegarde_couvre_toutes_les_tables_metier(conn: Conn) -> None:
    tables = {r["tablename"] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
    assert tables - set(TABLES_SAUVEES) == {
        "spatial_ref_sys", "schema_migration", "source_donnees", "modele_provenance", "geocodage_cache"}
