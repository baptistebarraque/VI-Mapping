"""Mise en forme du rapport de couverture : Markdown, CSV, JSON pour la carte."""

from __future__ import annotations

import csv
import io
from typing import Any

from . import REGION, Rapport
from .champs import Champ

LIBELLES_STATUT = {
    "ok": "visité", "vide": "sans page exploitable", "robots_interdit": "refusé par robots.txt",
    "cgu_interdit": "refusé par ses CGU", "tdm_reserve": "fouille de données réservée",
    "anti_robot": "protégé contre les robots (abandon)", "erreur_http": "en erreur", "injoignable": "injoignable",
}
SEUIL_FAIBLE = 0.5
LIBELLES_OBJET = {
    "commune": "Sites de mairies", "asso_parents": "Sites d'associations", "federation": "Sites de fédérations",
}


def pourcent(taux: float | None) -> str:
    """Jamais arrondi à 0 ou à 100 % : « 100 % » veut dire complet, « 0 % » vide."""
    if taux is None:
        return "–"
    if 0 < taux < 0.01:
        return "< 1 %"
    if 0.99 < taux < 1:
        return "> 99 %"
    return f"{taux * 100:.0f} %"


def entier(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _libelle(c: Champ) -> str:
    return f"{c.libelle} \\*" if c.nature == "part" else c.libelle


def _minuscule(libelle: str) -> str:
    """Première lettre en minuscule, sauf sigle (« IPS », « QPV »)."""
    return libelle if libelle[1:2].isupper() else libelle[:1].lower() + libelle[1:]


def _tableau(entetes: list[str], lignes: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(entetes) + " |",
        "|---|" + "---:|" * (len(entetes) - 1),
        *("| " + " | ".join(ligne) + " |" for ligne in lignes),
    ]


def markdown(r: Rapport) -> str:
    zones = r.zones
    t: list[str] = [
        "# Rapport de couverture",
        "",
        f"Produit par `vi couverture` le {r.genere_le:%d/%m/%Y}. Taux de remplissage de chaque champ, "
        "par département d'Île-de-France.",
        "",
        "- **%** : part des lignes où le champ est connu. **–** : aucune ligne.",
        "- **\\*** : part des lignes concernées. Une absence y veut dire « non », pas « inconnu ».",
        "- Une ligne qui touche plusieurs départements compte une fois dans chacun.",
        "- Les doublons entre sources sont exclus : seule la fiche principale compte.",
        "- Source, adresse web, méthode, date de collecte et confiance : 100 % partout, imposé par le schéma.",
        "",
        *_faibles(r),
        "## Nombre de lignes",
        "",
        *_tableau(["Table", *zones], [
            [m.table.libelle, *(entier(m.total.get(z, 0)) for z in zones)] for m in r.mesures
        ]),
        "",
    ]
    for m in r.mesures:
        t += [f"## {m.table.libelle}", "", f"Table `{m.table.nom}`.", ""]
        t += _tableau(["Champ", *zones], [
            [_libelle(c), *(pourcent(m.taux(c, z)) for z in zones)] for c in m.table.champs
        ])
        # Causes : seulement pour les champs réellement incomplets, regroupées quand elles sont communes.
        causes: dict[str, list[str]] = {}
        for c in m.table.champs:
            taux = m.taux(c, REGION)
            if c.cause and (taux is None or taux < 0.9):
                causes.setdefault(c.cause, []).append(_minuscule(c.libelle))
        if causes:
            t += ["", "Pourquoi c'est incomplet :", ""]
            t += [f"- {', '.join(champs)} : {cause}." for cause, champs in causes.items()]
        t.append("")
    t += _visites(r)
    t += _sources(r)
    return "\n".join(t).rstrip() + "\n"


def _faibles(r: Rapport) -> list[str]:
    """Champs connus pour moins de la moitié des lignes, du moins rempli au plus rempli."""
    lignes = []
    for m in r.mesures:
        for c in m.table.champs:
            taux = m.taux(c, REGION)
            if c.nature == "rempli" and taux is not None and taux < SEUIL_FAIBLE:
                deps = [(x, z) for z in r.departements if (x := m.taux(c, z)) is not None]
                lignes.append((taux, [
                    f"{m.table.libelle} : {_minuscule(c.libelle)}", pourcent(taux),
                    *(f"{pourcent(x)} ({z})" for x, z in (min(deps), max(deps))),
                ]))
    if not lignes:
        return []
    return ["## Champs connus pour moins de la moitié des lignes", "",
            *_tableau(["Champ", REGION, "Département le plus bas", "Département le plus haut"],
                      [x for _, x in sorted(lignes, key=lambda t: t[0])]), ""]


def _visites(r: Rapport) -> list[str]:
    if not r.visites:
        return []
    t = ["## Visite des sites web", ""]
    for type_, libelle in LIBELLES_OBJET.items():
        lignes = [v for v in r.visites if v["objet_type"] == type_]
        if lignes:
            detail = ", ".join(f"{LIBELLES_STATUT.get(v['statut'], v['statut'])} {entier(v['n'])}" for v in lignes)
            t.append(f"- {libelle} ({entier(sum(v['n'] for v in lignes))}) : {detail}.")
    return [*t, ""]


def _sources(r: Rapport) -> list[str]:
    # La Base adresse nationale n'a pas de collecte propre : elle sert aux autres sources.
    ouvertes = [s for s in r.sources if s["statut"] == "ouverte" and s["methode"] != "calcul" and s["code"] != "ban"]
    fermees = [s for s in r.sources if s["statut"] != "ouverte"]
    t = ["## Sources collectées", "", "| Source | Méthode | Fréquence | Dernière collecte |", "|---|---|---|---|"]
    for s in ouvertes:
        jour = f"{s['collecte']:%d/%m/%Y}" if s["collecte"] else "jamais"
        t.append(f"| {s['libelle']} | {s['methode']} | {s['frequence']} | {jour} |")
    if fermees:
        t += ["", "## Sources écartées", "",
              "Leurs conditions d'utilisation, vérifiées avant collecte, interdisent l'extraction automatique.", ""]
        t += [f"- **{s['libelle']}** : {' '.join((s['verification'] or {}).get('constat', 'non précisé').split())}"
              for s in fermees]
    return t


def csv_long(r: Rapport) -> str:
    """Une ligne par table, champ et zone."""
    f = io.StringIO()
    w = csv.writer(f, delimiter=";", lineterminator="\n")
    w.writerow(["table", "champ", "libelle", "nature", "zone", "lignes", "remplies", "taux"])
    for m in r.mesures:
        for c in m.table.champs:
            for z in r.zones:
                taux = m.taux(c, z)
                w.writerow([m.table.nom, c.code, c.libelle, c.nature, z, m.concernees[c.code].get(z, 0),
                            m.remplies[c.code].get(z, 0), "" if taux is None else f"{taux:.4f}".replace(".", ",")])
    return f.getvalue()


def pour_carte(r: Rapport) -> dict[str, Any]:
    return {
        "genere_le": r.genere_le,
        "zones": r.zones,
        "tables": [
            {
                "nom": m.table.nom, "libelle": m.table.libelle, "lignes": [m.total.get(z, 0) for z in r.zones],
                "champs": [
                    {
                        "libelle": c.libelle, "nature": c.nature, **({"cause": c.cause} if c.cause else {}),
                        "taux": [None if (x := m.taux(c, z)) is None else round(x, 4) for z in r.zones],
                    }
                    for c in m.table.champs
                ],
            }
            for m in r.mesures
        ],
    }
