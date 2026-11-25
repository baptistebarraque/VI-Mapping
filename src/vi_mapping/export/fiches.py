"""Fiches détaillées, un fichier par commune : la collectivité, ses écoles et tous les acteurs liés."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from typing import Any

from .commun import ACCUEILS, Connexion, prov, prov_groupes, sans_vide

SIGNAUX_MAX = 40
RELAIS_PAR_TYPE = 10
ASSOS_ALIMENTATION_MAX = 40


def par(lignes: Iterable[dict[str, Any]], cle: str) -> dict[str, list[dict[str, Any]]]:
    groupes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in lignes:
        groupes[r[cle]].append(r)
    return groupes


class Fiches:
    """Charge tout en mémoire (région entière), puis compose les fiches commune par commune."""

    def __init__(self, conn: Connexion, rang_producteur: dict[str, int], rang_relais: dict[str, int]) -> None:
        self.conn = conn
        self.rang_producteur, self.rang_relais = rang_producteur, rang_relais
        self.communes = {r["code_insee"]: r for r in conn.execute(
            """SELECT c.*, m.nom AS mere_nom,
                      (SELECT count(*) FROM accueil_periscolaire a WHERE a.commune = c.code_insee
                         AND a.doublon_de IS NULL) AS nb_accueils,
                      (SELECT count(*) FROM asso_parents a WHERE a.commune = c.code_insee AND a.doublon_de IS NULL
                         AND a.niveau <> 'second_degre') AS nb_assos,
                      (SELECT count(*) FROM relais_local x WHERE x.commune = c.code_insee AND x.doublon_de IS NULL)
                        AS nb_relais,
                      (SELECT count(*) FROM producteur p WHERE p.commune = c.code_insee AND p.eligible)
                        AS nb_producteurs,
                      (SELECT count(*) FROM elu x WHERE x.commune = c.code_insee) AS nb_elus
               FROM commune c LEFT JOIN commune m ON m.code_insee = c.commune_mere ORDER BY c.code_insee""")}
        self.ecoles = par(conn.execute(
            """SELECT e.*, d.nom AS qpv_nom, t.nom AS iris_nom, t.familles_avec_enfants, t.revenu_median,
                      t.taux_pauvrete, t.annee_familles, t.annee_revenus, t.provenances AS iris_provenances,
                      j.details
               FROM ecole e JOIN jauge_ecole j ON j.ecole_uai = e.uai
               LEFT JOIN territoire_social t ON t.iris = e.iris LEFT JOIN dispositif d ON d.id = e.qpv
               ORDER BY e.uai""").fetchall(), "commune")
        self._acteurs()
        self._collectivites()
        self._communes_v_i()

    def _acteurs(self) -> None:
        c = self.conn
        self.accueils = {r["id"]: r for r in c.execute(ACCUEILS)}
        self.liens_accueils = par(c.execute(
            "SELECT * FROM accueil_ecole ORDER BY ecole_uai, distance_m, accueil_id").fetchall(), "ecole_uai")
        self.assos = {r["id"]: r for r in c.execute(
            "SELECT *, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM asso_parents WHERE doublon_de IS NULL")}
        self.liens_assos = par(c.execute(
            "SELECT * FROM asso_ecole ORDER BY ecole_uai, confiance DESC, asso_id").fetchall(), "ecole_uai")
        self.gestionnaires = par(c.execute(
            """SELECT a.commune, g.siren, g.nom, g.type, count(*) AS n
               FROM accueil_periscolaire a JOIN gestionnaire_perisco g ON g.siren = a.gestionnaire_siren
               WHERE a.doublon_de IS NULL AND a.commune IS NOT NULL
               GROUP BY 1, 2, 3, 4 ORDER BY 1, n DESC, 3""").fetchall(), "commune")

    def _collectivites(self) -> None:
        c = self.conn
        self.elus = par(c.execute(
            """SELECT * FROM elu WHERE fonction LIKE 'Maire%' OR fonction ILIKE '%adjoint%' OR delegation IS NOT NULL
               ORDER BY commune, fonction NOT LIKE 'Maire%', delegation IS NULL,
                        coalesce(nullif(regexp_replace(fonction, '\\D', '', 'g'), '')::int, 99), nom, prenom"""
        ).fetchall(), "commune")
        self.signaux = par(c.execute(
            "SELECT * FROM signal_web ORDER BY commune, date_page DESC NULLS LAST, theme, url").fetchall(), "commune")
        self.visites = {r["objet_id"]: r for r in c.execute(
            "SELECT objet_id, statut, visite_le, pages_visitees FROM crawl_site WHERE objet_type = 'commune'")}
        # Périmètre déclaré ; pour un arrondissement, PAT de Paris et zones qui le recoupent vraiment.
        self.dispositifs = par(c.execute(
            """SELECT c.code_insee AS commune, d.id, d.type, d.nom, d.annee, d.niveau, d.niveau_num, d.echelon,
                      coalesce(d.axe_education_verifie, d.axe_education_alimentaire) AS axe_education_alimentaire,
                      d.axe_restauration_collective, d.priorites, d.score, d.editions,
                      d.source, d.url, d.collecte_le, d.confiance
               FROM commune c JOIN dispositif d ON CASE
                 WHEN c.commune_mere IS NULL THEN c.code_insee = ANY(d.communes)
                      OR c.code_insee = ANY(d.communes_ajoutees) OR d.id = ANY(c.cantine_pat)
                 WHEN d.type IN ('pat', 'laureat_aap') THEN c.commune_mere = ANY(d.communes)
                 ELSE c.commune_mere = ANY(d.communes) AND ST_Intersects(c.geom, d.geom)
                      AND ST_Area(ST_Intersection(c.geom, d.geom)) > 0.02 * ST_Area(d.geom) END
               ORDER BY c.code_insee, d.type, d.nom""").fetchall(), "commune")

    def _communes_v_i(self) -> None:
        """Étape « communes » : score propre, cuisine centrale, associations d'alimentation durable."""
        c = self.conn
        self.jauges_communes = {r["code_insee"]: r for r in c.execute(
            "SELECT code_insee, score, details, confiance FROM jauge_commune")}
        self.cuisines = {r["siret"]: r for r in c.execute(
            """SELECT k.*, m.nom AS commune_nom FROM cuisine_centrale k
               LEFT JOIN commune m ON m.code_insee = k.commune""")}
        self.assos_alimentation = par(c.execute(
            """SELECT *, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM asso_alimentation
               ORDER BY commune, categorie, derniere_declaration DESC NULLS LAST, nom""").fetchall(), "commune")

    def _proximites(self, codes: list[str]) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
        """Par école : producteurs [rang, km, minutes…] et relais [rang, km, minutes…], du plus proche au plus loin."""
        producteurs: dict[str, list[float]] = defaultdict(list)
        relais: dict[str, list[float]] = defaultdict(list)
        for r in self.conn.execute(
            """SELECT x.ecole_uai, x.cible_id, coalesce(x.km_route, x.km_vol_oiseau) AS km, x.minutes
               FROM proximite x JOIN ecole e ON e.uai = x.ecole_uai
               WHERE x.cible_type = 'producteur' AND e.commune = ANY(%s)
               ORDER BY x.ecole_uai, x.minutes NULLS LAST, x.cible_id""", (codes,)
        ):
            producteurs[r["ecole_uai"]] += [self.rang_producteur[r["cible_id"]], *_distance(r)]
        for r in self.conn.execute(
            """SELECT * FROM (
                 SELECT x.ecole_uai, x.cible_id, coalesce(x.km_route, x.km_vol_oiseau) AS km, x.minutes,
                        row_number() OVER (PARTITION BY x.ecole_uai, l.type ORDER BY x.minutes NULLS LAST, x.cible_id)
                          AS rang
                 FROM proximite x JOIN ecole e ON e.uai = x.ecole_uai JOIN relais_local l ON l.id = x.cible_id
                 WHERE x.cible_type = 'relais_local' AND e.commune = ANY(%s)
               ) t WHERE rang <= %s ORDER BY ecole_uai, minutes NULLS LAST, cible_id""", (codes, RELAIS_PAR_TYPE)
        ):
            relais[r["ecole_uai"]] += [self.rang_relais[r["cible_id"]], *_distance(r)]
        return producteurs, relais

    def composer(self, lot: int = 60) -> Iterator[tuple[str, dict[str, Any]]]:
        codes = list(self.communes)
        for i in range(0, len(codes), lot):
            producteurs, relais = self._proximites(codes[i : i + lot])
            for code in codes[i : i + lot]:
                yield code, self._fiche(code, producteurs, relais)

    def _fiche(
        self, code: str, producteurs: dict[str, list[float]], relais: dict[str, list[float]]
    ) -> dict[str, Any]:
        ecoles = self.ecoles[code]
        uais = [e["uai"] for e in ecoles]
        ids_accueils = {x["accueil_id"] for u in uais for x in self.liens_accueils[u]}
        ids_assos = {x["asso_id"] for u in uais for x in self.liens_assos[u]}
        return sans_vide({
            "commune": self._commune(code),
            "ecoles": {
                e["uai"]: self._ecole(e, producteurs[e["uai"]], relais[e["uai"]]) for e in ecoles
            },
            "accueils": {i: self._accueil(self.accueils[i]) for i in sorted(ids_accueils) if i in self.accueils},
            "assos": {i: self._asso(self.assos[i]) for i in sorted(ids_assos) if i in self.assos},
        })

    def _commune(self, code: str) -> dict[str, Any]:
        c = self.communes[code]
        visite = self.visites.get(code)
        return sans_vide({
            "code": code, "nom": c["nom"], "type": c["type"], "dep": c["departement"], "siren": c["siren"],
            "mere": {"code": c["commune_mere"], "nom": c["mere_nom"]} if c["commune_mere"] else None,
            "epci": c["epci_nom"], "ept": c["ept_nom"], "population": c["population"],
            "population_annee": c["population_annee"], "densite": c["densite"], "site": c["site_web"],
            "cantine": sans_vide({
                "gestion": c["cantine_gestion"], "nb": c["cantine_nb"], "declarations": c["cantine_nb_declarations"],
                "bio": c["cantine_pct_bio"], "egalim": c["cantine_pct_egalim"], "annee": c["cantine_annee"],
                "satellites": c["cantine_nb_satellites"], "sur_place": c["cantine_nb_sur_place"],
                "regie": c["cantine_part_regie"], "repas": c["cantine_repas_jour"],
                "centrale": self._cuisine(c["cuisine_centrale_siret"]),
            }) if c["cantine_nb"] else None,
            "contact": sans_vide({"tel": c["mairie_telephone"], "email": c["mairie_email"]}) or None,
            "score": self._score(code),
            "alimentation": self._alimentation(code),
            "nb": {k: c[f"nb_{k}"] for k in ("accueils", "assos", "relais", "producteurs", "elus")},
            "gestionnaires": [{"siren": g["siren"], "nom": g["nom"], "type": g["type"], "n": g["n"]}
                              for g in self.gestionnaires[code]],
            "dispositifs": [sans_vide({
                "id": d["id"], "type": d["type"], "nom": d["nom"], "axe": d["axe_education_alimentaire"],
                "restauration": d["axe_restauration_collective"], "annee": d["annee"], "niveau": d["niveau"],
                "echelon": d["echelon"], "score": d["score"], "editions": d["editions"], "priorites": d["priorites"],
                "p": prov(d),
            }) for d in self.dispositifs[code]],
            "elus": [sans_vide({
                "nom": f"{e['prenom']} {e['nom']}", "fonction": e["fonction"], "delegation": e["delegation"],
                "themes": e["delegation_themes"], "debut": e["debut_mandat"], "p": prov(e),
                "pd": prov_groupes(e["provenances"]).get("delegation"),
            }) for e in self.elus[code]],
            "signaux": [sans_vide({
                "theme": s["theme"], "titre": s["titre"], "date": s["date_page"], "type": s["type_page"], "p": prov(s),
            }) for s in self.signaux[code][:SIGNAUX_MAX]],
            "nb_signaux": len(self.signaux[code]),
            "visite": {"statut": visite["statut"], "date": visite["visite_le"].date()} if visite else None,
            "p": prov(c),
            "pg": prov_groupes(c["provenances"]),
        })

    def _cuisine(self, siret: str | None) -> dict[str, Any] | None:
        k = self.cuisines.get(siret or "")
        if k is None:
            return None
        return sans_vide({
            "siret": k["siret"], "nom": k["nom"], "type": k["type"], "commune": k["commune_nom"],
            "gestion": k["gestion"],
            "cantines": k["nb_cantines"], "repas": k["repas_jour"], "bio": k["pct_bio"], "egalim": k["pct_egalim"],
            "p": prov(k),
        })

    def _score(self, code: str) -> dict[str, Any] | None:
        j = self.jauges_communes.get(code)
        if j is None:
            return None
        return {"valeur": j["score"], "part": j["details"]["part_connue"], "criteres": [
            sans_vide({"code": c["code"], "valeur": c["valeur"], "detail": c["detail"]})
            for c in j["details"]["criteres"]]}

    def _alimentation(self, code: str) -> dict[str, Any] | None:
        assos = self.assos_alimentation[code]
        if not assos:
            return None
        categories: dict[str, int] = defaultdict(int)
        for a in assos:
            categories[a["categorie"]] += 1
        return {"n": len(assos), "categories": dict(categories), "assos": [sans_vide({
            "nom": a["nom"], "categorie": a["categorie"], "site": a["site_web"],
            "declaration": a["derniere_declaration"],
            "xy": _position(a), "p": prov(a),
        }) for a in assos[:ASSOS_ALIMENTATION_MAX]]}

    def _ecole(self, e: dict[str, Any], producteurs: list[float], relais: list[float]) -> dict[str, Any]:
        return sans_vide({
            "adresse": e["adresse"], "cp": e["code_postal"], "classes": e["nb_classes"],
            "contact": sans_vide({"tel": e["telephone"], "email": e["email"]}) or None,
            "rentree": e["effectifs_rentree"], "ips_rentree": e["ips_rentree"], "restauration": e["restauration"],
            "cite": e["cite_educative"],
            "iris": sans_vide({
                "nom": e["iris_nom"], "familles": e["familles_avec_enfants"], "revenu": e["revenu_median"],
                "pauvrete": e["taux_pauvrete"], "annee": e["annee_familles"], "annee_revenus": e["annee_revenus"],
                "pg": prov_groupes(e["iris_provenances"] or {}),
            }) if e["iris_nom"] else None,
            "qpv": {"nom": e["qpv_nom"], "m": e["qpv_distance_m"]} if e["qpv_nom"] else None,
            "jauges": {nom: {"part": j["part_connue"], "criteres": [
                sans_vide({"code": c["code"], "valeur": c["valeur"], "detail": c["detail"]}) for c in j["criteres"]
            ]} for nom, j in e["details"].items()},
            "accueils": [{"id": x["accueil_id"], "m": x["distance_m"], "motif": x["motif"], "c": x["confiance"]}
                         for x in self.liens_accueils[e["uai"]]],
            "assos": [{"id": x["asso_id"], "c": x["confiance"], "indices": x["indices"]}
                      for x in self.liens_assos[e["uai"]]],
            "prod": producteurs, "relais": relais,
            "p": prov(e), "pg": prov_groupes(e["provenances"]),
        })

    @staticmethod
    def _accueil(a: dict[str, Any]) -> dict[str, Any]:
        return sans_vide({
            "nom": a["nom"], "adresse": a["adresse"], "soir": a["accueil_soir"], "mercredi": a["accueil_mercredi"],
            "horaires": a["horaires"], "gestionnaire": a["gestionnaire"],
            "gestionnaire_type": a["gestionnaire_type"], "siren": a["siren"], "xy": _position(a),
            "p": prov(a),
        })

    @staticmethod
    def _asso(a: dict[str, Any]) -> dict[str, Any]:
        return sans_vide({
            "nom": a["nom"], "siege": a["siege"], "federation": a["federation"], "site": a["site_web"],
            "rna": a["rna"], "siren": a["siren"], "creation": a["date_creation"], "activite": a["derniere_activite"],
            "activite_url": a["derniere_activite_url"], "xy": _position(a), "p": prov(a),
            "pg": prov_groupes(a["provenances"]),
        })


def _position(r: dict[str, Any]) -> list[float] | None:
    return None if r["lon"] is None else [round(r["lon"], 5), round(r["lat"], 5)]


def _distance(r: dict[str, Any]) -> tuple[float, float | None]:
    return round(r["km"], 1), None if r["minutes"] is None else round(r["minutes"], 1)
