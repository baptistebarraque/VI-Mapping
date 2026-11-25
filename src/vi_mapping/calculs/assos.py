"""Rattachement association de parents ↔ école, avec un score de confiance de 0 à 1.

Indices : nom propre ou adresse de l'école dans le nom ou l'objet de l'association, nom de la commune, proximité du
siège, école unique dans la commune. Les poids sont dans config/idf.yaml.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from math import hypot
from typing import Any

from ..config import RattachementAsso
from ..db import upsert
from ..outils import motifs
from ..outils.noms import cle_adresse, developper, distinctifs, fort, numeros_cites, radical, radicaux
from ..outils.texte import normaliser
from ..sources.base import Compteurs, Contexte

# « parents d'élèves » d'un établissement qui n'est pas une école du premier degré
_HORS_ECOLE = re.compile(
    r"\bconservatoires?\b|\becoles? (de |d )?(musique|danse|theatre|cirque|infirmier|ingenieur|commerce|superieure)"
    r"|\bcreche\b|\bcollege\b|\blycee\b|\buniversite\b|\bime\b|\binstitut medico\b")


_LES_ECOLES = re.compile(r"\becoles\b|\bgroupes scolaires\b|\betablissements scolaires\b|\brpi\b")
ECOLES_PETITE_COMMUNE = 4


@dataclass(frozen=True)
class Ecole:
    uai: str
    commune: str
    type: str
    prive: bool
    mots: tuple[str, ...]
    x: float | None
    y: float | None
    adresse: tuple[str, str] | None = None  # (numéro, voie)


@dataclass(frozen=True)
class Asso:
    id: str
    commune: str
    titre: str       # normalisé
    objet: str       # normalisé
    titre_r: str     # radicaux
    objet_r: str     # radicaux
    niveau: str
    confiance: float
    federation: str | None
    x: float | None
    y: float | None
    listee_par_commune: bool = False
    adresses: str = ""  # titre et objet, voies développées ; vide si aucun numéro


@dataclass
class Lien:
    confiance: float
    indices: dict[str, Any] = field(default_factory=dict)


def alias_commune(code: str, nom: str) -> re.Pattern[str]:
    """Motif qui reconnaît la commune dans un texte normalisé (arrondissements parisiens compris)."""
    if code.startswith("751"):
        n = int(code[3:])
        return re.compile(rf"\bparis 0?{n}(e|eme|er)?\b|\b0?{n}(e|eme|er) arrondissement\b|\b750{n:02d}\b"
                          rf"|\bparis {n}(e|eme|er)? arrondissement\b")
    formes = {normaliser(nom)}
    formes |= {re.sub(r"\bsaint\b", "st", f) for f in formes} | {re.sub(r"\bsainte\b", "ste", f) for f in formes}
    return re.compile("|".join(rf"\b{re.escape(f)}\b" for f in sorted(formes) if f))


def nom_present(mots_ecole: tuple[str, ...], texte: str) -> float:
    """Part de confiance (0 à 1) que le nom propre de l'école figure dans le texte (radicaux des deux côtés)."""
    if not mots_ecole or not texte:
        return 0.0
    phrase = r"\W+(?:(?:de|du|des|d|la|le|les|l|et) )*".join(re.escape(m) for m in mots_ecole)
    if fort(list(mots_ecole)):
        if re.search(rf"\b{phrase}\b", texte):
            return 1.0
        # nom de famille seul : « FCPE Cottereau » pour l'école Baudoin Cottereau
        nom = mots_ecole[-1]
        if len(mots_ecole) >= 2 and len(nom) >= 5 and fort([nom]) and re.search(rf"\b{re.escape(nom)}\b", texte):
            return 0.75
        # nom écrit d'un seul tenant : « julesferry »
        compact = "".join(mots_ecole)
        return 0.75 if len(compact) >= 9 and compact in texte else 0.0
    # nom passe-partout (« Centre », « Parc ») : il doit suivre le mot « école »
    ecole = r"\b(ecole|maternelle|elementaire|primaire|groupe scolaire)( (de|du|des|d|la|le|les|l))*"
    return 0.9 if re.search(rf"{ecole} {phrase}\b", texte) else 0.0


