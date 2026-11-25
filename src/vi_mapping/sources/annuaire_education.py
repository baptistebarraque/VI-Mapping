"""Écoles du 1er degré, publiques et privées sous contrat (annuaire de l'éducation)."""

from __future__ import annotations

import re
from typing import Any

from ..db import point, upsert
from ..outils.ban import Adresse, geocoder
from ..outils.opendatasoft import exporter, url_fiche
from ..outils.texte import propre, sans_contact, titre
from .base import Compteurs, Contexte, connecteur

# Jamais demandé : fax. Téléphone et e-mail gardés seulement s'ils sont institutionnels (voir contacts()).
CHAMPS = [
    "identifiant_de_l_etablissement", "nom_etablissement", "statut_public_prive", "type_contrat_prive",
    "adresse_1", "code_postal", "code_commune", "nom_commune", "ecole_maternelle", "ecole_elementaire",
    "restauration", "appartenance_education_prioritaire", "latitude", "longitude", "precision_localisation",
    "etat", "code_nature", "telephone", "mail",
]

PRECISION = {"Numéro de rue": 1.0, "BATIMENT": 1.0, "NUMERO (ADRESSE)": 1.0, "Rue": 0.85, "Ville": 0.5}

# Abréviations de l'académie de Paris : « E.P.PU » = école primaire publique
_ABREVIATIONS = {
    "E.M.": "École maternelle", "E.E.": "École élémentaire", "E.P.": "École primaire",
}
_PREFIXE_PARIS = re.compile(r"^(E\.[MEP]\.)\s*(A\.)?\s*(PU|PR)\b\.?\s*", re.I)


def nom_lisible(nom: str) -> str:
    """Développe « E.P.PU ST MARTIN… » et met en casse de titre les noms tout en capitales."""
    nom = propre(nom) or ""
    if m := _PREFIXE_PARIS.match(nom):
        reste = nom[m.end():]
        if reste:
            debut = _ABREVIATIONS[m.group(1).upper()] + (" d'application" if m.group(2) else "")
            return f"{debut} {titre_mixte(reste)}"
    return titre(nom) or nom


def titre_mixte(texte: str) -> str:
    """Casse de titre appliquée seulement aux suites de mots en capitales (« ST MARTIN 211 rue… »)."""
    return re.sub(
        r"[A-ZÀ-Ý][A-ZÀ-Ý'’\-]+(?:\s+[A-ZÀ-Ý][A-ZÀ-Ý'’\-]*)*", lambda m: titre(m.group(0)) or m.group(0), texte
    )


def contacts(uai: str, telephone: Any, mail: Any) -> tuple[str | None, str | None]:
    """Standard de l'école (fixe) et adresse fonctionnelle ce.UAI@ac-….fr ; tout le reste est écarté."""
    chiffres = re.sub(r"\D", "", str(telephone or ""))
    if len(chiffres) == 9:
        chiffres = "0" + chiffres  # zéro initial perdu dans la source
    fixe = len(chiffres) == 10 and chiffres[:2] in ("01", "02", "03", "04", "05", "08", "09")
    tel = " ".join(chiffres[i:i + 2] for i in range(0, 10, 2)) if fixe else None
    email = str(mail or "").strip().lower()
    fonctionnel = re.fullmatch(rf"ce\.{uai.lower()}@ac-[a-z-]+\.fr", email)
    return tel, email if fonctionnel else None


def type_ecole(maternelle: Any, elementaire: Any, code_nature: int | None) -> str:
    if maternelle and elementaire:
        return "primaire"
    if maternelle or code_nature in (101, 103):
        return "maternelle"
    return "elementaire"


@connecteur("annuaire_education", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    base = ctx.config.url
    brutes = exporter(
        ctx.http, base, where=f'code_region="{ctx.idf.region.code}" and type_etablissement="Ecole"',
        select=",".join(CHAMPS),
    )
    communes = {r["code_insee"] for r in ctx.conn.execute("SELECT code_insee FROM commune")}
    contrats = set(ctx.idf.ecoles.contrats_prives)

    ecoles, hors_contrat, sans_commune = [], 0, 0
    for e in brutes:
        if e["etat"] != "OUVERT":
            continue
        public = e["statut_public_prive"] == "Public"
        if not public and e["type_contrat_prive"] not in contrats:
            hors_contrat += 1
            continue
        if e["code_commune"] not in communes:
            sans_commune += 1
            continue
        uai = e["identifiant_de_l_etablissement"]
        telephone, email = contacts(uai, e["telephone"], e["mail"])
        ecoles.append({
            "uai": uai,
            "nom": sans_contact(nom_lisible(e["nom_etablissement"])),
            "commune": e["code_commune"],
            "departement": e["code_commune"][:2],
            "type": type_ecole(e["ecole_maternelle"], e["ecole_elementaire"], e["code_nature"]),
            "secteur": "public" if public else "prive_sous_contrat",
            "adresse": sans_contact(e["adresse_1"]),
            "code_postal": e["code_postal"],
            "education_prioritaire": e["appartenance_education_prioritaire"],
            "restauration": None if e["restauration"] is None else bool(int(e["restauration"])),
            "telephone": telephone,
            "email": email,
            "geom": point(e["longitude"], e["latitude"]) if e["latitude"] is not None else None,
            "_precision": e["precision_localisation"],
            **ctx.provenance(url_fiche(base, "identifiant_de_l_etablissement", uai)),
        })

    # Positions imprécises (« Rue », « Ville » ou absentes) : la BAN donne souvent le numéro.
    floues = {
        e["uai"]: Adresse(e["adresse"], e["code_postal"] or "", e["commune"])
        for e in ecoles if PRECISION.get(e["_precision"], 0) < 1 and e["adresse"]
    }
    positions = geocoder(ctx.conn, ctx.http, floues.values())
    affinees = []
    for e in ecoles:
        precision = e.pop("_precision")
        e["confiance"] = PRECISION.get(precision, 0.5)
        pos = positions.get(floues[e["uai"]]) if e["uai"] in floues else None
        if pos and pos.type == "housenumber" and pos.score >= 0.6 and pos.code_insee == e["commune"]:
            e["geom"] = point(pos.lon, pos.lat)
            e["confiance"] = max(e["confiance"], pos.confiance)
            affinees.append({
                "uai": e["uai"],
                "provenance": {
                    "source": "ban", "url": "https://data.geopf.fr/geocodage/search", "methode": "api",
                    "collecte_le": ctx.debut.isoformat(timespec="seconds"), "confiance": pos.confiance,
                },
            })
        elif e["geom"] is None and pos:
            e["geom"], e["confiance"] = point(pos.lon, pos.lat), pos.confiance

    upsert(ctx.conn, "ecole", ecoles, ["uai"])
    _tracer_positions(ctx, affinees)
    supprimees = ctx.purger("ecole")
    return {
        "ecoles": len(ecoles), "hors_contrat_exclues": hors_contrat, "commune_inconnue": sans_commune,
        "positions_affinees": len(affinees), "sans_position": sum(e["geom"] is None for e in ecoles),
        "supprimees": supprimees,
    }


def _tracer_positions(ctx: Contexte, affinees: list[dict[str, Any]]) -> None:
    ctx.conn.execute("UPDATE ecole SET provenances = provenances - 'position' WHERE provenances ? 'position'")
    if affinees:
        ctx.enrichir("ecole", [{**a, "source": "annuaire_education"} for a in affinees], "uai", "position")
