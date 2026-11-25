"""Table `proximite` : paires école-cible à moins de 50 km à vol d'oiseau, puis distance et temps par la route.

Le trajet va de la cible (producteur, relais) vers l'école. Durées OSRM sans trafic : plutôt optimistes.
"""

from __future__ import annotations

import hashlib
from typing import Any

from psycopg.types.json import Jsonb

from ..config import dossier_donnees
from ..sources.base import Compteurs, Contexte, connecteur
from .osrm_graphe import Matrices, preparer

CIBLES = {
    # Producteurs « pris en compte » : bio ou conversion, légumes ou fruits, vente directe ou AMAP
    "producteur": "SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat, geom_l93 FROM producteur WHERE eligible",
    "relais_local": "SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat, geom_l93 FROM relais_local "
                    "WHERE doublon_de IS NULL",
}


def empreinte(ctx: Contexte, version_graphe: str) -> str:
    """Identifie les entrées du calcul : positions, réglages, graphe routier."""
    h = hashlib.sha1(version_graphe.encode())
    reglages = ctx.idf.proximite
    h.update(repr((reglages.km_vol_oiseau_max, sorted(reglages.cibles), reglages.facteur_duree)).encode())
    requetes = ["SELECT uai AS id, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM ecole WHERE geom IS NOT NULL"]
    requetes += [f"SELECT id, lon, lat FROM ({CIBLES[c]}) t" for c in sorted(ctx.idf.proximite.cibles)]
    for q in requetes:
        for r in ctx.conn.execute(f"{q} ORDER BY id"):
            h.update(f"{r['id']}|{r['lon']:.6f}|{r['lat']:.6f}\n".encode())
    return h.hexdigest()[:16]


@connecteur("osrm", calcul=True)
def calculer(ctx: Contexte) -> Compteurs:
    graphe, version = preparer(ctx.http, ctx.idf)
    cle = empreinte(ctx, version)
    temoin = ctx.conn.execute(
        "SELECT parametres->>'empreinte' AS e FROM collecte_run WHERE source = 'osrm' AND statut = 'succes' "
        "AND parametres ? 'empreinte' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    existant = ctx.conn.execute("SELECT EXISTS (SELECT 1 FROM proximite) AS oui").fetchone()
    if not ctx.options.get("forcer") and temoin and temoin["e"] == cle and existant and existant["oui"]:
        ctx.note("positions et graphe inchangés : rien à recalculer")
        ctx.conn.execute("UPDATE collecte_run SET parametres = parametres || %s WHERE source = 'osrm' "
                         "AND statut = 'en_cours'", (Jsonb({"empreinte": cle}),))
        return {"recalcul": 0}

    matrices = Matrices(graphe)
    prov = ctx.provenance()
    compte: Compteurs = {"recalcul": 1}
    ecoles = ctx.conn.execute(
        "SELECT uai, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM ecole WHERE geom IS NOT NULL "
        "ORDER BY ST_GeoHash(geom), uai"  # lots compacts : matrices plus petites
    ).fetchall()
    ctx.conn.execute("DELETE FROM proximite WHERE cible_type <> ALL(%s)", (ctx.idf.proximite.cibles,))
    metres_max = ctx.idf.proximite.km_vol_oiseau_max * 1000
    for type_ in ctx.idf.proximite.cibles:
        ctx.conn.execute("DELETE FROM proximite WHERE cible_type = %s", (type_,))
        total = sans_route = 0
        for i in range(0, len(ecoles), ctx.idf.proximite.lot_ecoles):
            lot = ecoles[i : i + ctx.idf.proximite.lot_ecoles]
            n, s = _lot(ctx, matrices, type_, lot, metres_max, prov)
            total += n
            sans_route += s
            if (i // ctx.idf.proximite.lot_ecoles) % 5 == 4:
                ctx.note(f"{type_} : {i + len(lot)}/{len(ecoles)} écoles, {total} paires")
        compte[f"paires_{type_}"] = total
        compte[f"sans_route_{type_}"] = sans_route
    ctx.conn.execute("ANALYZE proximite")
    ctx.conn.execute("UPDATE collecte_run SET parametres = parametres || %s WHERE source = 'osrm' "
                     "AND statut = 'en_cours'", (Jsonb({"empreinte": cle}),))
    return compte


def _lot(
    ctx: Contexte, matrices: Matrices, type_: str, lot: list[dict[str, Any]], metres_max: float, prov: dict[str, Any]
) -> tuple[int, int]:
    """Calcule et écrit les paires d'un lot d'écoles ; retourne (paires, paires sans itinéraire)."""
    paires = ctx.conn.execute(
        f"""SELECT e.uai, c.id, c.lon, c.lat, ST_Distance(e.geom_l93, c.geom_l93) / 1000 AS km
            FROM ecole e JOIN ({CIBLES[type_]}) c ON ST_DWithin(e.geom_l93, c.geom_l93, %s)
            WHERE e.uai = ANY(%s)""",
        (metres_max, [e["uai"] for e in lot]),
    ).fetchall()
    if not paires:
        return 0, 0
    cibles = {p["id"]: (p["lon"], p["lat"]) for p in paires}
    rang_cible = {id_: k for k, id_ in enumerate(cibles)}
    rang_ecole = {e["uai"]: k for k, e in enumerate(lot)}
    km, minutes = matrices.calculer(list(cibles.values()), [(e["lon"], e["lat"]) for e in lot])
    minutes = minutes * ctx.idf.proximite.facteur_duree
    sans = 0
    with ctx.conn.cursor() as cur, cur.copy(
        "COPY proximite (ecole_uai, cible_type, cible_id, km_vol_oiseau, km_route, minutes, "
        "source, url, methode, collecte_le, confiance) FROM STDIN"
    ) as copie:
        for p in paires:
            i, j = rang_cible[p["id"]], rang_ecole[p["uai"]]
            k, m = km[i, j], minutes[i, j]
            route = k == k and m == m  # faux si NaN
            sans += not route
            copie.write_row((
                p["uai"], type_, p["id"], round(p["km"], 2), round(float(k), 2) if route else None,
                round(float(m), 1) if route else None,
                prov["source"], prov["url"], prov["methode"], prov["collecte_le"], prov["confiance"],
            ))
    return len(paires), sans


def taille_graphe() -> int:
    """Octets occupés par le graphe routier local."""
    return sum(f.stat().st_size for f in (dossier_donnees() / "osrm").rglob("*") if f.is_file())
