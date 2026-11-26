"""Fiches des acteurs (un fichier par nature) et carnet de contacts : tout ce qu'on ouvre d'un clic sur la carte.

Un contact garde toujours sa provenance `p` : celle de la ligne, du doublon qui le porte, ou du groupe de champs.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from ..config import ConfigJauges
from ..outils.texte import normaliser
from .commun import ACCUEILS, CITE_ECOLE, Connexion, prov, prov_groupes, sans_vide

PROCHES_MAX = 15  # écoles citées dans la fiche d'un producteur ou d'un relais

Fiche = dict[str, Any]
Fiches = dict[str, Fiche]

_FORMES = re.compile(
    r"^(?:communaute de communes|communaute d agglomeration|communaute urbaine|conseil departemental|departement"
    r"|conseil regional|region|ville|commune|etablissement public territorial|ept|cc|ca|cu)\b"
    r"(?: (?:de|du|des|d|la|le|les|l)\b)*"
)


def cle_nom(nom: str | None) -> str:
    """Nom d'une collectivité sans sa forme : « CC entre Juine et Renarde » et « Communauté de communes Entre… »."""
    n = normaliser(re.sub(r"\(.*?\)", " ", nom or ""))
    return _FORMES.sub("", n).strip() or n


def contact(r: dict[str, Any], *doublons: dict[str, Any], **champs: Any) -> Fiche | None:
    """Coordonnées d'une ligne, sinon du premier doublon qui en a (même lieu, autre source)."""
    for x in (r, *doublons):
        c = sans_vide({"tel": x.get("telephone"), "email": x.get("email"), "site": x.get("site_web"),
                       "formulaire": x.get("formulaire"), **champs})
        if c:
            return {**c, "p": prov(x)}
    return None


def _xy(r: dict[str, Any]) -> list[float] | None:
    return None if r["lon"] is None else [round(r["lon"], 5), round(r["lat"], 5)]


def par(lignes: Iterable[dict[str, Any]], cle: str) -> dict[str, list[dict[str, Any]]]:
    groupes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in lignes:
        groupes[r[cle]].append(r)
    return groupes