def confiance(
    asso: Asso, ecole: Ecole, *, commune: re.Pattern[str], unique: bool, communale: bool, r: RattachementAsso,
) -> Lien:
    """Score d'un couple association-école ; 0 si rien ne les relie.

    `unique` : seule école possible dans la commune. `communale` : l'association dit représenter « les écoles »
    d'une petite commune.
    """
    texte = f"{asso.titre} {asso.objet}"
    indices: dict[str, Any] = {}
    score = 0.0
    nom = max(nom_present(ecole.mots, asso.titre_r), 0.9 * nom_present(ecole.mots, asso.objet_r))
    adresse = adresse_citee(asso, ecole)
    if adresse:
        nom = 1.0  # « l'école du 15 rue de Monceau » désigne l'école aussi sûrement que son nom
    if nom:
        indices["nom_ecole"] = round(nom, 2)
        score += r.poids.nom_ecole * nom
    # Les listes départementales FCPE rangent chaque conseil local sous sa commune.
    citee = bool(commune.search(texte)) or (asso.listee_par_commune and asso.commune == ecole.commune)
    if citee:
        indices["commune"] = True
        score += r.poids.commune
    distance = None
    if asso.x is not None and ecole.x is not None and asso.y is not None and ecole.y is not None:
        distance = hypot(asso.x - ecole.x, asso.y - ecole.y)
        etendue = r.distance_nulle_m - r.distance_pleine_m
        part = min(1.0, max(0.0, 1 - (distance - r.distance_pleine_m) / etendue))
        if part > 0:
            indices["siege_m"] = round(distance)
            score += r.poids.proximite * part
    if unique:
        indices["ecole_unique"] = True
        score += r.poids.ecole_unique
    elif communale and citee and not nom:
        indices["toutes_les_ecoles"] = True
        score += r.poids.ecole_unique
    # L'association nomme un niveau que l'école n'a pas, ou l'inverse du secteur (APEL : écoles privées)
    if incompatible(asso, ecole):
        indices["niveau_ou_secteur"] = "different"
        score *= 0.5
    if adresse is not None:
        indices["adresse"] = "meme" if adresse else "autre_numero"
        score *= 1 if adresse else 0.5
    if asso.confiance < 0.6 and not nom:
        return Lien(0.0, indices)  # objet vague : le nom de l'école est indispensable
    return Lien(round(min(score, 1.0), 2), indices)


def adresse_citee(asso: Asso, ecole: Ecole) -> bool | None:
    """L'association cite-t-elle l'adresse de l'école ? False : même rue, autre numéro ; None : on ne peut rien dire."""
    if not asso.adresses or ecole.adresse is None:
        return None
    numeros = numeros_cites(asso.adresses, ecole.adresse[1])
    if not numeros:
        return None
    numero = int(ecole.adresse[0])
    if numero in numeros:
        return True
    # « groupe scolaire du 67 » : l'école du 65 en fait souvent partie
    return None if any(abs(numero - n) <= 2 for n in numeros) else False


def incompatible(asso: Asso, ecole: Ecole) -> bool:
    maternelle = bool(re.search(r"\bmaternelles?\b", asso.titre))
    elementaire = bool(re.search(r"\belementaires?\b|\bprimaires?\b|\bgroupes? scolaires?\b", asso.titre))
    if maternelle and not elementaire and ecole.type == "elementaire":
        return True
    if elementaire and not maternelle and ecole.type == "maternelle" and "groupe" not in asso.titre:
        return True
    if asso.federation == "APEL" and not ecole.prive:
        return True
    return asso.federation in ("FCPE", "PEEP") and ecole.prive


