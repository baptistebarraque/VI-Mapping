"""Calcul des cinq jauges et du score de chaque école, puis du score propre de chaque commune, à partir de la base."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import psycopg

from ..config import ConfigJauges, config_jauges
from ..db import upsert
from ..outils.texte import normaliser
from ..sources.base import Compteurs, Contexte, connecteur
from . import formules
from .formules import Accueil, AssoLiee, Jauge, PatCommune


def il_y_a(mois: int, jour: date) -> date:
    """Date `mois` mois avant `jour` (fin de mois ramenée au 28)."""
    total = jour.year * 12 + jour.month - 1 - mois
    return date(total // 12, total % 12 + 1, min(jour.day, 28))


def distances_producteurs(
    conn: psycopg.Connection[Any], cfg: ConfigJauges
) -> dict[str, list[tuple[float | None, float | None]]]:
    """(km, minutes) des producteurs utiles à la jauge de chaque école.

    Les 5 plus proches en km et les 5 plus proches en minutes suffisent, quel que soit le rayon : le nombre est
    plafonné à 5 et seul le plus proche compte ensuite.
    """
    n = cfg.producteurs.nombre_plein
    resultat: dict[str, list[tuple[float | None, float | None]]] = defaultdict(list)
    for r in conn.execute(
        """SELECT ecole_uai, km, minutes FROM (
             SELECT ecole_uai, coalesce(km_route, km_vol_oiseau) AS km, minutes,
                    row_number() OVER (PARTITION BY ecole_uai
                                       ORDER BY coalesce(km_route, km_vol_oiseau), cible_id) AS rang_km,
                    row_number() OVER (PARTITION BY ecole_uai ORDER BY minutes NULLS LAST, cible_id) AS rang_min
             FROM proximite x JOIN producteur p ON p.id = x.cible_id
             WHERE cible_type = 'producteur' AND p.adresse_type = ANY(%s)
           ) t WHERE rang_km <= %s OR rang_min <= %s""", (list(cfg.producteurs.adresses), n, n),
    ):
        resultat[r["ecole_uai"]].append((r["km"], r["minutes"]))
    return resultat


class Donnees:
    """Tout ce dont les jauges ont besoin, chargé une fois."""

    def __init__(self, ctx: Contexte, cfg: ConfigJauges) -> None:
        self.ctx, self.cfg = ctx, cfg
        jour = ctx.debut.date()
        conn = ctx.conn
        self.communes = {
            r["code_insee"]: r for r in conn.execute(
                """SELECT code_insee, commune_mere, site_web, cantine_pct_bio, cantine_annee, cantine_pat, population,
                          departement, cantine_nb_satellites, cantine_nb_sur_place, cantine_part_regie,
                          cuisine_centrale_siret FROM commune""")
        }
        self._pat()
        self._territoires()
        self._web(jour)
        self._accueils()
        self._assos(jour)
        self._producteurs()
        self._ips_voisins()

    def _pat(self) -> None:
        """PAT de chaque commune : périmètre France PAT, communes ajoutées (DRIAAF) et PAT déclarés dans ma cantine.

        L'axe éducation alimentaire lu dans la fiche DRIAAF prime sur le repérage par mot-clé.
        """
        par_id: dict[str, PatCommune] = {}
        self.pats: dict[str, dict[str, PatCommune]] = defaultdict(dict)
        for r in self.ctx.conn.execute(
            """SELECT id, nom, communes, communes_ajoutees, niveau_num, axe_restauration_collective AS restauration,
                      coalesce(axe_education_verifie, axe_education_alimentaire) AS education
               FROM dispositif WHERE type = 'pat'"""
        ):
            pat = par_id[r["id"]] = PatCommune(r["nom"], r["niveau_num"], r["restauration"], r["education"])
            for c in {*r["communes"], *r["communes_ajoutees"]}:
                self.pats[c][r["id"]] = pat
        for code, c in self.communes.items():
            for id_ in c["cantine_pat"]:
                if id_ in par_id:
                    self.pats[code][id_] = par_id[id_]

    def pats_de(self, code: str) -> list[PatCommune]:
        """PAT de la commune, et ceux de la commune mère pour un arrondissement de Paris."""
        mere = self.communes[code]["commune_mere"]
        return list({**self.pats[code], **(self.pats[mere] if mere else {})}.values())

    def _territoires(self) -> None:
        """Soutiens (référentiel), cuisines centrales, associations d'alimentation et élèves par commune."""
        conn = self.ctx.conn
        self.soutien: dict[tuple[str, str], int] = {}
        self.aap_mgp: set[str] = set()
        self.syndicat: set[str] = set()
        for r in conn.execute(
            "SELECT type, echelon, score, communes FROM dispositif "
            "WHERE type IN ('soutien_territorial', 'laureat_aap_mgp', 'syndicat_restauration')"
        ):
            for c in r["communes"]:
                if r["type"] == "laureat_aap_mgp":
                    self.aap_mgp.add(c)
                elif r["type"] == "syndicat_restauration":
                    self.syndicat.add(c)
                elif r["score"] is not None:
                    cle = (c, r["echelon"])
                    self.soutien[cle] = max(self.soutien.get(cle, 0), r["score"])
        self.cuisines = {r["siret"]: r["type"] for r in conn.execute("SELECT siret, type FROM cuisine_centrale")}
        self.assos_alim = {r["commune"]: r["n"] for r in conn.execute(
            "SELECT commune, count(*) AS n FROM asso_alimentation GROUP BY commune")}
        self.eleves = {r["commune"]: r["n"] for r in conn.execute(
            "SELECT commune, sum(nb_eleves) AS n FROM ecole GROUP BY commune HAVING sum(nb_eleves) IS NOT NULL")}

    # -- sites des mairies : signaux partagés entre communes d'un même site, puis commune mère (Paris)
    def _web(self, jour: date) -> None:
        depuis = il_y_a(self.cfg.engagement.web.fenetre_mois, jour)
        par_site: dict[str, set[str]] = defaultdict(set)
        for code, c in self.communes.items():
            if c["site_web"]:
                par_site[c["site_web"]].add(code)
        visites = {
            r["objet_id"] for r in self.ctx.conn.execute(
                "SELECT objet_id FROM crawl_site WHERE objet_type = 'commune' AND statut = 'ok'")
        }
        recents: dict[str, set[str]] = defaultdict(set)
        sans_date: dict[str, set[str]] = defaultdict(set)
        for r in self.ctx.conn.execute("SELECT commune, theme, date_page FROM signal_web"):
            if r["date_page"] is None:
                sans_date[r["commune"]].add(r["theme"])
            elif r["date_page"] >= depuis:
                recents[r["commune"]].add(r["theme"])
        self.web: dict[str, tuple[set[str], set[str]] | None] = {}
        for code, c in self.communes.items():
            origines = {code} | (par_site[c["site_web"]] if c["site_web"] else set())
            if c["commune_mere"]:
                origines.add(c["commune_mere"])
            if not origines & visites:
                self.web[code] = None
                continue
            self.web[code] = (
                set().union(*(recents[o] for o in origines)), set().union(*(sans_date[o] for o in origines)),
            )

    def _accueils(self) -> None:
        self.accueils: dict[str, list[Accueil]] = defaultdict(list)
        for r in self.ctx.conn.execute(
            """SELECT l.ecole_uai, a.nom, a.accueil_soir, a.accueil_mercredi,
                      a.gestionnaire_siren IS NOT NULL OR a.exploitant IS NOT NULL AS gestionnaire
               FROM accueil_ecole l JOIN accueil_periscolaire a ON a.id = l.accueil_id
               WHERE l.distance_m <= %s OR l.motif = 'adresse'""",
            (self.cfg.periscolaire.distance_max_m,),
        ):
            n = normaliser(r["nom"])
            self.accueils[r["ecole_uai"]].append(Accueil(
                r["accueil_soir"], r["accueil_mercredi"], r["gestionnaire"], "loisir" in n or "alsh" in n))

    def _assos(self, jour: date) -> None:
        depuis = il_y_a(self.cfg.parents.fenetre_activite_mois, jour)
        self.assos: dict[str, list[AssoLiee]] = defaultdict(list)
        for r in self.ctx.conn.execute(
            """SELECT l.ecole_uai, l.confiance, a.federation, a.derniere_activite
               FROM asso_ecole l JOIN asso_parents a ON a.id = l.asso_id"""
        ):
            activite = r["derniere_activite"]
            self.assos[r["ecole_uai"]].append(AssoLiee(
                float(r["confiance"]), r["federation"], None if activite is None else activite >= depuis))

    def _producteurs(self) -> None:
        self.producteurs = distances_producteurs(self.ctx.conn, self.cfg)
        calcule = self.ctx.conn.execute("SELECT EXISTS (SELECT 1 FROM proximite) AS oui").fetchone()
        self.proximite_calculee = bool(calcule and calcule["oui"])

    def _ips_voisins(self) -> None:
        """Écoles sans IPS publié (maternelles) : IPS de l'école élémentaire voisine du même secteur."""
        self.ips_voisin = {
            r["uai"]: (float(r["ips"]), r["nom"]) for r in self.ctx.conn.execute(
                """SELECT DISTINCT ON (s.uai) s.uai, v.ips, v.nom
                   FROM ecole s
                   JOIN ecole v ON v.ips IS NOT NULL AND v.secteur = s.secteur AND v.uai <> s.uai
                        AND ST_DWithin(s.geom_l93, v.geom_l93, %s)
                   WHERE s.ips IS NULL
                   ORDER BY s.uai, ST_Distance(s.geom_l93, v.geom_l93), v.uai""",
                (self.cfg.familles.mixite.ips_voisin_max_m,),
            )
        }

    # -- jauges d'une école
    def jauges(self, e: dict[str, Any]) -> dict[str, Jauge]:
        cfg = self.cfg
        commune = self.communes[e["commune"]]
        mere = self.communes.get(commune["commune_mere"] or "")
        pats = [(bool(p.education), p.nom) for p in self.pats_de(e["commune"])]
        pat, pat_nom = "aucun", None
        if pats:
            axe, pat_nom = max(pats)
            pat = "avec_axe_education" if axe else "sans_axe_education"
        cantine = commune if commune["cantine_pct_bio"] is not None else mere or commune
        web = self.web[e["commune"]]
        alimentaires = set(cfg.engagement.web.themes)
        ips, origine = (float(e["ips"]), "ecole") if e["ips"] is not None else (None, None)
        if ips is None and e["uai"] in self.ips_voisin:
            ips, origine = self.ips_voisin[e["uai"]]
        tous = (web[0] | web[1]) if web else set()
        return {
            "engagement": formules.engagement(
                cfg, pat=pat, pat_nom=pat_nom,
                pct_bio=None if cantine["cantine_pct_bio"] is None else float(cantine["cantine_pct_bio"]),
                annee_bio=cantine["cantine_annee"],
                themes=None if web is None else sorted(web[0] & alimentaires),
                themes_sans_date=() if web is None else sorted((web[1] - web[0]) & alimentaires),
                cite=e["cite_educative"],
            ),
            "periscolaire": formules.periscolaire(
                cfg, self.accueils[e["uai"]],
                soir_commune=e["secteur"] == "public" and "periscolaire_soir" in tous,
                mercredi_commune=e["secteur"] == "public" and "periscolaire_mercredi" in tous,
            ),
            "parents": formules.parents(cfg, self.assos[e["uai"]]),
            "producteurs": formules.producteurs(
                cfg, self.producteurs[e["uai"]] if e["localisee"] and self.proximite_calculee else None),
            "familles": formules.familles(
                cfg, nb_eleves=e["nb_eleves"], familles_iris=e["familles_avec_enfants"], ips=ips, ips_origine=origine,
                qpv_distance_m=e["qpv_distance_m"],
            ),
        }


    # -- score propre d'une commune
    def jauge_commune(self, code: str, producteurs_ecoles: list[float | None]) -> Jauge:
        cfg = self.cfg
        c = self.communes[code]
        mere = self.communes.get(c["commune_mere"] or "")
        cantine = c if c["cantine_pct_bio"] is not None or mere is None else mere
        pat, pat_nom = formules.commune_pat(cfg, self.pats_de(code))
        heritier = mere["code_insee"] if mere else code
        soutiens = formules.commune_soutiens(
            cfg, departement=self.soutien.get((code, "departement")),
            interco=self.soutien.get((code, "interco"), self.soutien.get((heritier, "interco"))),
            aap_mgp=code in self.aap_mgp)
        cuisine, origine = formules.commune_cuisine(
            cfg, type_centrale=self.cuisines.get(c["cuisine_centrale_siret"] or ""),
            satellites=c["cantine_nb_satellites"], sur_place=c["cantine_nb_sur_place"],
            part_regie=None if c["cantine_part_regie"] is None else float(c["cantine_part_regie"]),
            syndicat=code in self.syndicat)
        bio = None if cantine["cantine_pct_bio"] is None else float(cantine["cantine_pct_bio"])
        web = self.web[code]
        alimentaires = set(cfg.engagement.web.themes)
        nb_assos = self.assos_alim.get(code, 0)
        eleves = self.eleves.get(code)
        valeurs = {
            "pat": pat,
            "soutiens": soutiens,
            "cuisine": cuisine,
            "cantine_bio": None if bio is None else formules.borne(100 * bio / cfg.engagement.bio.pct_plein),
            "producteurs": formules.commune_producteurs(producteurs_ecoles),
            "associations": formules.commune_associations(cfg, nb_assos, c["population"]),
            "communications": None if web is None else formules.commune_communications(
                cfg, sorted(web[0] & alimentaires), sorted((web[1] - web[0]) & alimentaires)),
            "ecoles": None if eleves is None else formules.borne(100 * eleves / cfg.communes.ecoles.eleves_plein),
        }
        details = {
            "pat": pat_nom, "cuisine": origine, "cantine_bio": bio, "associations": nb_assos, "ecoles": eleves,
            "producteurs": sum(v is not None for v in producteurs_ecoles) or None,
            "communications": None if web is None else sorted(web[0] & alimentaires),
            "soutiens": {"departement": self.soutien.get((code, "departement")), "aap_mgp": code in self.aap_mgp},
        }
        return formules.commune(cfg, valeurs, details)


