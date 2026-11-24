"""Gestionnaires des accueils périscolaires, et accueils supplémentaires trouvés par leur nom.

Les dirigeants ne sont pas demandés à l'API (réponse minimale).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..db import point, upsert
from ..outils import motifs
from ..outils.texte import adresse_sans_personne, normaliser, sans_contact, titre
from .base import Compteurs, Contexte, connecteur
from .sirene import NAF_EXCLUES

RECHERCHES = ["centre de loisirs", "accueil de loisirs", "periscolaire", "centre aere", "alsh"]
FICHE = "https://annuaire-entreprises.data.gouv.fr/{type}/{numero}"
PAGES_MAX = 20


def type_gestionnaire(nature_juridique: str | None) -> str:
    """Catégorie juridique Insee : 7xxx organismes publics, 92xx associations, sinon entreprise."""
    code = nature_juridique or ""
    if code.startswith("7"):
        return "regie"
    return "association" if code.startswith(("92", "93")) else "entreprise"


def chercher(ctx: Contexte, **params: Any) -> Iterator[dict[str, Any]]:
    page = 1
    while page <= PAGES_MAX:
        d = ctx.http.json(f"{ctx.config.url}/search", params={
            "etat_administratif": "A", "per_page": 25, "page": page, "minimal": "true",
            "include": "matching_etablissements,siege", "limite_matching_etablissements": 100, **params,
        })
        yield from d["results"]
        if page >= d["total_pages"]:
            return
        page += 1


@connecteur("recherche_entreprises", depend_de=["ign_admin_express", "sirene", "osm"])
def collecter(ctx: Contexte) -> Compteurs:
    trouves = decouvrir(ctx)
    supprimes = ctx.purger("accueil_periscolaire")
    gestionnaires, anonymes = identifier(ctx)
    supprimes += ctx.purger("gestionnaire_perisco")
    return {"accueils_trouves": trouves, "gestionnaires": gestionnaires, "personnes_physiques_ignorees": anonymes,
            "supprimes": supprimes}


def decouvrir(ctx: Contexte) -> int:
    communes = {r["code_insee"] for r in ctx.conn.execute("SELECT code_insee FROM commune")}
    connus = {
        r["id"].removeprefix("sirene:")
        for r in ctx.conn.execute("SELECT id FROM accueil_periscolaire WHERE id LIKE 'sirene:%%'")
    }
    lignes: dict[str, dict[str, Any]] = {}
    for dep in ctx.idf.departements:
        for q in RECHERCHES:
            for e in chercher(ctx, q=q, departement=dep):
                if (e["nature_juridique"] or "").startswith("1"):
                    continue  # personne physique
                for s in e["matching_etablissements"]:
                    nom = nom_accueil(e, s)
                    if (
                        nom is None or s["etat_administratif"] != "A" or s["siret"] in connus
                        or s["commune"] not in communes or not s["latitude"] or not s["longitude"]
                        or (s["activite_principale"] or "").startswith(NAF_EXCLUES)
                    ):
                        continue
                    n = normaliser(nom)
                    lignes[s["siret"]] = {
                        "id": f"re:{s['siret']}",
                        "nom": titre(sans_contact(nom)),
                        "adresse": adresse_sans_personne(titre(s["adresse"])),
                        "commune": s["commune"],
                        "accueil_soir": motifs.accueil_soir(n),
                        "accueil_mercredi": motifs.accueil_mercredi(n),
                        "horaires": None,
                        "geom": point(float(s["longitude"]), float(s["latitude"])),
                        **ctx.provenance(FICHE.format(type="etablissement", numero=s["siret"]), confiance=0.7),
                    }
    return upsert(ctx.conn, "accueil_periscolaire", lignes.values(), ["id"])


def nom_accueil(entreprise: dict[str, Any], etablissement: dict[str, Any]) -> str | None:
    """Enseigne ou nom de l'établissement s'il désigne un accueil, sinon nom de l'organisme."""
    candidats = [*(etablissement["liste_enseignes"] or []), etablissement["nom_commercial"], entreprise["nom_complet"]]
    return next((c for c in candidats if c and motifs.est_accueil(normaliser(c))), None)


def identifier(ctx: Contexte) -> tuple[int, int]:
    """Nom et type du gestionnaire de chaque accueil dont le Siren (ou la commune exploitante) est connu."""
    sirens: dict[str, list[str]] = {}
    for a in ctx.conn.execute(
        "SELECT id, split_part(id, ':', 2) AS siret FROM accueil_periscolaire WHERE id ~ '^(sirene|re):[0-9]{14}$'"
    ):
        sirens.setdefault(a["siret"][:9], []).append(a["id"])
    # OSM : exploitant « Mairie de X » ou nom « municipal » -> la commune elle-même
    for a in ctx.conn.execute(
        "SELECT a.id, a.nom, a.exploitant, c.siren, c.nom AS commune FROM accueil_periscolaire a "
        "JOIN commune c ON c.code_insee = a.commune WHERE a.source = 'osm' AND c.siren IS NOT NULL"
    ):
        exploitant = normaliser(a["exploitant"])
        publics = ("mairie", "ville de", "commune de", "municipal", normaliser(a["commune"]))
        if any(p in exploitant for p in publics if exploitant) or "municipal" in normaliser(a["nom"]):
            sirens.setdefault(a["siren"], []).append(a["id"])

    gestionnaires, anonymes = [], 0
    for siren in sirens:
        trouve = next((e for e in chercher(ctx, q=siren) if e["siren"] == siren), None)
        if trouve is None:
            continue
        if (trouve["nature_juridique"] or "").startswith("1"):
            anonymes += 1
            continue
        gestionnaires.append({
            "siren": siren,
            "nom": titre(sans_contact(trouve["nom_complet"])),
            "type": type_gestionnaire(trouve["nature_juridique"]),
            "nb_accueils": len(sirens[siren]),
            **ctx.provenance(FICHE.format(type="entreprise", numero=siren)),
        })
    upsert(ctx.conn, "gestionnaire_perisco", gestionnaires, ["siren"])
    ctx.conn.execute("UPDATE accueil_periscolaire SET gestionnaire_siren = NULL")
    for g in gestionnaires:
        ctx.conn.execute(
            "UPDATE accueil_periscolaire SET gestionnaire_siren = %s WHERE id = ANY(%s)",
            (g["siren"], sirens[g["siren"]]),
        )
    return len(gestionnaires), anonymes
