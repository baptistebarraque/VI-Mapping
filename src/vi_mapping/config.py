"""Chargement et validation de la configuration (config/*.yaml + variables d'environnement)."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_CONFIG = RACINE / "config"
DOSSIER_SQL = RACINE / "sql"

Part = Annotated[float, Field(ge=0, le=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- idf.yaml
class Region(_Strict):
    code: str
    nom: str
    departements: dict[str, str]
    bbox: tuple[float, float, float, float]


class Ecoles(_Strict):
    contrats_prives: list[str]


class Producteurs(_Strict):
    etats_bio: list[str]
    etats_conversion: list[str]
    certifications_actives: list[str]
    prefixes_maraichage: list[str]
    prefixes_fruits: list[str]
    activites_maraichage: list[str]
    activites_fruits: list[str]
    activites_exclues: list[str]
    categories_vente_directe: list[str]
    confiance_adresse: dict[Literal["lieu_activite", "lieu_vente", "siege"], Part]


class RattachementAccueil(_Strict):
    distance_max_m: int
    similarite_nom_min: Part
    distance_max_nom_m: int
    confiance: dict[Literal["adresse", "distance", "nom"], Part]


class PoidsAsso(_Strict):
    nom_ecole: Part
    commune: Part
    proximite: Part
    ecole_unique: Part


class RattachementAsso(_Strict):
    confiance_min: Part
    distance_max_m: int
    poids: PoidsAsso
    distance_pleine_m: int
    distance_nulle_m: int
    ecoles_max_par_asso: int


class Rattachements(_Strict):
    accueil_ecole: RattachementAccueil
    asso_ecole: RattachementAsso
    qpv_distance_max_m: int


class Proximite(_Strict):
    km_vol_oiseau_max: float
    cibles: list[Literal["producteur", "relais_local"]]
    moteur: Literal["osrm"]
    profil: Literal["car"]
    facteur_duree: Annotated[float, Field(gt=0)]
    osm_url: str
    lot_ecoles: int


class Http(_Strict):
    nom_robot: str
    version: str
    timeout_s: float
    tentatives: int
    delai_min_s: float


class Scraping(_Strict):
    delai_s: float
    pages_max_par_site: int
    sites_en_parallele: int
    octets_max: int
    timeout_s: float
    echantillon_sans_contact: int


class ConfigIdf(_Strict):
    region: Region
    ecoles: Ecoles
    producteurs: Producteurs
    rattachements: Rattachements
    proximite: Proximite
    http: Http
    scraping: Scraping

    @property
    def departements(self) -> list[str]:
        return list(self.region.departements)


# --------------------------------------------------------------------------- sources.yaml
class Verification(_Strict):
    le: date
    constat: str
    robots: str | None = None
    cgu_url: str | None = None
    anti_robot: str | None = None
    remplacement: list[str] = []
    demarche: str | None = None


class Autorisation(_Strict):
    date: date
    reference: str


class SourceConfig(_Strict):
    libelle: str
    alimente: str  # tables et champs remplis
    producteur: str
    url: str
    licence: str
    methode: Literal["api", "csv", "scraping", "calcul"]
    frequence: Literal["mensuelle", "annuelle"]
    statut: Literal["ouverte", "verrouillee"]
    confiance: Part
    hotes: list[str] = []  # domaines couverts, refusés par tous les scrapers si la source est verrouillée
    verification: Verification | None = None
    autorisation: Autorisation | None = None

    @property
    def verrouillee(self) -> bool:
        return self.statut == "verrouillee" and self.autorisation is None

    @model_validator(mode="after")
    def _verrou_justifie(self) -> SourceConfig:
        if self.statut == "verrouillee" and self.verification is None:
            raise ValueError("une source verrouillée doit documenter sa vérification")
        return self


# --------------------------------------------------------------------------- jauges.yaml
NOMS_JAUGES = ("engagement", "periscolaire", "parents", "producteurs", "familles")


def _somme_100(poids: dict[str, float], ou: str) -> None:
    if abs(sum(poids.values()) - 100) > 1e-6:
        raise ValueError(f"{ou} : la somme des poids doit valoir 100 (ici {sum(poids.values()):g})")


class DonneesInsuffisantes(_Strict):
    part_min_connue_jauge: Part
    part_min_connue_score: Part


class Rayon(_Strict):
    km: float
    minutes: float
    mode: Literal["ou", "km", "minutes"]


class _Jauge(_Strict):
    sous_poids: dict[str, float]

    @model_validator(mode="after")
    def _verifie(self) -> _Jauge:
        _somme_100(self.sous_poids, type(self).__name__)
        return self


class BaremePat(_Strict):
    avec_axe_education: float
    sans_axe_education: float
    aucun: float


class BaremeBio(_Strict):
    pct_plein: float


class BaremeWeb(_Strict):
    fenetre_mois: int
    themes_plein: int
    poids_sans_date: Part
    themes: list[str]


class JaugeEngagement(_Jauge):
    pat: BaremePat
    bio: BaremeBio
    web: BaremeWeb


class BaremeSoir(_Strict):
    oui: float
    accueil_sans_horaire: float
    oui_commune: float


class BaremeMercredi(_Strict):
    oui: float
    centre_de_loisirs: float
    oui_commune: float


class BaremeGestionnaire(_Strict):
    identifie: float
    non_identifie: float


class JaugePeriscolaire(_Jauge):
    distance_max_m: int
    soir: BaremeSoir
    mercredi: BaremeMercredi
    gestionnaire: BaremeGestionnaire
    source_exhaustive: bool


class JaugeParents(_Jauge):
    confiance_min: Part
    fenetre_activite_mois: int
    source_exhaustive: bool


class JaugeProducteurs(_Jauge):
    adresses: list[Literal["lieu_activite", "lieu_vente", "siege"]]
    minutes_plein: float
    km_plein: float
    nombre_plein: int


class BaremeMixite(_Strict):
    ips_reference: float
    ips_amplitude: float
    ips_voisin_max_m: int
    part_ips: float
    part_qpv: float
    qpv_distance_max_m: int


class JaugeFamilles(_Jauge):
    nb_eleves_plein: int
    familles_iris_plein: int
    mixite: BaremeMixite


class BaremePatCommune(_Strict):
    part_niveau: float
    part_restauration: float
    part_education: float
    niveau_inconnu: Annotated[int, Field(ge=0, le=2)]


class BaremeSoutiens(_Strict):
    part_departement: float
    part_interco: float
    part_aap_mgp: float


class BaremeCuisine(_Strict):
    municipale: float
    caisse_des_ecoles: float
    sur_place_regie: float
    intercommunale: float
    autre_public: float
    sur_place_concedee: float
    privee: float


class BaremeAssociations(_Strict):
    nombre_plein: int
    densite_plein_10k: float


class BaremeEcolesCommune(_Strict):
    eleves_plein: int


CRITERES_COMMUNES = (
    "pat", "soutiens", "cuisine", "cantine_bio", "producteurs", "associations", "communications", "ecoles",
)


class JaugeCommunes(_Jauge):
    pat: BaremePatCommune
    soutiens: BaremeSoutiens
    cuisine: BaremeCuisine
    associations: BaremeAssociations
    ecoles: BaremeEcolesCommune

    @model_validator(mode="after")
    def _criteres(self) -> JaugeCommunes:
        if set(self.sous_poids) != set(CRITERES_COMMUNES):
            raise ValueError(f"communes.sous_poids : il faut exactement {CRITERES_COMMUNES}")
        return self


class ConfigJauges(_Strict):
    poids: dict[Literal["engagement", "periscolaire", "parents", "producteurs", "familles"], float]
    donnees_insuffisantes: DonneesInsuffisantes
    rayon: Rayon
    engagement: JaugeEngagement
    periscolaire: JaugePeriscolaire
    parents: JaugeParents
    producteurs: JaugeProducteurs
    familles: JaugeFamilles
    communes: JaugeCommunes

    @model_validator(mode="after")
    def _verifie(self) -> ConfigJauges:
        if set(self.poids) != set(NOMS_JAUGES):
            raise ValueError(f"poids : il faut exactement {NOMS_JAUGES}")
        _somme_100(self.poids, "poids")
        return self

    def empreinte(self) -> str:
        """Identifie la configuration qui a produit un calcul."""
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()[:12]


# --------------------------------------------------------------------------- accès
def _yaml(nom: str) -> Any:
    return yaml.safe_load((DOSSIER_CONFIG / nom).read_text(encoding="utf-8"))


@lru_cache
def config_idf() -> ConfigIdf:
    return ConfigIdf.model_validate(_yaml("idf.yaml"))


@lru_cache
def config_sources() -> dict[str, SourceConfig]:
    return {code: SourceConfig.model_validate(s) for code, s in _yaml("sources.yaml")["sources"].items()}


@lru_cache
def hotes_verrouilles() -> frozenset[str]:
    """Domaines qu'aucun scraper ne doit visiter (CGU), sous-domaines compris."""
    return frozenset(h for s in config_sources().values() if s.verrouillee for h in s.hotes)


@lru_cache
def config_jauges() -> ConfigJauges:
    return ConfigJauges.model_validate(_yaml("jauges.yaml"))


def _charge_env() -> None:
    """Lit .env à la racine sans écraser l'environnement (format CLE=valeur, commentaires #)."""
    fichier = RACINE / ".env"
    if not fichier.exists():
        return
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, _, valeur = ligne.partition("=")
            os.environ.setdefault(cle.strip(), valeur.strip().strip("'\""))


_charge_env()


def url_base() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://vi@127.0.0.1:55432/vi_mapping")


def contact() -> str | None:
    return os.environ.get("VI_CONTACT") or None


def dossier_donnees() -> Path:
    d = Path(os.environ.get("VI_DATA_DIR", RACINE / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d
