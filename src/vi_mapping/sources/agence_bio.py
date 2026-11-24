"""Producteurs bio (API Professionnels Bio de l'Agence Bio).

Téléphones et e-mails ne sont jamais conservés ; `gerant` ne sert qu'à écarter, en mémoire, les noms
de personnes physiques : un exploitant individuel sans nom commercial est anonymisé.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..config import Producteurs
from ..db import point, upsert
from ..outils.ban import Adresse, geocoder
from ..outils.texte import adresse_sans_personne, normaliser, propre, sans_contact, titre
from .base import Compteurs, Contexte, connecteur

PAGE = 500
FICHE = "https://annuaire.agencebio.org/fiche/{numero}"
TYPES_ADRESSE = {"Lieux d'activité": "lieu_activite", "Lieux de vente": "lieu_vente", "Siège social": "siege"}
# Mots qui signalent un nom d'entreprise ou de lieu plutôt qu'un nom de personne
MOTS_ENTREPRISE = {
    "abbaye", "abeille", "abeilles", "agricole", "agricoles", "agriculture", "agroforesterie", "association",
    "atelier", "aux", "bergerie", "bio", "biologique", "bois", "brasserie", "centre", "champ", "champignon",
    "champignons", "champs", "chateau", "clos", "cocagne", "collectif", "commune", "compagnie", "conservatoire",
    "cooperative", "cueillette", "culture", "cultures", "des", "domaine", "du", "earl", "elevage", "entreprise",
    "esat", "etablissement", "etablissements", "etang", "ets", "eurl", "exploitation", "ferme", "fermes", "fils",
    "foret", "freres", "fruits", "gaec", "graines", "groupement", "herbes", "houblon", "houblonniere", "inrae",
    "institut", "jardin", "jardinier", "jardins", "l", "la", "le", "legumes", "les", "lycee", "maraichage",
    "maraichages", "maraicher", "maraichere", "maraichers", "micro", "miel", "moulin", "oeufs", "panier", "paniers",
    "pepiniere", "pepinieres", "permaculture", "plaine", "plaines", "plantes", "potager", "potagers", "poules",
    "prieure", "rucher", "ruchers", "sa", "safran", "safraniere", "sarl", "sas", "sasu", "saveurs", "sca", "scea",
    "scev", "sci", "scic", "scop", "semences", "serre", "serres", "sicae", "simples", "snc", "societe", "source",
    "sources", "terre", "terres", "terroir", "urbain", "urbaine", "vallee", "verger", "vergers", "vigne", "vignes",
    "vignoble", "ville",
}


def nom_public(operateur: dict[str, Any]) -> str | None:
    """Nom commercial sans nom de personne physique, ou None s'il faut anonymiser."""
    gerant = {m for m in normaliser(operateur.get("gerant")).split() if len(m) > 1}
    for brut in (operateur.get("denominationcourante"), operateur.get("raisonSociale")):
        mots = normaliser(brut).split()
        if not mots or mots[0] in {"m", "mr", "mme", "mlle", "monsieur", "madame"}:
            continue
        communs = gerant & set(mots)
        if gerant and (communs == gerant or len(communs) >= 2):
            continue  # nom et prénom de l'exploitant
        if set(mots) & MOTS_ENTREPRISE or (gerant and not communs and len(mots) == 1):
            return titre(sans_contact(brut))
    return None


def types_production(operateur: dict[str, Any], c: Producteurs) -> tuple[bool, bool, set[str], set[str]]:
    """(maraîchage, fruits, états bio des légumes et fruits, états bio de toutes les productions)."""
    maraichage = fruits = False
    etats: set[str] = set()
    tous: set[str] = set()
    for p in operateur.get("productions") or []:
        code = p.get("code") or ""
        est_m = code.startswith(tuple(c.prefixes_maraichage))
        est_f = code.startswith(tuple(c.prefixes_fruits))
        maraichage, fruits = maraichage or est_m, fruits or est_f
        de_la_production = {e["etatProduction"] for e in p.get("etatProductions") or []}
        tous |= de_la_production
        if est_m or est_f:
            etats |= de_la_production
    noms = {a["nom"] for a in operateur.get("annuaireActivites") or []}
    maraichage = maraichage or bool(noms & set(c.activites_maraichage))
    fruits = fruits or bool(noms & set(c.activites_fruits))
    return maraichage, fruits, etats, tous


def etat_bio(etats: set[str], c: Producteurs) -> str:
    bio, conversion = bool(etats & set(c.etats_bio)), bool(etats & set(c.etats_conversion))
    if bio and conversion:
        return "bio_et_conversion"
    return "bio" if bio else "conversion" if conversion else "inconnu"


