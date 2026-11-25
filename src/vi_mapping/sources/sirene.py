"""Accueils de loisirs et relais locaux reconnus à leur enseigne (stock Sirene des établissements).

Le fichier national est interrogé à distance (Parquet) : seules les lignes franciliennes utiles transitent.
Les noms de personnes physiques du fichier ne sont pas lus.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import duckdb

from ..db import upsert
from ..outils import motifs
from ..outils.datagouv import derniere
from ..outils.texte import adresse_sans_personne, nom_voie, normaliser, propre, sans_contact, titre
from .base import Compteurs, Contexte, connecteur

JEU = "5b7ffc618b4c4169d30727e0"
FICHE = "https://annuaire-entreprises.data.gouv.fr/etablissement/{siret}"

# Pré-filtre large (le tri fin est fait par outils.motifs sur le nom normalisé)
PREFILTRE = (
    r"LOISIRS|\bALSH\b|\bCLSH\b|\bALAE\b|PERI ?-?SCOLAIRE|CENTRE AERE|CENTRES AERES|GARDERIE (SCOLAIRE|DU SOIR)"
    r"|CENTRES? SOCIA|CENTRES? SOCIO|ESPACE DE VIE SOCIALE|EPICERIE (SOCIALE|SOLIDAIRE)|FERME PEDAGOGIQUE|\bAMAP\b"
)
# Syndicats et comités d'entreprise, hébergement touristique, commerce : pas un accueil ouvert aux écoliers
NAF_EXCLUES = ("94.20Z", "55.", "47.", "46.", "70.", "69.", "66.", "77.", "13.", "45.", "93.11", "93.12", "93.13")


@connecteur("sirene", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    ressource = derniere(ctx.http, JEU, r"stock-stocketablissement-parquet\.parquet")
    communes = {
        r["code_insee"]: r["nom"] for r in ctx.conn.execute(
            # Adresse postale : « Paris » pour un arrondissement
            "SELECT c.code_insee, coalesce(m.nom, c.nom) AS nom FROM commune c "
            "LEFT JOIN commune m ON m.code_insee = c.commune_mere")
    }
    deps = ", ".join(f"'{d}'" for d in ctx.idf.departements)
    base = duckdb.connect()
    base.execute("INSTALL httpfs; LOAD httpfs; SET enable_progress_bar = false;")
    lignes = base.execute(
        f"""
        SELECT siret, codeCommuneEtablissement, activitePrincipaleEtablissement,
               trim(concat_ws(' ', enseigne1Etablissement, enseigne2Etablissement, enseigne3Etablissement)) AS ens,
               denominationUsuelleEtablissement, numeroVoieEtablissement, typeVoieEtablissement,
               libelleVoieEtablissement, codePostalEtablissement,
               coordonneeLambertAbscisseEtablissement, coordonneeLambertOrdonneeEtablissement
        FROM read_parquet(?)
        WHERE substr(codeCommuneEtablissement, 1, 2) IN ({deps}) AND etatAdministratifEtablissement = 'A'
          AND regexp_matches(concat_ws(' ', enseigne1Etablissement, enseigne2Etablissement,
                                       enseigne3Etablissement, denominationUsuelleEtablissement), ?)
        """,
        [ressource.url, PREFILTRE],
    ).fetchall()
    base.close()

    accueils: list[dict[str, Any]] = []
    relais: list[dict[str, Any]] = []
    compte: Counter[str] = Counter(lues=len(lignes))
    for siret, commune, naf, enseigne, denomination, num, tv, lv, cp, x, y in lignes:
        nom_brut = enseigne or denomination or ""
        nom = normaliser(nom_brut)
        if commune not in communes or (naf or "").startswith(NAF_EXCLUES):
            continue
        accueil = motifs.est_accueil(nom)
        type_ = None if accueil else motifs.type_relais(nom)
        if not accueil and type_ is None:
            continue
        if x in (None, "", "[ND]") or y in (None, "", "[ND]"):
            compte["sans_position"] += 1
            continue
        rue = " ".join(m for m in (propre(num), nom_voie(tv, lv)) if m)
        ville = " ".join(m for m in (propre(cp), communes[commune]) if m)
        commun = {
            "id": f"sirene:{siret}",
            "nom": titre(sans_contact(nom_brut)),
            "adresse": adresse_sans_personne(f"{rue}, {ville}".strip(" ,")),
            "commune": commune,
            "geom": (float(x), float(y)),
            **ctx.provenance(FICHE.format(siret=siret)),
        }
        if accueil:
            accueils.append({**commun, "accueil_soir": motifs.accueil_soir(nom),
                             "accueil_mercredi": motifs.accueil_mercredi(nom), "horaires": None})
        else:
            relais.append({**commun, "type": type_, "site_web": None})
            compte[str(type_)] += 1

    ecrire(ctx, "accueil_periscolaire", accueils)
    ecrire(ctx, "relais_local", relais)
    compte["accueils"] = len(accueils)
    compte["supprimes"] = ctx.purger("accueil_periscolaire") + ctx.purger("relais_local")
    return dict(compte)


def ecrire(ctx: Contexte, table: str, lignes: list[dict[str, Any]]) -> None:
    """Convertit les coordonnées Lambert 93 de Sirene, puis écrit."""
    for ligne in lignes:
        x, y = ligne["geom"]
        ligne["geom"] = ctx.conn.execute(
            "SELECT ST_AsEWKT(ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 2154), 4326)) AS g", (x, y)
        ).fetchone()["g"]  # type: ignore[index]
    upsert(ctx.conn, table, lignes, ["id"])
