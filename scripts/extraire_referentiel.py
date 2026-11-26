"""Extraction ponctuelle du référentiel V.i depuis le classeur « mapping_communes_ecoles_IDF ».

Écrit les CSV de config/referentiel/, tenus ensuite à jour à la main (une source par ligne).
Ne lit ni les contacts, ni les maires, ni les étiquettes politiques du classeur.

    uv run --with openpyxl python scripts/extraire_referentiel.py chemin/vers/mapping_communes_ecoles_IDF_v2.xlsx
"""

from __future__ import annotations

import csv
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import openpyxl

SORTIE = Path(__file__).resolve().parents[1] / "config" / "referentiel"

DRIAAF = "https://driaaf.ile-de-france.agriculture.gouv.fr/les-projets-alimentaires-territoriaux-franciliens-a2903.html"
MGP = "https://www.metropolegrandparis.fr/fr/plan-alimentaire-metropolitain"

# PAT du livret DRIAAF -> identifiant France PAT (dispositif « pat:<id> »), rapprochés par nom et périmètre
FRANCE_PAT = {
    "PAT01": "1439", "PAT02": "1443", "PAT03": "1438", "PAT04": "1437", "PAT05": "1441", "PAT06": "1444",
    "PAT07": "1440", "PAT08": "1435", "PAT09": "1442", "PAT10": "1434", "PAT11": "1433", "PAT12": "54114",
    "PAT13": "375553", "PAT14": "", "PAT15": "5587",
}

# Soutiens : territoire du classeur -> (échelon, type de périmètre, périmètre, adresse de la source)
TERRITOIRES = {
    "Île-de-France": ("region", "region", "11", "https://www.iledefrance.fr/"),
    "75": ("departement", "departement", "75", "https://www.paris.fr/pages/l-alimentation-durable-a-paris-5345"),
    "93": ("departement", "departement", "93", "https://seinesaintdenis.fr/"),
    "94": ("departement", "departement", "94", "https://www.valdemarne.fr/"),
    "91": ("departement", "departement", "91", "https://www.essonne.fr/"),
    "92": ("departement", "departement", "92", "https://www.hauts-de-seine.fr/"),
    "77": ("departement", "departement", "77", "https://www.seine-et-marne.fr/"),
    "78": ("departement", "departement", "78", "https://www.yvelines.fr/"),
    "95": ("departement", "departement", "95", "https://www.valdoise.fr/"),
    "Métropole du Grand Paris": ("interco", "epci", "200054781", MGP),
    "CA Grand Paris Sud Seine-Essonne-Sénart": ("interco", "epci", "200059228", "https://www.grandparissud.fr/"),
    "Grand Paris Sud Est Avenir": ("interco", "ept", "200058006", "https://sudestavenir.fr/"),
}


def lignes(feuille: Any, entete: int) -> Iterable[dict[str, Any]]:
    """Lignes d'une feuille en dictionnaires, à partir de la ligne d'en-tête (numérotée depuis 1)."""
    rangs = feuille.iter_rows(min_row=entete, values_only=True)
    noms = [str(c).strip() if c is not None else "" for c in next(rangs)]
    for r in rangs:
        if any(v not in (None, "") for v in r):
            yield {n: v for n, v in zip(noms, r, strict=False) if n}


def oui_non(v: Any) -> str:
    texte = str(v or "").strip().lower()
    return "oui" if texte == "oui" else "non" if texte == "non" else ""


def niveau(texte: str) -> str:
    m = re.search(r"niveau\s*([12])", texte, re.I)
    return m.group(1) if m else ""


def ecrire(nom: str, colonnes: list[str], donnees: Iterable[dict[str, Any]]) -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(SORTIE / nom, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, colonnes, lineterminator="\n")
        w.writeheader()
        for d in donnees:
            w.writerow({c: d.get(c, "") for c in colonnes})
            n += 1
    return n