def vente_directe(operateur: dict[str, Any], c: Producteurs) -> bool | None:
    if {k["nom"] for k in operateur.get("categories") or []} & set(c.categories_vente_directe):
        return True
    return (operateur.get("venteAnnuaire") or {}).get("venteParticuliers")


def meilleure_adresse(operateur: dict[str, Any], communes: set[str]) -> tuple[str, dict[str, Any]] | None:
    """Adresse francilienne la plus proche du lieu de production : activité, puis vente, puis siège."""
    for libelle, type_ in TYPES_ADRESSE.items():
        for a in operateur["adressesOperateurs"]:
            if libelle in a["typeAdresseOperateurs"] and a["codeCommune"] in communes and a.get("active", True):
                return type_, a
    return None


def operateurs(ctx: Contexte) -> Iterator[dict[str, Any]]:
    vus: set[int] = set()
    for dep in ctx.idf.departements:
        debut = 0
        while True:
            page = ctx.http.json(ctx.config.url, params={
                "departements": dep, "activite": "Production", "nb": PAGE, "debut": debut,
            })
            for o in page["items"]:
                if o["id"] not in vus:
                    vus.add(o["id"])
                    yield o
            debut += PAGE
            if not page["items"] or debut >= int(page["nbTotal"]):
                break


@connecteur("agence_bio", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    c = ctx.idf.producteurs
    communes = {r["code_insee"]: r["nom"] for r in ctx.conn.execute("SELECT code_insee, nom FROM commune")}
    lignes: list[dict[str, Any]] = []
    a_geocoder: dict[str, Adresse] = {}
    compte = {"operateurs": 0, "non_certifies": 0, "hors_idf": 0, "noms_anonymises": 0, "sans_position": 0}
    for o in operateurs(ctx):
        compte["operateurs"] += 1
        if not any(k["etatCertification"] in c.certifications_actives for k in o["certificats"]):
            compte["non_certifies"] += 1
            continue
        choix = meilleure_adresse(o, set(communes))
        if choix is None:
            compte["hors_idf"] += 1
            continue
        type_adresse, a = choix
        maraichage, fruits, etats, tous = types_production(o, c)
        etat, directe = etat_bio(etats, c), vente_directe(o, c)
        nom = nom_public(o)
        compte["noms_anonymises"] += nom is None
        rue = adresse_sans_personne(titre(a["lieu"])) or ""
        ville = propre(f"{a['codePostal']} {titre(a['ville'])}")
        id_ = f"agencebio:{o['numeroBio']}"
        if a.get("lat") is None or a.get("long") is None:
            a_geocoder[id_] = Adresse(rue or str(a["ville"]), str(a["codePostal"]), a["codeCommune"])
        lignes.append({
            "id": id_,
            "siret": (o.get("siret") or "").strip() or None,
            "numero_bio": o["numeroBio"],
            "nom": nom or f"Producteur bio n° {o['numeroBio']} ({communes[a['codeCommune']]})",
            "activites": sorted({propre(x["nom"]) or "" for x in o.get("annuaireActivites") or []} - {""}),
            "productions": sorted({propre(x["nom"]) or "" for x in o.get("productions") or []} - {""}),
            "maraichage": maraichage,
            "fruits": fruits,
            "etat_bio": etat if etat != "inconnu" else etat_bio(tous, c),
            "vente_directe": directe,
            "membre_amap": None,  # l'API ne le dit pas ; la carte du Réseau AMAP IdF est verrouillée
            "eligible": etat != "inconnu" and (maraichage or fruits) and bool(directe),
            # Siège d'un exploitant individuel : souvent son domicile, on s'en tient à la ville.
            "adresse": ville if nom is None and type_adresse == "siege" else propre(f"{rue}, {ville}".strip(" ,")),
            "adresse_type": type_adresse,
            "commune": a["codeCommune"],
            "geom": point(a["long"], a["lat"]) if id_ not in a_geocoder else None,
            **ctx.provenance(FICHE.format(numero=o["numeroBio"]), confiance=c.confiance_adresse[type_adresse]),
        })
    positions = geocoder(ctx.conn, ctx.http, a_geocoder.values())
    gardees = []
    for ligne in lignes:
        if ligne["geom"] is None:
            pos = positions.get(a_geocoder[ligne["id"]])
            if pos is None:
                compte["sans_position"] += 1
                continue
            ligne["geom"] = point(pos.lon, pos.lat)
            ligne["confiance"] = round(ligne["confiance"] * pos.confiance, 2)
        gardees.append(ligne)
    n = upsert(ctx.conn, "producteur", gardees, ["id"])
    return {**compte, "producteurs": n, "eligibles": sum(ligne["eligible"] for ligne in gardees),
            "supprimes": ctx.purger("producteur")}
