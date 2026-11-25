"""Rattachement accueil périscolaire ↔ école : même adresse, ou moins de 300 m, ou nom proche."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..db import upsert
from ..outils.noms import cle_adresse, distinctifs, distinctifs_accueil, meme_adresse, similarite
from ..sources.base import Compteurs, Contexte


def motif(
    distance_m: float, adresse_accueil: str | None, adresse_ecole: str | None,
    nom_accueil: list[str], nom_ecole: list[str], meme_commune: bool, r: Any,
) -> str | None:
    """Motif de rattachement le plus fort, ou None. `r` : config rattachements.accueil_ecole."""
    if meme_commune and meme_adresse(cle_adresse(adresse_accueil), cle_adresse(adresse_ecole)):
        return "adresse"
    if distance_m <= r.distance_max_m:
        return "distance"
    if (
        meme_commune and distance_m <= r.distance_max_nom_m
        and similarite(nom_accueil, nom_ecole) >= r.similarite_nom_min
    ):
        return "nom"
    return None


def rattacher(ctx: Contexte) -> Compteurs:
    r = ctx.idf.rattachements.accueil_ecole
    paires = ctx.conn.execute(
        """SELECT a.id, a.nom AS nom_accueil, a.adresse AS adresse_accueil, a.url, a.commune AS commune_accueil,
                  e.uai, e.nom AS nom_ecole, e.adresse AS adresse_ecole, e.commune AS commune_ecole,
                  c.nom AS commune, ST_Distance(a.geom_l93, e.geom_l93) AS d
           FROM accueil_periscolaire a
           JOIN ecole e ON ST_DWithin(a.geom_l93, e.geom_l93, %s)
           JOIN commune c ON c.code_insee = e.commune""",
        (max(r.distance_max_m, r.distance_max_nom_m),),
    ).fetchall()
    lignes: list[dict[str, Any]] = []
    compte: Counter[str] = Counter()
    for p in paires:
        m = motif(
            p["d"], p["adresse_accueil"], p["adresse_ecole"],
            distinctifs_accueil(p["nom_accueil"], p["commune"]), distinctifs(p["nom_ecole"]),
            p["commune_accueil"] == p["commune_ecole"], r,
        )
        if m is None:
            continue
        compte[m] += 1
        lignes.append({
            "accueil_id": p["id"],
            "ecole_uai": p["uai"],
            "motif": m,
            "distance_m": round(p["d"]),
            **ctx.provenance(p["url"], confiance=r.confiance[m]),
        })
    upsert(ctx.conn, "accueil_ecole", lignes, ["accueil_id", "ecole_uai"])
    ctx.conn.execute("DELETE FROM accueil_ecole WHERE collecte_le < %s", (ctx.debut,))
    # La carte n'affiche que la fiche principale : elle reprend les écoles liées à ses doublons.
    compte["repris"] = ctx.conn.execute(
        """INSERT INTO accueil_ecole (accueil_id, ecole_uai, motif, distance_m, source, url, methode, collecte_le,
                                      confiance)
           SELECT DISTINCT ON (a.doublon_de, l.ecole_uai) a.doublon_de, l.ecole_uai, l.motif, l.distance_m,
                  l.source, l.url, l.methode, l.collecte_le, l.confiance
           FROM accueil_ecole l JOIN accueil_periscolaire a ON a.id = l.accueil_id
           WHERE a.doublon_de IS NOT NULL
           ORDER BY a.doublon_de, l.ecole_uai, l.confiance DESC, l.distance_m
           ON CONFLICT DO NOTHING""").rowcount
    return {f"accueil_ecole_{k}": v for k, v in compte.items()}
