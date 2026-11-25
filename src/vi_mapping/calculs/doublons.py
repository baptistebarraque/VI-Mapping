"""Repère les fiches qui décrivent le même lieu dans plusieurs sources (colonne `doublon_de`).

Aucune fiche n'est supprimée : chacune garde sa provenance. La carte n'affiche que la fiche principale,
les jauges utilisent l'information de toutes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from itertools import combinations
from math import hypot
from typing import Any

from ..outils.noms import distinctifs_accueil, mots, similarite
from ..outils.texte import normaliser
from ..sources.base import Compteurs, Contexte

# Fiche principale : la source la plus précise sur le lieu
PRIORITE = {
    "accueil_periscolaire": ["sites_mairies", "osm", "sirene", "recherche_entreprises"],
    "relais_local": ["osm", "sirene", "rna"],
    "asso_parents": ["rna", "fcpe_departements"],
}


class Groupes:
    """Union-find : regroupe des identifiants reliés deux à deux."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def racine(self, x: str) -> str:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def unir(self, a: str, b: str) -> None:
        ra, rb = self.racine(a), self.racine(b)
        if ra != rb:
            self._parent[max(ra, rb)] = min(ra, rb)

    def listes(self) -> list[list[str]]:
        groupes: dict[str, list[str]] = defaultdict(list)
        for x in self._parent:
            groupes[self.racine(x)].append(x)
        return [sorted(g) for g in groupes.values() if len(g) > 1]


def rattacher(ctx: Contexte) -> Compteurs:
    return {
        "doublons_accueils": _traiter(ctx, "accueil_periscolaire", paires_accueils(ctx), _richesse_accueil),
        "doublons_relais": _traiter(ctx, "relais_local", paires_relais(ctx), _richesse_relais),
        "doublons_assos": _traiter(ctx, "asso_parents", paires_assos(ctx), _richesse_asso),
    }


def _traiter(
    ctx: Contexte, table: str, paires: Iterable[tuple[str, str]], richesse: Callable[[dict[str, Any]], Any]
) -> int:
    groupes = Groupes()
    for a, b in paires:
        groupes.unir(a, b)
    ctx.conn.execute(f"UPDATE {table} SET doublon_de = NULL WHERE doublon_de IS NOT NULL")
    n = 0
    for membres in groupes.listes():
        fiches = ctx.conn.execute(f"SELECT * FROM {table} WHERE id = ANY(%s)", (membres,)).fetchall()
        ordre = PRIORITE[table]
        fiches.sort(key=lambda f: (ordre.index(f["source"]), [-x for x in richesse(f)], f["id"]))
        principale = fiches[0]["id"]
        ctx.conn.execute(
            f"UPDATE {table} SET doublon_de = %s WHERE id = ANY(%s)", (principale, [f["id"] for f in fiches[1:]])
        )
        n += len(fiches) - 1
    return n


def _richesse_accueil(f: dict[str, Any]) -> list[float]:
    return [sum(f[c] is not None for c in ("accueil_soir", "accueil_mercredi", "horaires", "gestionnaire_siren",
                                           "exploitant", "adresse"))]


def _richesse_relais(f: dict[str, Any]) -> list[float]:
    return [sum(f[c] is not None for c in ("site_web", "adresse"))]


def _richesse_asso(f: dict[str, Any]) -> list[float]:
    # Une association recréée remplace l'ancienne, souvent restée « active » au répertoire.
    return [f["date_creation"].toordinal() if f["date_creation"] else 0, sum(
        f[c] is not None for c in ("site_web", "siren", "federation", "geom"))]


def paires_accueils(ctx: Contexte) -> Iterable[tuple[str, str]]:
    for r in ctx.conn.execute(
        """SELECT a.id AS ia, b.id AS ib, a.nom AS na, b.nom AS nb, a.source <> b.source AS autre_source,
                  ST_Distance(a.geom_l93, b.geom_l93) AS d, coalesce(c.nom, '') AS commune
           FROM accueil_periscolaire a
           JOIN accueil_periscolaire b ON a.id < b.id AND ST_DWithin(a.geom_l93, b.geom_l93, 300)
           LEFT JOIN commune c ON c.code_insee = a.commune"""
    ).fetchall():
        a, b = distinctifs_accueil(r["na"], r["commune"]), distinctifs_accueil(r["nb"], r["commune"])
        s = similarite(a, b)
        niveaux = niveau_accueil(r["na"]), niveau_accueil(r["nb"])
        if None not in niveaux and niveaux[0] != niveaux[1]:
            continue  # maternel et élémentaire : deux accueils distincts
        proche = r["autre_source"] and r["d"] <= 60 and (not a or not b or s >= 0.6)
        homonyme = s >= 0.85 or (not a and not b and r["d"] <= 60 and normaliser(r["na"]) == normaliser(r["nb"]))
        if proche or homonyme:
            yield r["ia"], r["ib"]