@connecteur("jauges", calcul=True)
def calculer(ctx: Contexte) -> Compteurs:
    cfg = config_jauges()
    donnees = Donnees(ctx, cfg)
    empreinte = cfg.empreinte()
    lignes: list[dict[str, Any]] = []
    compte: Compteurs = dict.fromkeys((*cfg.poids, "score"), 0)
    producteurs_par_commune: dict[str, list[float | None]] = defaultdict(list)
    for e in ctx.conn.execute(
        """SELECT e.uai, e.commune, e.secteur, e.nb_eleves, e.ips, e.cite_educative, e.qpv_distance_m,
                  e.geom IS NOT NULL AS localisee, t.familles_avec_enfants
           FROM ecole e LEFT JOIN territoire_social t ON t.iris = e.iris ORDER BY e.uai"""
    ).fetchall():
        jauges = donnees.jauges(e)
        valeurs = {nom: j.valeur for nom, j in jauges.items()}
        producteurs_par_commune[e["commune"]].append(valeurs["producteurs"])
        global_ = formules.score(cfg, valeurs)
        part = sum(cfg.poids[n] * j.part_connue for n, j in jauges.items()) / sum(cfg.poids.values())  # type: ignore[index]
        for nom, v in {**valeurs, "score": global_.valeur}.items():
            compte[nom] += v is not None
        lignes.append({
            "ecole_uai": e["uai"],
            **valeurs,
            "score": global_.valeur,
            "details": {nom: j.en_json() for nom, j in jauges.items()},
            "config_hash": empreinte,
            **ctx.provenance(confiance=min(part, 1.0)),
        })
    upsert(ctx.conn, "jauge_ecole", lignes, ["ecole_uai"])
    ctx.conn.execute("DELETE FROM jauge_ecole WHERE collecte_le < %s", (ctx.debut,))
    communes = []
    for code in donnees.communes:
        j = donnees.jauge_commune(code, producteurs_par_commune[code])
        communes.append({
            "code_insee": code, "score": j.valeur, "details": j.en_json(), "config_hash": empreinte,
            **ctx.provenance(confiance=min(j.part_connue, 1.0)),
        })
    upsert(ctx.conn, "jauge_commune", communes, ["code_insee"])
    ctx.conn.execute("DELETE FROM jauge_commune WHERE collecte_le < %s", (ctx.debut,))
    return {"ecoles": len(lignes), **{f"avec_{k}": v for k, v in compte.items()}, "communes": len(communes),
            "communes_avec_score": sum(c["score"] is not None for c in communes)}
