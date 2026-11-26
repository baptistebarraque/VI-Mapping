"""Table des communes en colonnes, alignée sur meta.communes : score propre et critères, pour les classer dans la carte.

Le critère « producteurs » est recalculé dans la carte (moyenne des écoles, selon le rayon choisi) ; les autres
critères arrivent tout faits et la carte refait seulement la moyenne pondérée selon les poids choisis.
"""

from __future__ import annotations

from typing import Any

from ..config import CRITERES_COMMUNES
from .commun import Connexion


def communes(conn: Connexion, liste: list[dict[str, Any]]) -> dict[str, list[Any]]:
    jauges = {r["code_insee"]: r for r in conn.execute(
        "SELECT code_insee, score, confiance, details FROM jauge_commune")}
    infos = {r["code_insee"]: r for r in conn.execute(
        """SELECT c.code_insee, c.population, c.cantine_pct_bio, cc.type AS cuisine_type,
                  (SELECT count(*) FROM asso_alimentation a WHERE a.commune = c.code_insee) AS assos,
                  (SELECT sum(nb_eleves) FROM ecole e WHERE e.commune = c.code_insee) AS eleves
           FROM commune c LEFT JOIN cuisine_centrale cc ON cc.siret = c.cuisine_centrale_siret""")}
    colonnes: dict[str, list[Any]] = {
        nom: [] for nom in ("score", "confiance", *CRITERES_COMMUNES, "pat_nom", "population", "eleves", "assos")
    }
    for c in liste:
        j, i = jauges.get(c["code"]), infos[c["code"]]
        criteres = {x["code"]: x for x in j["details"]["criteres"]} if j else {}
        colonnes["score"].append(j["score"] if j else None)
        colonnes["confiance"].append(j["confiance"] if j else None)
        for nom in CRITERES_COMMUNES:
            colonnes[nom].append(criteres[nom]["valeur"] if nom in criteres else None)
        colonnes["pat_nom"].append(criteres["pat"]["detail"] if "pat" in criteres else None)
        colonnes["population"].append(i["population"])
        colonnes["eleves"].append(i["eleves"])
        colonnes["assos"].append(i["assos"])
    return colonnes
