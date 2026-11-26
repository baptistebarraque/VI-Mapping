"""Référentiel V.i : complète les PAT de France PAT sans les remplacer, résout les périmètres des soutiens."""

from __future__ import annotations

from pathlib import Path

from test_base import CARRE, T0, Conn, commune, contexte, prov
from vi_mapping.db import upsert
from vi_mapping.sources.referentiel_vi import collecter

FICHIERS = {
    "pat_driaaf.csv": (
        "id,nom,porteur,france_pat_id,niveau_num,niveau,statut,axe_restauration_collective,"
        "axe_education_alimentaire,priorites,perimetre_precision,source,url\n"
        "PAT01,PAT Est,Ville,1,2,Niveau 2,Labellisé,oui,non,Restauration collective,exacte,DRIAAF,https://driaaf.fr/\n"
        "PAT02,PAT Ouest,PNR,,,Non confirmé,À vérifier,non,non,Filières,approchée,DRIAAF,https://driaaf.fr/\n"
    ),
    "pat_driaaf_communes.csv": (
        "pat_id,code_insee,commune,origine\nPAT01,93048,Montreuil,driaaf\nPAT01,94080,Vincennes,ma_cantine\n"
        "PAT02,94080,Vincennes,driaaf\nPAT02,99999,Hors périmètre,driaaf\n"
    ),
    "soutiens.csv": (
        "id,echelon,territoire,perimetre_type,perimetre,score,dispositif,source,url\n"
        "departement:93,departement,93,departement,93,2,PAT départemental,seinesaintdenis.fr,https://ssd.fr/\n"
        "interco:200054781,interco,MGP,epci,200054781,1,Plan alimentaire métropolitain,mgp,https://mgp.fr/\n"
    ),
    "laureats_aap_mgp.csv": "code_insee,commune,editions,source,url\n93048,Montreuil,2023 ; 2024-25,mgp,https://mgp.fr/\n",
    "syndicats_restauration.csv": (
        "syndicat,code_insee,commune,source,url\nSIRESCO,93048,Montreuil,mgp,https://mgp.fr/\n"
        "SIRESCO,94080,Vincennes,mgp,https://mgp.fr/\n"
    ),
}


def referentiel(dossier: Path) -> Path:
    for nom, texte in FICHIERS.items():
        (dossier / nom).write_text(texte, encoding="utf-8")
    return dossier


def test_referentiel(conn: Conn, tmp_path: Path) -> None:
    commune(conn)
    upsert(conn, "commune", [{
        "code_insee": "94080", "nom": "Vincennes", "departement": "94", "geom": CARRE, "population": 50_000,
        "superficie_km2": 2.0, "epci_siren": "200054781", **prov("ign_admin_express")}], ["code_insee"])
    upsert(conn, "dispositif", [{
        "id": "pat:1", "type": "pat", "nom": "PAT Est (France PAT)", "communes": ["93048"],
        "axe_education_alimentaire": True, "niveau_num": 2, **prov("france_pat")}], ["id"])

    compte = collecter(contexte(conn, "referentiel_vi", dossier=str(referentiel(tmp_path))))
    assert compte["pat_completes"] == 1 and compte["pat_ajoutes"] == 1 and compte["syndicats"] == 1

    d = {r["id"]: r for r in conn.execute("SELECT * FROM dispositif")}
    # PAT connu de France PAT : complété (axes DRIAAF, commune ajoutée), périmètre et source d'origine conservés
    est = d["pat:1"]
    assert (est["source"], est["communes"], est["communes_ajoutees"]) == ("france_pat", ["93048"], ["94080"])
    assert (est["axe_education_alimentaire"], est["axe_education_verifie"], est["axe_restauration_collective"]) == (
        True, False, True)
    assert "referentiel" in est["provenances"]
    # PAT absent de France PAT : ajouté, communes hors Île-de-France ignorées, confiance abaissée (« à vérifier »)
    ouest = d["referentiel:PAT02"]
    assert (ouest["communes"], float(ouest["confiance"])) == (["94080"], 0.6)
    # Soutiens : périmètres résolus par département et par Siren d'EPCI
    assert d["soutien:departement:93"]["communes"] == ["93048"]
    assert (d["soutien:interco:200054781"]["communes"], d["soutien:interco:200054781"]["score"]) == (["94080"], 1)
    assert d["aap_mgp:93048"]["editions"] == "2023 ; 2024-25"
    assert d["syndicat:SIRESCO"]["communes"] == ["93048", "94080"]
    assert all(r["geom"] is not None for r in d.values() if r["source"] == "referentiel_vi")


def test_referentiel_rejouable(conn: Conn, tmp_path: Path) -> None:
    commune(conn)
    dossier = str(referentiel(tmp_path))
    collecter(contexte(conn, "referentiel_vi", dossier=dossier))
    avant = conn.execute("SELECT count(*) AS n FROM dispositif").fetchone()
    collecter(contexte(conn, "referentiel_vi", T0.replace(day=2), dossier=dossier))
    assert conn.execute("SELECT count(*) AS n FROM dispositif").fetchone() == avant