def niveau_accueil(nom: str) -> str | None:
    n = normaliser(nom)
    maternel, elementaire = "maternel" in n, "elementaire" in n or "primaire" in n
    if maternel == elementaire:
        return None
    return "maternel" if maternel else "elementaire"


_VIDES_RELAIS = {
    "amap", "association", "epicerie", "solidaire", "sociale", "centre", "social", "socioculturel", "culturel",
    "espace", "vie", "ferme", "pedagogique", "maintien", "agriculture", "paysanne", "socio", "maison", "asso",
}


def _mots_relais(nom: str, commune: str) -> list[str]:
    n, c = normaliser(nom), normaliser(commune)
    if c:
        n = n.replace(c, " ")
    return [m for m in mots(n) if m not in _VIDES_RELAIS]


def paires_relais(ctx: Contexte) -> Iterable[tuple[str, str]]:
    for r in ctx.conn.execute(
        """SELECT a.id AS ia, b.id AS ib, a.nom AS na, b.nom AS nb, a.source <> b.source AS autre_source,
                  a.commune = b.commune AS meme_commune, ST_Distance(a.geom_l93, b.geom_l93) AS d,
                  coalesce(c.nom, '') AS commune
           FROM relais_local a
           JOIN relais_local b ON a.type = b.type AND a.id < b.id AND ST_DWithin(a.geom_l93, b.geom_l93, 2000)
           LEFT JOIN commune c ON c.code_insee = a.commune"""
    ).fetchall():
        a, b = _mots_relais(r["na"], r["commune"]), _mots_relais(r["nb"], r["commune"])
        s = similarite(a, b)
        identiques = normaliser(r["na"]) == normaliser(r["nb"])
        if (
            (r["d"] <= 150 and (s >= 0.8 or identiques))
            or (r["autre_source"] and r["d"] <= 60 and (s >= 0.5 or not a or not b))
            or (r["meme_commune"] and (s >= 0.92 or (identiques and len(a) >= 1)))
        ):
            yield r["ia"], r["ib"]


def paires_assos(ctx: Contexte) -> Iterable[tuple[str, str]]:
    """Association recréée sous le même nom, ou conseil local FCPE déjà déclaré au RNA."""
    par_nom: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    rna_fcpe: dict[str, list[tuple[str, set[str]]]] = defaultdict(list)
    conseils: list[tuple[str, str, set[str]]] = []
    noms = {r["code_insee"]: normaliser(r["nom"]) for r in ctx.conn.execute("SELECT code_insee, nom FROM commune")}
    for r in ctx.conn.execute(
        "SELECT id, nom, commune, federation, source, ST_X(geom_l93) AS x, ST_Y(geom_l93) AS y "
        "FROM asso_parents ORDER BY id"
    ):
        propres = {m for m in mots(r["nom"]) if m not in _VIDES_ASSO} - set(mots(noms.get(r["commune"], "")))
        par_nom[r["commune"], " ".join(mots(r["nom"]))].append({**r, "propres": propres})
        if r["source"] == "fcpe_departements":
            conseils.append((r["id"], r["commune"], propres))
        elif r["federation"] == "FCPE":
            rna_fcpe[r["commune"]].append((r["id"], propres))
    for fiches in par_nom.values():
        for a, b in combinations(fiches, 2):
            # Un nom sans mot propre (« Association des parents d'élèves ») ne suffit pas : il faut le même siège.
            if a["propres"] or (a["x"] and b["x"] and hypot(a["x"] - b["x"], a["y"] - b["y"]) <= 100):
                yield a["id"], b["id"]
    for id_, commune, propres in conseils:
        if not any(len(m) >= 5 for m in propres):
            continue
        for autre, propres_rna in rna_fcpe[commune]:
            if propres <= propres_rna:
                yield autre, id_


_VIDES_ASSO = {
    "fcpe", "conseil", "local", "association", "parents", "eleves", "eleve", "ecole", "ecoles", "maternelle",
    "elementaire", "primaire", "groupe", "scolaire", "federation", "conseils", "union", "coordination", "locale",
}