def main(chemin: str) -> None:
    classeur = openpyxl.load_workbook(chemin, read_only=True, data_only=True)

    # ------------------------------------------------------------- PAT du livret DRIAAF
    pats = list(lignes(classeur["PAT"], 2))
    par_nom = {p["PAT"]: p["ID"] for p in pats}
    print("pat_driaaf.csv", ecrire("pat_driaaf.csv", [
        "id", "nom", "porteur", "france_pat_id", "niveau_num", "niveau", "statut", "axe_restauration_collective",
        "axe_education_alimentaire", "priorites", "perimetre_precision", "source", "url"], (
        {"id": p["ID"], "nom": p["PAT"], "porteur": p["Porteur"], "france_pat_id": FRANCE_PAT[p["ID"]],
         "niveau_num": niveau(p["Niveau de labellisation"] or ""), "niveau": p["Niveau de labellisation"],
         "statut": p["Statut"], "axe_restauration_collective": oui_non(p["Axe restauration collective"]),
         "axe_education_alimentaire": oui_non(p["Axe éducation alimentaire"]), "priorites": p["Axes et priorités"],
         "perimetre_precision": p["Précision du périmètre"], "source": p["Sources"], "url": DRIAAF}
        for p in pats)))

    # ------------------------------------------------------------- communes : périmètre DRIAAF, lauréats, syndicats
    communes = list(lignes(classeur["Communes"], 2))
    perimetres, laureats, syndicats = [], [], []
    for c in communes:
        code = str(c["Code INSEE"])
        ajoutes = {x.strip() for x in str(c.get("PAT ajouté d'après ma cantine") or "").split(";") if x.strip()}
        for nom in (x.strip() for x in str(c.get("PAT : noms") or "").split(";")):
            if nom in par_nom:
                perimetres.append({"pat_id": par_nom[nom], "code_insee": code, "commune": c["Commune"],
                                   "origine": "ma_cantine" if nom in ajoutes else "driaaf"})
        if editions := c.get("Lauréat AAP MGP restauration bio et locale"):
            laureats.append({"code_insee": code, "commune": c["Commune"], "editions": str(editions),
                             "source": "metropolegrandparis.fr (dépliant 2025)", "url": MGP})
        if syndicat := c.get("Syndicat de restauration (cité MGP)"):
            syndicats.append({"syndicat": syndicat, "code_insee": code, "commune": c["Commune"],
                              "source": "metropolegrandparis.fr (liste partielle)", "url": MGP})
    print("pat_driaaf_communes.csv", ecrire(
        "pat_driaaf_communes.csv", ["pat_id", "code_insee", "commune", "origine"], perimetres))
    print("laureats_aap_mgp.csv", ecrire(
        "laureats_aap_mgp.csv", ["code_insee", "commune", "editions", "source", "url"], laureats))
    print("syndicats_restauration.csv", ecrire(
        "syndicats_restauration.csv", ["syndicat", "code_insee", "commune", "source", "url"], syndicats))

    # ------------------------------------------------------------- soutiens : région, départements, intercos
    soutiens = []
    for s in lignes(classeur["Soutiens territoriaux"], 2):
        territoire = str(s["Territoire"])
        if territoire not in TERRITOIRES:
            continue  # communes lauréates et syndicats : fichiers dédiés ci-dessus
        echelon, type_, perimetre, url = TERRITOIRES[territoire]
        score = s["Score retenu"] if isinstance(s["Score retenu"], int) else ""
        # Ligne de la région : pas de score, le texte est décalé d'une colonne dans le classeur.
        dispositif, source = (s["Politique / dispositif"], s["Source"]) if score != "" else (
            s["Score retenu"], s["Politique / dispositif"])
        soutiens.append({"id": f"{echelon}:{perimetre}", "echelon": echelon, "territoire": territoire,
                         "perimetre_type": type_, "perimetre": perimetre, "score": score,
                         "dispositif": dispositif, "source": source, "url": url})
    print("soutiens.csv", ecrire("soutiens.csv", [
        "id", "echelon", "territoire", "perimetre_type", "perimetre", "score", "dispositif", "source", "url",
    ], soutiens))


if __name__ == "__main__":
    main(sys.argv[1])
