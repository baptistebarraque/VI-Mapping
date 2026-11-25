"""Intercommunalités : nom de l'EPCI et établissement public territorial (EPT) de chaque commune."""

from __future__ import annotations

import io

import openpyxl
from psycopg.types.json import Jsonb

from .base import Compteurs, Contexte, connecteur

FISCALITE_PROPRE = {"CC", "CA", "CU", "METRO", "MET69"}


@connecteur("banatic", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    # Lecture en mémoire : le fichier contient des coordonnées de service dont on n'a pas l'usage.
    contenu = ctx.http.get(ctx.config.url).content
    feuille = openpyxl.load_workbook(io.BytesIO(contenu), read_only=True).worksheets[0]
    lignes = feuille.iter_rows(values_only=True)
    entete = [str(c).strip() for c in next(lignes)]
    i_siren, i_nom = entete.index("N° SIREN"), entete.index("Nom du groupement")
    i_nature, i_membre = entete.index("Nature juridique"), entete.index("Siren membre")

    epci: dict[str, tuple[str, str]] = {}
    ept: dict[str, tuple[str, str]] = {}
    for ligne in lignes:
        membre = str(ligne[i_membre] or "").strip()[:9]
        groupement = (str(ligne[i_siren]).strip(), str(ligne[i_nom]).strip())
        nature = str(ligne[i_nature] or "").strip()
        if nature in FISCALITE_PROPRE:
            epci[membre] = groupement
        elif nature == "EPT":
            ept[membre] = groupement
    if not epci:
        raise RuntimeError("aucun EPCI à fiscalité propre lu : format Banatic modifié ?")

    prov = Jsonb(ctx.provenance_json())
    n_epci = n_ept = 0
    for siren, (code, nom) in epci.items():
        n_epci += ctx.conn.execute(
            "UPDATE commune SET epci_siren = %s, epci_nom = %s, "
            "provenances = provenances || jsonb_build_object('intercommunalite', %s::jsonb) WHERE siren = %s",
            (code, nom, prov, siren),
        ).rowcount
    ctx.conn.execute("UPDATE commune SET ept_siren = NULL, ept_nom = NULL")
    for siren, (code, nom) in ept.items():
        n_ept += ctx.conn.execute(
            "UPDATE commune SET ept_siren = %s, ept_nom = %s WHERE siren = %s", (code, nom, siren)
        ).rowcount
    return {"communes_avec_epci": n_epci, "communes_avec_ept": n_ept}
