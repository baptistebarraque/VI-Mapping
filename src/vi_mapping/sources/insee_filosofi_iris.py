"""Revenu disponible médian et taux de pauvreté par IRIS (Filosofi, dernier millésime infracommunal)."""

from __future__ import annotations

import csv
import io
import re
import zipfile

from .base import Compteurs, Contexte, connecteur

FICHIER = "https://www.insee.fr/fr/statistiques/fichier/8229323/BASE_TD_FILO_IRIS_2021_DISP_CSV.zip"


def decimal(texte: str) -> float | None:
    """« 19,0 » -> 19.0 ; « ns » (non significatif) et « nd » (non diffusé) -> None."""
    return float(texte.replace(",", ".")) if re.fullmatch(r"-?\d+(,\d+)?", texte or "") else None


@connecteur("insee_filosofi_iris", depend_de=["ign_iris"])
def collecter(ctx: Contexte) -> Compteurs:
    departements = set(ctx.idf.departements)
    chemin = ctx.http.telecharger(FICHIER, "insee_filosofi_iris_2021.zip")
    with zipfile.ZipFile(chemin) as archive:
        membre = next(n for n in archive.namelist() if n.startswith("BASE_") and n.endswith(".csv"))
        annee = 2000 + int(membre[-len("21_DISP.csv"):][:2])
        texte = archive.read(membre).decode("utf-8-sig")
    suffixe = str(annee)[2:]
    lignes = []
    for r in csv.DictReader(io.StringIO(texte), delimiter=";"):
        if r["IRIS"][:2] not in departements:
            continue
        revenu, pauvrete = decimal(r[f"DISP_MED{suffixe}"]), decimal(r[f"DISP_TP60{suffixe}"])
        if revenu is None and pauvrete is None:
            continue  # secret statistique : donnée manquante, pas zéro
        lignes.append({
            "iris": r["IRIS"],
            "revenu_median": round(revenu) if revenu is not None else None,
            "taux_pauvrete": pauvrete,
            "annee_revenus": annee,
            "provenance": ctx.provenance_json(FICHIER),
        })
    return {"millesime": annee, "iris": ctx.enrichir("territoire_social", lignes, "iris", "revenus")}
