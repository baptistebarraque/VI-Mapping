"""Champs mesurés par le rapport de couverture, table par table.

Chaque table est une requête qui donne `cle` (identifiant), `dep` (département) et les colonnes citées par les champs.
Une ligne qui touche plusieurs départements y est comptée une fois dans chacun, et une seule fois au total régional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Nature = Literal["rempli", "part"]


@dataclass(frozen=True)
class Champ:
    code: str
    libelle: str
    rempli: str  # expression SQL booléenne
    nature: Nature = "rempli"  # « part » : une valeur absente veut dire « non », pas « inconnu »
    cause: str | None = None  # pourquoi le champ reste incomplet
    parmi: str | None = None  # lignes concernées par le champ (expression SQL) ; toutes par défaut


@dataclass(frozen=True)
class Table:
    nom: str
    libelle: str
    source: str
    champs: tuple[Champ, ...]


def present(code: str, libelle: str, cause: str | None = None, parmi: str | None = None) -> Champ:
    return Champ(code, libelle, f"{code} IS NOT NULL", "rempli", cause, parmi)


def part(code: str, libelle: str, rempli: str, cause: str | None = None) -> Champ:
    return Champ(code, libelle, rempli, "part", cause)


CAMPAGNE = "dépend de l'avancée de la visite des sites de mairies"
MA_CANTINE = "déclaration propre à chaque gestionnaire sur « ma cantine », pas toujours faite"
MONENFANT = "monenfant.fr verrouillée ; restent OSM, Sirene, l'API Recherche d'entreprises et les sites de mairies"
FILOSOFI = "Filosofi : IRIS assez peuplés, communes de plus de 5 000 habitants"

# Commune d'un objet → département ; les objets sans commune connue n'ont pas de département et sont hors tableau.
_AVEC_COMMUNE = """SELECT x.*, c.departement AS dep, x.{cle}::text AS cle
        FROM {table} x JOIN commune c ON c.code_insee = x.commune"""

TABLES: tuple[Table, ...] = (
    Table("commune", "Communes et arrondissements", """
        SELECT c.*, c.departement AS dep, c.code_insee AS cle,
               coalesce(c.cantine_pct_bio, m.cantine_pct_bio) AS bio,
               coalesce(c.cantine_pct_egalim, m.cantine_pct_egalim) AS egalim,
               EXISTS (SELECT 1 FROM crawl_site s WHERE s.objet_type = 'commune' AND s.objet_id = c.code_insee
                         AND s.statut = 'ok') AS visitee
        FROM commune c LEFT JOIN commune m ON m.code_insee = c.commune_mere""", (
        present("siren", "Siren", parmi="type <> 'arrondissement'"),
        present("epci_siren", "EPCI", parmi="type <> 'arrondissement'"),
        present("population", "Population"),
        present("densite", "Densité"),
        present("site_web", "Site web de la mairie"),
        present("cantine_gestion", "Cantine : régie ou concédée", MA_CANTINE),
        present("bio", "Cantine : % bio", MA_CANTINE),
        present("egalim", "Cantine : % EGalim", MA_CANTINE),
        part("visitee", "Site de la mairie visité", "visitee", CAMPAGNE),
    )),
    Table("ecole", "Écoles", "SELECT e.*, e.departement AS dep, e.uai AS cle FROM ecole e", (
        present("nom", "Nom"),
        present("adresse", "Adresse"),
        present("geom", "Position"),
        present("nb_eleves", "Nombre d'élèves"),
        present("nb_classes", "Nombre de classes"),
        present("ips", "IPS (hors maternelles)", "calculé sur les élèves de CM2 : écoles qui n'en ont pas exclues",
                "type <> 'maternelle'"),
        present("restauration", "Restauration"),
        present("iris", "Quartier IRIS"),
        part("education_prioritaire", "REP ou REP+", "education_prioritaire IS NOT NULL"),
        part("cite_educative", "Cité éducative", "cite_educative IS NOT NULL"),
        part("qpv", "QPV à moins de 2 km", "qpv IS NOT NULL"),
    )),
    Table("accueil_periscolaire", "Accueils périscolaires",
          _AVEC_COMMUNE.format(table="accueil_periscolaire", cle="id") + " WHERE x.doublon_de IS NULL", (
        present("adresse", "Adresse"),
        present("geom", "Position"),
        present("accueil_soir", "Accueil du soir", MONENFANT),
        present("accueil_mercredi", "Accueil du mercredi", MONENFANT),
        present("horaires", "Horaires", MONENFANT),
        Champ("gestionnaire", "Gestionnaire", "gestionnaire_siren IS NOT NULL OR exploitant IS NOT NULL", "rempli",
              MONENFANT),
        part("rattache", "Rattaché à une école",
             "EXISTS (SELECT 1 FROM accueil_ecole l WHERE l.accueil_id = t.cle)"),
    )),
    Table("gestionnaire_perisco", "Gestionnaires périscolaires", """
        SELECT DISTINCT g.*, c.departement AS dep, g.siren AS cle FROM gestionnaire_perisco g
        JOIN accueil_periscolaire a ON a.gestionnaire_siren = g.siren JOIN commune c ON c.code_insee = a.commune""", (
        present("siren", "Siren"),
        present("nom", "Nom"),
        present("type", "Type"),
        Champ("nb_accueils", "Nombre d'accueils", "nb_accueils > 0"),
    )),
    Table("asso_parents", "Associations de parents d'élèves (1er degré)",
          _AVEC_COMMUNE.format(table="asso_parents", cle="id")
          + " WHERE x.doublon_de IS NULL AND x.niveau <> 'second_degre'", (
        present("rna", "Numéro RNA", "les conseils locaux FCPE non déclarés en propre n'en ont pas"),
        present("siren", "Siren", "attribué seulement aux associations qui en ont demandé un"),
        present("siege", "Siège"),
        present("geom", "Position du siège"),
        part("federation", "Fédération reconnue", "federation IS NOT NULL",
             "nom ou objet ; fcpe75.org et le site national de la PEEP sont verrouillés"),
        present("date_creation", "Date de création"),
        present("site_web", "Site web", "rarement déclaré au RNA"),
        present("derniere_activite", "Dernière activité en ligne",
                "site web connu et visitable, hors réseaux sociaux"),
        part("ecole_uai", "Rattachée à une école", "ecole_uai IS NOT NULL",
             "nom générique sans école ni adresse exploitable"),
    )),
    Table("territoire_social", "Quartiers IRIS", _AVEC_COMMUNE.format(table="territoire_social", cle="iris"), (
        present("familles_avec_enfants", "Familles avec enfants"),
        present("revenu_median", "Revenu médian", FILOSOFI),
        present("taux_pauvrete", "Taux de pauvreté", FILOSOFI),
        part("qpv", "Touché par un QPV", "qpv <> '{}'"),
    )),
    Table("relais_local", "Relais locaux",
          _AVEC_COMMUNE.format(table="relais_local", cle="id") + " WHERE x.doublon_de IS NULL", (
        present("type", "Type"),
        present("nom", "Nom"),
        present("adresse", "Adresse", "souvent absente d'OpenStreetMap"),
        present("geom", "Position"),
        present("site_web", "Site web", "rarement renseigné dans OSM et le RNA"),
    )),
    Table("elu", "Élus municipaux", _AVEC_COMMUNE.format(table="elu", cle="id"), (
        present("nom", "Nom"),
        present("fonction", "Fonction"),
        present("delegation", "Délégation des adjoints", CAMPAGNE, "fonction ILIKE '%adjoint%'"),
        present("debut_mandat", "Début de mandat"),
    )),
    Table("signal_web", "Signaux des sites de mairies", _AVEC_COMMUNE.format(table="signal_web", cle="id"), (
        present("url", "Adresse de la page"),
        present("theme", "Thème"),
        present("type_page", "Type de page"),
        present("titre", "Titre"),
        present("date_page", "Date", "page ou document sans date affichée"),
    )),
    Table("dispositif", "Dispositifs", """
        SELECT DISTINCT d.*, c.departement AS dep, d.id AS cle
        FROM dispositif d JOIN commune c ON c.code_insee = ANY(d.communes)""", (
        present("type", "Type"),
        Champ("communes", "Périmètre", "communes <> '{}'"),
        present("geom", "Contour"),
        present("annee", "Année"),
        present("axe_education_alimentaire", "Volet éducation alimentaire (PAT)", parmi="type = 'pat'"),
    )),
    Table("producteur", "Producteurs bio", _AVEC_COMMUNE.format(table="producteur", cle="id"), (
        present("siret", "Siret"),
        present("numero_bio", "Numéro bio"),
        Champ("activites", "Activités", "activites <> '{}'"),
        present("vente_directe", "Vente directe"),
        present("membre_amap", "Membre d'une AMAP",
                "absent de l'API ; carte du Réseau AMAP IdF verrouillée"),
        Champ("lieu", "Adresse du lieu d'activité", "adresse_type <> 'siege'", "rempli",
              "seul le siège est connu : producteur affiché, non compté dans la jauge"),
        part("eligible", "Pris en compte (critères de la jauge)", "eligible"),
    )),
    Table("proximite", "Paires école-cible à moins de 50 km", """
        SELECT x.km_route, x.minutes, e.departement AS dep, x.ecole_uai || x.cible_type || x.cible_id AS cle
        FROM proximite x JOIN ecole e ON e.uai = x.ecole_uai""", (
        present("km_route", "Distance par la route"),
        present("minutes", "Temps de trajet"),
    )),
    Table("jauge_ecole", "Jauges des écoles", """
        SELECT j.*, e.departement AS dep, e.uai AS cle,
               EXISTS (SELECT 1 FROM accueil_ecole l WHERE l.ecole_uai = e.uai) AS avec_accueil,
               EXISTS (SELECT 1 FROM asso_ecole l WHERE l.ecole_uai = e.uai) AS avec_asso,
               (j.engagement IS NOT NULL)::int + (j.periscolaire IS NOT NULL)::int + (j.parents IS NOT NULL)::int
                 + (j.producteurs IS NOT NULL)::int + (j.familles IS NOT NULL)::int AS connues
        FROM ecole e JOIN jauge_ecole j ON j.ecole_uai = e.uai""", (
        present("engagement", "Engagement de la collectivité"),
        present("periscolaire", "Périscolaire", MONENFANT),
        present("parents", "Parents", "associations déclarées et rattachées seulement"),
        present("producteurs", "Producteurs"),
        present("familles", "Familles"),
        present("score", "Score global"),
        part("connues", "Les cinq jauges connues", "connues = 5"),
        part("avec_accueil", "École avec au moins un accueil", "avec_accueil", MONENFANT),
        part("avec_asso", "École avec au moins une association", "avec_asso"),
    )),
)