class Acteurs:
    def __init__(self, conn: Connexion, cfg: ConfigJauges, departements: dict[str, str]) -> None:
        self.conn, self.cfg, self.departements = conn, cfg, departements
        self.communes = {r["code_insee"]: r for r in conn.execute(
            """SELECT code_insee, nom, siren, departement, commune_mere, epci_siren, ept_siren, site_web,
                      mairie_telephone, mairie_email, mairie_formulaire, cuisine_centrale_siret, provenances,
                      source, url, collecte_le, confiance FROM commune ORDER BY code_insee""")}
        self.par_siren = {r["siren"]: c for c, r in self.communes.items() if r["siren"]}
        self.organismes = {r["siren"]: r for r in conn.execute("SELECT * FROM organisme ORDER BY siren")}
        self.dispositifs = {r["id"]: r for r in conn.execute("SELECT * FROM dispositif ORDER BY id")}
        self.porteurs = self._porteurs()

    # ---------------------------------------------------------------- liens entre collectivités
    def _porteurs(self) -> dict[str, Fiche]:
        """Dispositif -> collectivité qui le porte : {organisme: siren} ou {commune: code}, si elle est reconnue."""
        par_type = {("departement", o["departement"]): s for s, o in self.organismes.items()
                    if o["type"] == "departement"}
        region = next((s for s, o in self.organismes.items() if o["type"] == "region"), None)
        noms_o = {cle_nom(o["nom"]): s for s, o in self.organismes.items()}
        noms_c = {cle_nom(c["nom"]): code for code, c in self.communes.items()}
        porteurs: dict[str, Fiche] = {}
        for id_, d in self.dispositifs.items():
            fin = id_.rsplit(":", 1)[-1]
            siren = commune = None
            if d["type"] == "soutien_territorial":
                siren = {"region": region, "departement": par_type.get(("departement", fin)),
                         "interco": fin if fin in self.organismes else None}.get(d["echelon"])
            elif d["type"] == "syndicat_restauration":
                sigle = normaliser(d["nom"]).split(" ")[0]
                siren = next((s for s, o in self.organismes.items() if o["type"] == "syndicat_restauration"
                              and sigle in normaliser(o["nom"]).split()), None)
            elif d["type"] == "laureat_aap_mgp":
                commune = fin if fin in self.communes else None
            elif d["porteur"]:
                cle = cle_nom(d["porteur"])
                est_ville = normaliser(d["porteur"]).startswith(("ville", "commune "))
                siren = None if est_ville else noms_o.get(cle)
                commune = noms_c.get(cle) if est_ville else None
            if siren or commune:
                porteurs[id_] = sans_vide({"organisme": siren, "commune": commune})
        return porteurs

    def pat(self, id_: str) -> Fiche:
        """Compléments d'un PAT pour sa couche : porteur, service, contact, priorités."""
        d = self.dispositifs[id_]
        return sans_vide({
            "porteur": d["porteur"], "priorites": d["priorites"], "restauration": d["axe_restauration_collective"],
            "contact": contact(d, service=d["service"]), **self.porteurs.get(id_, {}),
        })

    # ---------------------------------------------------------------- fiches par nature
    def fiches(self) -> dict[str, Fiches]:
        accueils = self._accueils()
        return {
            "accueil": accueils, "asso": self._assos(), "producteur": self._producteurs(),
            "relais": self._relais(), "alimentation": self._alimentation(),
            "gestionnaire": self._gestionnaires(accueils), "cuisine": self._cuisines(),
            "dispositif": self._dispositifs(), "organisme": self._organismes(), "iris": self._iris(),
        }

    def _doublons(self, table: str) -> dict[str, list[dict[str, Any]]]:
        return par(self.conn.execute(
            f"SELECT * FROM {table} WHERE doublon_de IS NOT NULL ORDER BY confiance DESC, id").fetchall(), "doublon_de")

    def _proches(self, type_: str) -> dict[str, list[list[Any]]]:
        """Écoles les plus proches de chaque cible : [UAI, km, minutes]."""
        liste: dict[str, list[list[Any]]] = defaultdict(list)
        for r in self.conn.execute(
            """SELECT * FROM (
                 SELECT cible_id, ecole_uai, coalesce(km_route, km_vol_oiseau) AS km, minutes,
                        row_number() OVER (PARTITION BY cible_id ORDER BY minutes NULLS LAST, ecole_uai) AS rang
                 FROM proximite WHERE cible_type = %s) t
               WHERE rang <= %s ORDER BY cible_id, rang""", (type_, PROCHES_MAX)
        ):
            liste[r["cible_id"]].append([
                r["ecole_uai"], round(r["km"], 1), None if r["minutes"] is None else round(r["minutes"], 1)])
        return liste

    def _accueils(self) -> Fiches:
        doublons = self._doublons("accueil_periscolaire")
        liens = par(self.conn.execute(
            "SELECT * FROM accueil_ecole ORDER BY accueil_id, distance_m, ecole_uai").fetchall(), "accueil_id")
        return {r["id"]: sans_vide({
            "nom": r["nom"], "commune": r["commune"], "adresse": r["adresse"], "xy": _xy(r),
            "soir": r["accueil_soir"], "mercredi": r["accueil_mercredi"], "horaires": r["horaires"],
            "gestionnaire": r["gestionnaire"], "gestionnaire_type": r["gestionnaire_type"], "siren": r["siren"],
            "ecoles": [{"uai": x["ecole_uai"], "m": x["distance_m"], "motif": x["motif"], "c": x["confiance"]}
                       for x in liens[r["id"]]],
            "contact": contact(r, *doublons[r["id"]]), "p": prov(r),
        }) for r in self.conn.execute(f"SELECT a.* FROM ({ACCUEILS}) a ORDER BY a.id")}

    def _assos(self) -> Fiches:
        liens = par(self.conn.execute(
            "SELECT * FROM asso_ecole ORDER BY asso_id, confiance DESC, ecole_uai").fetchall(), "asso_id")
        return {r["id"]: sans_vide({
            "nom": r["nom"], "commune": r["commune"], "siege": r["siege"], "federation": r["federation"],
            "objet": r["objet"], "rna": r["rna"], "siren": r["siren"], "creation": r["date_creation"],
            "activite": r["derniere_activite"], "activite_url": r["derniere_activite_url"], "xy": _xy(r),
            "ecoles": [{"uai": x["ecole_uai"], "c": x["confiance"]} for x in liens[r["id"]]],
            "contact": contact(r), "p": prov(r), "pg": prov_groupes(r["provenances"]),
        }) for r in self.conn.execute(
            """SELECT *, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM asso_parents
               WHERE doublon_de IS NULL AND niveau <> 'second_degre' ORDER BY id""")}

    def _producteurs(self) -> Fiches:
        proches = self._proches("producteur")
        return {r["id"]: sans_vide({
            "nom": r["nom"], "commune": r["commune"], "adresse": r["adresse"], "adresse_type": r["adresse_type"],
            "xy": _xy(r), "activites": r["activites"], "productions": r["productions"], "bio": r["etat_bio"],
            "legumes": r["maraichage"], "fruits": r["fruits"], "vente": r["vente_directe"],
            "collective": r["vente_restauration_collective"], "amap": r["membre_amap"], "eligible": r["eligible"],
            "compte": r["eligible"] and r["adresse_type"] in self.cfg.producteurs.adresses,
            "numero_bio": r["numero_bio"], "siret": r["siret"], "proches": proches.get(r["id"]),
            "contact": contact(r), "p": prov(r),
        }) for r in self.conn.execute(
            "SELECT *, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM producteur ORDER BY id")}

    def _relais(self) -> Fiches:
        doublons, proches = self._doublons("relais_local"), self._proches("relais_local")
        return {r["id"]: sans_vide({
            "nom": r["nom"], "type": r["type"], "commune": r["commune"], "adresse": r["adresse"], "xy": _xy(r),
            "proches": proches.get(r["id"]), "contact": contact(r, *doublons[r["id"]]), "p": prov(r),
        }) for r in self.conn.execute(
            """SELECT *, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM relais_local
               WHERE doublon_de IS NULL ORDER BY id""")}

    def _alimentation(self) -> Fiches:
        return {r["id"]: sans_vide({
            "nom": r["nom"], "type": r["categorie"], "commune": r["commune"], "objet": r["objet"], "rna": r["rna"],
            "creation": r["date_creation"], "declaration": r["derniere_declaration"], "xy": _xy(r),
            "contact": contact(r), "p": prov(r),
        }) for r in self.conn.execute(
            "SELECT *, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM asso_alimentation ORDER BY id")}

    def _gestionnaires(self, accueils: Fiches) -> Fiches:
        geres: dict[str, list[str]] = defaultdict(list)
        for id_, a in accueils.items():
            if "siren" in a:
                geres[a["siren"]].append(id_)
        return {r["siren"]: sans_vide({
            "nom": r["nom"], "type": r["type"], "siren": r["siren"],
            "commune": self.par_siren.get(r["siren"]),
            "accueils": geres[r["siren"]],
            "communes": sorted({accueils[i]["commune"] for i in geres[r["siren"]] if "commune" in accueils[i]}),
            "p": prov(r),
        }) for r in self.conn.execute("SELECT * FROM gestionnaire_perisco ORDER BY siren")}

    def _cuisines(self) -> Fiches:
        livrees: dict[str, list[str]] = defaultdict(list)
        for code, c in self.communes.items():
            if c["cuisine_centrale_siret"]:
                livrees[c["cuisine_centrale_siret"]].append(code)
        return {r["siret"]: sans_vide({
            "nom": r["nom"], "type": r["type"], "siret": r["siret"],
            "commune": r["commune"] or self.par_siren.get(r["siret"][:9]),
            "organisme": r["siret"][:9] if r["siret"][:9] in self.organismes else None,
            "gestion": r["gestion"], "cantines": r["nb_cantines"], "repas": r["repas_jour"], "bio": r["pct_bio"],
            "egalim": r["pct_egalim"], "annee": r["annee"], "communes": livrees[r["siret"]], "p": prov(r),
        }) for r in self.conn.execute("SELECT * FROM cuisine_centrale ORDER BY siret")}

    def nom_dispositif(self, d: dict[str, Any]) -> str:
        if d["type"] == "soutien_territorial" and d["echelon"] == "departement":
            return f"Département : {self.departements.get(d['nom'], d['nom'])}"
        if d["type"] == "soutien_territorial" and d["echelon"] == "region":
            return f"Région {d['nom']}"
        return str(d["nom"])

    def _dispositifs(self) -> Fiches:
        """Tout sauf les PAT et leurs mentions « lauréat », qui ont leur propre couche."""
        ecoles: dict[str, list[Fiche]] = defaultdict(list)
        for e in self.conn.execute(
            f"""SELECT e.uai, e.qpv, e.qpv_distance_m AS m, e.confiance, {CITE_ECOLE} AS cite_id
                FROM ecole e WHERE e.qpv IS NOT NULL OR e.cite_educative IS NOT NULL
                ORDER BY e.qpv_distance_m, e.uai"""
        ):
            if e["qpv"]:
                ecoles[e["qpv"]].append({"uai": e["uai"], "m": e["m"], "c": e["confiance"]})
            if e["cite_id"]:
                ecoles[e["cite_id"]].append({"uai": e["uai"], "c": e["confiance"]})
        return {id_: sans_vide({
            "nom": self.nom_dispositif(d), "type": d["type"], "communes": d["communes"], "echelon": d["echelon"],
            "score": d["score"], "editions": d["editions"], "priorites": d["priorites"], "annee": d["annee"],
            "niveau": d["niveau"], "ecoles": ecoles[id_], **self.porteurs.get(id_, {}), "p": prov(d),
        }) for id_, d in self.dispositifs.items() if d["type"] not in ("pat", "laureat_aap")}

    def _organismes(self) -> Fiches:
        soutiens: dict[str, list[str]] = defaultdict(list)
        for id_, p in self.porteurs.items():
            if "organisme" in p and self.dispositifs[id_]["type"] != "laureat_aap":
                soutiens[p["organisme"]].append(id_)
        return {s: sans_vide({
            "nom": o["nom"], "type": o["type"], "siren": s, "dep": o["departement"], "communes": o["communes"],
            "dispositifs": soutiens[s], "contact": contact(o), "p": prov(o),
        }) for s, o in self.organismes.items()}

    def _iris(self) -> Fiches:
        ecoles = par(self.conn.execute("SELECT uai, iris FROM ecole WHERE iris IS NOT NULL ORDER BY uai").fetchall(),
                     "iris")
        return {r["iris"]: sans_vide({
            "nom": r["nom"], "commune": r["commune"], "familles": r["familles_avec_enfants"],
            "revenu": r["revenu_median"], "pauvrete": r["taux_pauvrete"], "annee": r["annee_familles"],
            "annee_revenus": r["annee_revenus"], "qpv": r["qpv"], "part_qpv": r["part_qpv"],
            "uais": [e["uai"] for e in ecoles[r["iris"]]], "p": prov(r), "pg": prov_groupes(r["provenances"]),
        }) for r in self.conn.execute(
            """SELECT iris, nom, commune, familles_avec_enfants, revenu_median, taux_pauvrete, annee_familles,
                      annee_revenus, qpv, part_qpv, provenances, source, url, collecte_le, confiance
               FROM territoire_social ORDER BY iris""")}

    # ---------------------------------------------------------------- carnet de contacts
    def carnet(self, fiches: dict[str, Fiches]) -> list[Fiche]:
        """Un contact par ligne : mairies, écoles et acteurs qui en publient un, avec sa provenance."""
        lignes: list[Fiche] = []
        for code, c in self.communes.items():
            fiche = self.contact_mairie(code)
            if fiche:
                lignes.append({"n": "commune", "id": code, "nom": f"Mairie de {c['nom']}", "commune": code, **fiche})
        for e in self.conn.execute(
            """SELECT uai, nom, commune, telephone, email, source, url, collecte_le, confiance FROM ecole
               WHERE telephone IS NOT NULL OR email IS NOT NULL ORDER BY uai"""
        ):
            lignes.append({"n": "ecole", "id": e["uai"], "nom": e["nom"], "commune": e["commune"],
                           **(contact(e) or {})})
        for nature, liste in fiches.items():
            lignes += [sans_vide({
                "n": nature, "id": id_, "nom": f["nom"], "commune": f.get("commune"),
                "communes": f.get("communes") if nature == "organisme" else None, "dep": f.get("dep"),
                "type": f.get("type"), **f["contact"],
            }) for id_, f in liste.items() if f.get("contact")]
        for id_, d in self.dispositifs.items():
            if d["type"] == "pat" and (x := contact(d, service=d["service"])):
                lignes.append(sans_vide({
                    "n": "pat", "id": id_, "nom": d["nom"] if not d["porteur"] else f"{d['nom']} ({d['porteur']})",
                    "communes": d["communes"], **x}))
        return lignes

    def contact_mairie(self, code: str) -> Fiche | None:
        c = self.communes[code]
        groupes = prov_groupes(c["provenances"])
        x = sans_vide({"tel": c["mairie_telephone"], "email": c["mairie_email"], "site": c["site_web"],
                       "formulaire": c["mairie_formulaire"]})
        p = groupes.get("contact_mairie") or groupes.get("site_web")
        return {**x, "p": p} if x and p else None
