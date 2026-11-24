"""Associations de parents d'élèves et relais locaux (répertoire national des associations).

Lecture partielle de l'archive nationale, en mémoire. Colonnes de gestion (adresse du dirigeant, civilité)
et complément d'adresse (« chez M. X ») jamais lues.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Any

from ..db import point, upsert
from ..outils import motifs
from ..outils.ban import Adresse, Position, geocoder
from ..outils.datagouv import derniere
from ..outils.texte import adresse_sans_personne, normaliser, propre, sans_contact, site_web, titre, type_voie
from ..outils.zip_distant import lignes_csv, ouvrir
from .base import Compteurs, Contexte, connecteur

JEU = "58e53811c751df03df38f42d"
OBJET_PARENTS = "015005"  # nomenclature du RNA : associations de parents d'élèves
FICHE = "https://www.data-asso.fr/association/{rna}"

_GERER = r"(gerer|gestion|creer|creation|ouvrir|ouverture|animer|animation|developper|mise en place|tenir|faire vivre)"
_RELAIS_OBJET = {
    "distribution_amap": re.compile(
        r"\bcharte (des|de l|d) ?amap\b|\b(creation|creer|gerer|gestion|constituer) (d une |une |de l )amap\b"
        r"|\bassociation pour le maintien (de l|d une) ?agriculture paysanne\b"
    ),
    "epicerie_solidaire": re.compile(
        rf"\b{_GERER}\b.{{0,40}}\bepiceries? (sociales?|solidaires?)|^epicerie (sociale|solidaire)"
    ),
    "ferme_pedagogique": re.compile(rf"\b{_GERER}\b.{{0,40}}\bfermes? pedagogiques?|^ferme pedagogique"),
}


def jour(texte: str) -> date | None:
    try:
        d = date.fromisoformat(texte[:10])
    except ValueError:
        return None
    return d if d.year >= 1901 else None


def voie(r: dict[str, str]) -> str:
    """Numéro et voie du siège, sans complément nominatif."""
    morceaux = [r["adrs_numvoie"], r["adrs_repetition"], type_voie(r["adrs_typevoie"]), titre(r["adrs_libvoie"])]
    texte = " ".join(m for m in (propre(m) for m in morceaux) if m and m not in ("_", "0"))
    return adresse_sans_personne(texte) or ""


def est_asso_parents(r: dict[str, str], t: str, o: str) -> float | None:
    """Confiance dans le fait qu'il s'agit d'une association de parents d'élèves, ou None."""
    code = OBJET_PARENTS in (r["objet_social1"], r["objet_social2"])
    if motifs.PARENTS.search(t):
        return 0.8
    if code:
        return 0.75 if re.search(r"\bparents?\b|\becoles?\b|\beleves?\b|\bscolaires?\b", f"{t} {o}") else None
    if motifs.federation(t, "") and re.search(r"\bparents?\b|\becoles?\b|\beleves?\b", f"{t} {o}"):
        return 0.75
    if motifs.PARENTS.search(o):
        return 0.65 if re.search(r"\bparents?\b", t) else 0.5
    return None


def relais(t: str, o: str) -> tuple[str, float] | None:
    if type_ := motifs.type_relais(t):
        return type_, 0.6
    for type_, motif in _RELAIS_OBJET.items():
        if motif.search(o):
            return type_, 0.45
    return None


@connecteur("rna", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    ressource = derniere(ctx.http, JEU, r"rna_waldec_\d{8}\.zip")
    communes = {r["code_insee"]: r["nom"] for r in ctx.conn.execute("SELECT code_insee, nom FROM commune")}
    retenues: list[tuple[dict[str, str], float | None, tuple[str, float] | None]] = []
    with ouvrir(ctx.http, ressource.url) as archive:
        for dep in ctx.idf.departements:
            membre = next(n for n in archive.namelist() if n.endswith(f"_dpt_{dep}.csv"))
            for r in lignes_csv(archive, membre):
                if r["position"] != "A":
                    continue
                t, o = normaliser(r["titre"]), normaliser(r["objet"])
                parents, lieu = est_asso_parents(r, t, o), None
                if parents is None:
                    lieu = relais(t, o)
                if parents is not None or lieu is not None:
                    retenues.append((r, parents, lieu))

    # Une adresse postale sans rue exploitable est géocodée à la commune et marquée comme telle.
    adresses: dict[str, Adresse] = {}
    for r, *_ in retenues:
        rue = voie(r)
        adresses[r["id"]] = Adresse(rue or r["adrs_libcommune"], r["adrs_codepostal"], "")
    positions = geocoder(ctx.conn, ctx.http, adresses.values())

    assos: list[dict[str, Any]] = []
    lieux: list[dict[str, Any]] = []
    compte: Counter[str] = Counter()
    for r, parents, lieu in retenues:
        pos = positions.get(adresses[r["id"]])
        commune = commune_de(r, pos, communes)
        if commune is None:
            compte["hors_idf_ou_inconnue"] += 1
            continue
        precise = pos is not None and pos.type in ("housenumber", "street", "locality") and pos.score >= 0.5
        geom = point(pos.lon, pos.lat) if pos and precise else None
        rue = voie(r)
        siege = propre(f"{rue}, {r['adrs_codepostal']} {titre(r['adrs_libcommune'])}".strip(" ,"))
        nom = titre(sans_contact(r["titre"])) or f"Association {r['id']}"
        prov = ctx.provenance(FICHE.format(rna=r["id"]), confiance=parents or (lieu[1] if lieu else None))
        if parents is not None:
            t, o = normaliser(r["titre"]), normaliser(r["objet"])
            objet = sans_contact(r["objet"])
            assos.append({
                "id": f"rna:{r['id']}",
                "rna": r["id"],
                "siren": r["siret"][:9] if re.fullmatch(r"\d{14}", r["siret"]) else None,
                "nom": nom,
                "objet": objet[:1200] if objet else None,
                "siege": siege,
                "commune": commune,
                "federation": motifs.federation(t, o),
                "niveau": motifs.niveau_scolaire(t, o),
                "date_creation": jour(r["date_creat"]),
                "site_web": site_web(r["siteweb"]),
                "geom": geom,
                **prov,
            })
        elif lieu is not None:
            if geom is None:
                compte["relais_sans_position"] += 1
                continue
            lieux.append({
                "id": f"rna:{r['id']}",
                "type": lieu[0],
                "nom": nom,
                "adresse": siege,
                "commune": commune,
                "site_web": site_web(r["siteweb"]),
                "geom": geom,
                # Siège de l'association : pas forcément le lieu d'accueil ou de distribution.
                **{**prov, "confiance": round(lieu[1] * (0.7 + 0.3 * pos.confiance if pos else 0.7), 2)},
            })
            compte[lieu[0]] += 1
    # Siren : complété par sirene_unites, à ne pas effacer.
    upsert(ctx.conn, "asso_parents", assos, ["id"], ne_pas_ecraser=["siren"])
    upsert(ctx.conn, "relais_local", lieux, ["id"])
    compte["assos_parents"] = len(assos)
    compte["assos_sans_position"] = sum(a["geom"] is None for a in assos)
    compte["assos_federees"] = sum(a["federation"] is not None for a in assos)
    compte["supprimees"] = ctx.purger("asso_parents") + ctx.purger("relais_local")
    return dict(compte)


def commune_de(r: dict[str, str], pos: Position | None, communes: dict[str, str]) -> str | None:
    """Commune du siège : code de l'adresse géocodée, sinon code déclaré, sinon arrondissement du code postal."""
    if pos and pos.code_insee in communes and pos.score >= 0.4:
        return pos.code_insee
    declare = r["adrs_codeinsee"]
    if declare in communes and declare != "75056":
        return declare
    cp = r["adrs_codepostal"]
    if re.fullmatch(r"750(0[1-9]|1\d|20)", cp):
        return f"751{cp[3:]}"
    return declare if declare in communes else None