def rattacher(ctx: Contexte) -> Compteurs:
    r = ctx.idf.rattachements.asso_ecole
    ecoles = lire_ecoles(ctx)
    par_commune: dict[str, list[Ecole]] = defaultdict(list)
    for e in ecoles.values():
        par_commune[e.commune].append(e)
    noms = {
        c["code_insee"]: c["nom"]
        for c in ctx.conn.execute("SELECT code_insee, nom FROM commune WHERE code_insee <> '75056'")
    }
    alias = {code: alias_commune(code, nom) for code, nom in noms.items()}
    uniques = {c for c, liste in par_commune.items() if groupe_unique(liste)}
    voisines = defaultdict(list)
    for p in ctx.conn.execute(
        "SELECT a.id, e.uai FROM asso_parents a JOIN ecole e ON ST_DWithin(a.geom_l93, e.geom_l93, %s)",
        (r.distance_max_m,),
    ):
        voisines[p["id"]].append(p["uai"])

    lignes: list[dict[str, Any]] = []
    compte: Counter[str] = Counter()
    for a in ctx.conn.execute(
        """SELECT id, commune, nom, objet, niveau, confiance, federation, url, source,
                  ST_X(geom_l93) AS x, ST_Y(geom_l93) AS y
           FROM asso_parents WHERE niveau <> 'second_degre' AND commune IS NOT NULL"""
    ).fetchall():
        titre, objet = normaliser(a["nom"]), normaliser(a["objet"])
        if motifs.DEPARTEMENTALE.search(titre) or (_HORS_ECOLE.search(titre) and not re.search(r"\becoles?\b", titre)):
            compte["assos_hors_perimetre"] += 1
            continue
        if re.search(r"\bconservatoires?\b|\becoles? (de |d )?(musique|danse)", titre):
            compte["assos_hors_perimetre"] += 1
            continue
        texte = f"{a['nom']} {a['objet'] or ''}"
        asso = Asso(a["id"], a["commune"], titre, objet, radicaux(a["nom"]), radicaux(a["objet"] or ""),
                    a["niveau"], float(a["confiance"]), a["federation"], a["x"], a["y"],
                    a["source"] == "fcpe_departements",
                    developper(texte) if re.search(r"\d", texte) else "")
        communale = bool(_LES_ECOLES.search(titre)) and len(par_commune[a["commune"]]) <= ECOLES_PETITE_COMMUNE
        candidats = {e.uai: e for e in par_commune[a["commune"]]}
        candidats.update({u: ecoles[u] for u in voisines[a["id"]]})
        liens = []
        for e in candidats.values():
            lien = confiance(
                asso, e, commune=alias[e.commune], r=r,
                unique=e.commune in uniques and e.commune == asso.commune,
                communale=communale and e.commune == asso.commune,
            )
            if e.commune != asso.commune and "commune" not in lien.indices:
                # école voisine d'une autre commune : le nom seul ne suffit pas (homonymes)
                lien = Lien(round(lien.confiance * 0.6, 2), lien.indices)
            if lien.confiance >= r.confiance_min:
                liens.append((lien, e))
        liens.sort(key=lambda x: (-x[0].confiance, x[0].indices.get("siege_m", 10**6), x[1].uai))
        liens = departager(liens)[: r.ecoles_max_par_asso]
        compte["assos_rattachees"] += bool(liens)
        compte["liens"] += len(liens)
        for lien, e in liens:
            lignes.append({
                "asso_id": asso.id,
                "ecole_uai": e.uai,
                "indices": lien.indices,
                **ctx.provenance(a["url"], confiance=lien.confiance),
            })
    upsert(ctx.conn, "asso_ecole", lignes, ["asso_id", "ecole_uai"])
    ctx.conn.execute("DELETE FROM asso_ecole WHERE collecte_le < %s", (ctx.debut,))
    ctx.conn.execute("UPDATE asso_parents SET ecole_uai = NULL, confiance_rattachement = NULL")
    ctx.conn.execute(
        """UPDATE asso_parents a SET ecole_uai = m.ecole_uai, confiance_rattachement = m.confiance
           FROM (SELECT DISTINCT ON (asso_id) asso_id, ecole_uai, confiance FROM asso_ecole
                 ORDER BY asso_id, confiance DESC, (indices->>'siege_m')::int NULLS LAST, ecole_uai) m
           WHERE m.asso_id = a.id"""
    )
    return dict(compte)


def departager(liens: list[tuple[Lien, Ecole]]) -> list[tuple[Lien, Ecole]]:
    """Si l'association nomme une école, les écoles seulement voisines du siège sont écartées.

    Si elle donne l'adresse d'une école, ses homonymes de la même rue le sont aussi.
    """
    if any(x[0].indices.get("adresse") == "meme" for x in liens):
        liens = [x for x in liens if x[0].indices.get("adresse") != "autre_numero"]
    nommees = [x for x in liens if x[0].indices.get("nom_ecole", 0) >= 0.7]
    if not nommees:
        return liens
    meilleur = max(x[0].indices["nom_ecole"] for x in nommees)
    return [x for x in nommees if x[0].indices["nom_ecole"] >= meilleur - 0.15]


def groupe_unique(liste: list[Ecole]) -> bool:
    """Une seule école dans la commune, ou un seul groupe (maternelle et élémentaire voisines), même secteur."""
    if len(liste) == 1:
        return True
    if len(liste) > 2 or len({e.prive for e in liste}) > 1:
        return False
    a, b = liste
    if a.x is None or b.x is None or a.y is None or b.y is None or a.type == b.type:
        return False
    return hypot(a.x - b.x, a.y - b.y) <= 400


def lire_ecoles(ctx: Contexte) -> dict[str, Ecole]:
    return {
        e["uai"]: Ecole(e["uai"], e["commune"], e["type"], e["secteur"] != "public",
                        tuple(radical(m) for m in distinctifs(e["nom"])), e["x"], e["y"], cle_adresse(e["adresse"]))
        for e in ctx.conn.execute(
            "SELECT uai, commune, type, secteur, nom, adresse, ST_X(geom_l93) AS x, ST_Y(geom_l93) AS y "
            "FROM ecole ORDER BY uai"
        )
    }
