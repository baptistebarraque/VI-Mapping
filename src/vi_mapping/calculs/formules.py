"""Formules des jauges (0 à 100). Fonctions pures, sans base de données : tout vient de config/jauges.yaml.

Chaque jauge est la moyenne pondérée de ses critères connus. Un critère inconnu vaut None et n'est jamais
compté 0 ; si la part connue est trop faible, la jauge vaut None (« données insuffisantes »).
Les formules `producteurs` et `score` sont reprises en TypeScript (web/src/jauges.ts) : mêmes vecteurs de test.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..config import ConfigJauges, Rayon


@dataclass(frozen=True)
class Critere:
    code: str
    valeur: float | None          # 0 à 100, None = inconnu
    poids: float
    detail: Any = None            # ce qui explique la valeur (affiché dans la fiche)


@dataclass(frozen=True)
class Jauge:
    valeur: float | None
    part_connue: float            # 0 à 1
    criteres: tuple[Critere, ...]

    def en_json(self) -> dict[str, Any]:
        return {
            "valeur": self.valeur,
            "part_connue": round(self.part_connue, 2),
            "criteres": [
                {"code": c.code, "valeur": None if c.valeur is None else round(c.valeur, 1), "poids": c.poids,
                 "detail": c.detail}
                for c in self.criteres
            ],
        }


def borne(x: float) -> float:
    return max(0.0, min(100.0, x))


def moyenne(criteres: Sequence[Critere], part_min: float) -> Jauge:
    total = sum(c.poids for c in criteres)
    connus = [c for c in criteres if c.valeur is not None]
    poids = sum(c.poids for c in connus)
    part = poids / total if total else 0.0
    if not connus or part < part_min or poids == 0:
        return Jauge(None, part, tuple(criteres))
    valeur = sum(c.poids * c.valeur for c in connus if c.valeur is not None) / poids
    return Jauge(round(borne(valeur), 1), part, tuple(criteres))


# --------------------------------------------------------------------------- engagement de la collectivité
def engagement(
    cfg: ConfigJauges, *, pat: str, pat_nom: str | None, pct_bio: float | None, annee_bio: int | None,
    themes: Sequence[str] | None, themes_sans_date: Sequence[str] = (), cite: str | None = None,
) -> Jauge:
    """`pat` : avec_axe_education, sans_axe_education ou aucun. `themes` : None si le site n'a pas été visité."""
    e = cfg.engagement
    web = None
    if themes is not None:
        seuls = [t for t in themes_sans_date if t not in themes]
        web = borne(100 * (len(themes) + e.web.poids_sans_date * len(seuls)) / e.web.themes_plein)
    return moyenne([
        Critere("pat", getattr(e.pat, pat), e.sous_poids["pat"], pat_nom),
        Critere("bio", None if pct_bio is None else borne(100 * pct_bio / e.bio.pct_plein), e.sous_poids["bio"],
                None if pct_bio is None else {"pct": pct_bio, "annee": annee_bio}),
        Critere("web", web, e.sous_poids["web"],
                None if themes is None else {"recents": sorted(themes), "sans_date": sorted(set(themes_sans_date))}),
        Critere("cite_educative", 100.0 if cite else 0.0, e.sous_poids["cite_educative"], cite),
    ], cfg.donnees_insuffisantes.part_min_connue_jauge)


# --------------------------------------------------------------------------- périscolaire
@dataclass(frozen=True)
class Accueil:
    soir: bool | None
    mercredi: bool | None
    gestionnaire: bool            # identifié (Siren ou nom d'exploitant)
    centre_de_loisirs: bool       # nommé « centre / accueil de loisirs »


def periscolaire(
    cfg: ConfigJauges, accueils: Sequence[Accueil], *, soir_commune: bool = False, mercredi_commune: bool = False,
) -> Jauge:
    """`accueils` : ceux à moins de 300 m (ou à la même adresse). `*_commune` : annoncé sur le site de la mairie."""
    p = cfg.periscolaire
    exhaustif = p.source_exhaustive
    soir: float | None = 0.0 if exhaustif else None
    origine_soir = None
    options_soir: list[tuple[float, str]] = []
    if any(a.soir for a in accueils):
        options_soir.append((p.soir.oui, "oui"))
    if any(a.soir is None for a in accueils):
        options_soir.append((p.soir.accueil_sans_horaire, "accueil_sans_horaire"))
    if soir_commune:
        options_soir.append((p.soir.oui_commune, "oui_commune"))
    if not options_soir and accueils:
        options_soir.append((0.0, "non"))
    if options_soir:
        soir, origine_soir = max(options_soir)

    mercredi: float | None = 0.0 if exhaustif else None
    origine_mercredi = None
    options: list[tuple[float, str]] = []
    if any(a.mercredi for a in accueils):
        options.append((p.mercredi.oui, "oui"))
    if any(a.mercredi is None and a.centre_de_loisirs for a in accueils):
        options.append((p.mercredi.centre_de_loisirs, "centre_de_loisirs"))
    if mercredi_commune:
        options.append((p.mercredi.oui_commune, "oui_commune"))
    if not options and accueils and all(a.mercredi is False for a in accueils):
        options.append((0.0, "non"))
    if options:
        mercredi, origine_mercredi = max(options)

    gestionnaire: float | None = None
    if accueils:
        identifie = any(a.gestionnaire for a in accueils)
        gestionnaire = p.gestionnaire.identifie if identifie else p.gestionnaire.non_identifie
    elif exhaustif:
        gestionnaire = 0.0
    return moyenne([
        Critere("soir", soir, p.sous_poids["soir"], origine_soir),
        Critere("mercredi", mercredi, p.sous_poids["mercredi"], origine_mercredi),
        Critere("gestionnaire", gestionnaire, p.sous_poids["gestionnaire"], len(accueils) or None),
    ], cfg.donnees_insuffisantes.part_min_connue_jauge)


# --------------------------------------------------------------------------- parents
@dataclass(frozen=True)
class AssoLiee:
    confiance: float
    federation: str | None
    active: bool | None           # activité en ligne de moins de 12 mois ; None si on ne sait pas


def parents(cfg: ConfigJauges, assos: Sequence[AssoLiee]) -> Jauge:
    p = cfg.parents
    liees = [a for a in assos if a.confiance >= p.confiance_min]
    part_min = cfg.donnees_insuffisantes.part_min_connue_jauge
    if not liees:
        vide = 0.0 if p.source_exhaustive else None
        return moyenne([Critere(c, vide, p.sous_poids[c]) for c in ("rattachee", "federee", "active")], part_min)
    meilleure = max(a.confiance for a in liees)
    federations = sorted({a.federation for a in liees if a.federation})
    actives = [a.active for a in liees if a.active is not None]
    return moyenne([
        Critere("rattachee", 100 * meilleure, p.sous_poids["rattachee"], len(liees)),
        Critere("federee", 100.0 if federations else 0.0, p.sous_poids["federee"], federations or None),
        Critere("active", None if not actives else 100.0 if any(actives) else 0.0, p.sous_poids["active"]),
    ], part_min)


# --------------------------------------------------------------------------- producteurs
def dans_rayon(km: float | None, minutes: float | None, rayon: Rayon) -> bool:
    en_km = km is not None and km <= rayon.km
    en_minutes = minutes is not None and minutes <= rayon.minutes
    return en_km if rayon.mode == "km" else en_minutes if rayon.mode == "minutes" else en_km or en_minutes


def proximite_producteur(cfg: ConfigJauges, km: float | None, minutes: float | None, rayon: Rayon) -> float | None:
    """100 à 15 min ou moins, 0 en bord de rayon. En mode km (ou sans durée connue), même principe en km."""
    p = cfg.producteurs
    if minutes is not None and rayon.mode != "km":
        return _pente(minutes, p.minutes_plein, rayon.minutes)
    return None if km is None else _pente(km, p.km_plein, rayon.km)


def _pente(x: float, plein: float, bord: float) -> float:
    if x <= plein and x <= bord:
        return 100.0
    return borne(100 * (bord - x) / (bord - plein)) if bord > plein else 0.0


def producteurs(
    cfg: ConfigJauges, distances: Iterable[tuple[float | None, float | None]] | None, rayon: Rayon | None = None
) -> Jauge:
    """`distances` : (km, minutes) par la route de chaque producteur ; None si l'école n'est pas localisée."""
    p, r = cfg.producteurs, rayon or cfg.rayon
    plus_proche: float | None = None
    nombre: float | None = None
    detail: dict[str, Any] | None = None
    if distances is not None:
        dedans = [(k, m) for k, m in distances if dans_rayon(k, m, r)]
        notes = [n for n in (proximite_producteur(cfg, k, m, r) for k, m in dedans) if n is not None]
        plus_proche = max(notes, default=0.0)
        nombre = borne(100 * len(dedans) / p.nombre_plein)
        minutes = [m for _, m in dedans if m is not None]
        detail = {"nombre": min(len(dedans), p.nombre_plein), "minutes": min(minutes, default=None)}
    return moyenne([
        Critere("plus_proche", plus_proche, p.sous_poids["plus_proche"], detail and detail["minutes"]),
        Critere("nombre", nombre, p.sous_poids["nombre"], detail and detail["nombre"]),
    ], cfg.donnees_insuffisantes.part_min_connue_jauge)


# --------------------------------------------------------------------------- familles
def mixite(cfg: ConfigJauges, ips: float | None, qpv_distance_m: int | None) -> float | None:
    """Mixité sociale : IPS proche de la référence (70 %), QPV à proximité (30 %). Inconnue sans IPS."""
    m = cfg.familles.mixite
    if ips is None:
        return None
    note_ips = borne(100 * (1 - abs(ips - m.ips_reference) / m.ips_amplitude))
    note_qpv = 100.0 if qpv_distance_m is not None and qpv_distance_m <= m.qpv_distance_max_m else 0.0
    return (m.part_ips * note_ips + m.part_qpv * note_qpv) / (m.part_ips + m.part_qpv)


def familles(
    cfg: ConfigJauges, *, nb_eleves: int | None, familles_iris: int | None, ips: float | None,
    qpv_distance_m: int | None, ips_origine: str | None = None,
) -> Jauge:
    f = cfg.familles
    return moyenne([
        Critere("nb_eleves", None if nb_eleves is None else borne(100 * nb_eleves / f.nb_eleves_plein),
                f.sous_poids["nb_eleves"], nb_eleves),
        Critere("familles_iris", None if familles_iris is None else borne(100 * familles_iris / f.familles_iris_plein),
                f.sous_poids["familles_iris"], familles_iris),
        Critere("mixite", mixite(cfg, ips, qpv_distance_m), f.sous_poids["mixite"],
                {"ips": ips, "ips_origine": ips_origine, "qpv_m": qpv_distance_m}),
    ], cfg.donnees_insuffisantes.part_min_connue_jauge)


# --------------------------------------------------------------------------- score
def score(cfg: ConfigJauges, jauges: Mapping[str, float | None], poids: Mapping[str, float] | None = None) -> Jauge:
    """Moyenne pondérée des jauges connues ; None si leur poids total est trop faible."""
    p = poids or cfg.poids
    return moyenne(
        [Critere(nom, jauges.get(nom), p[nom]) for nom in p],  # type: ignore[index]
        cfg.donnees_insuffisantes.part_min_connue_score,
    )


# --------------------------------------------------------------------------- communes (étape 1 de la demande)
@dataclass(frozen=True)
class PatCommune:
    nom: str
    niveau: int | None            # 1 ou 2 ; None : reconnu sans niveau publié
    restauration: bool | None     # axe restauration collective
    education: bool | None        # axe éducation alimentaire


def commune_pat(cfg: ConfigJauges, pats: Sequence[PatCommune]) -> tuple[float, str | None]:
    """Meilleur PAT couvrant la commune ; 0 sans PAT (l'absence est connue : les PAT franciliens sont recensés)."""
    b = cfg.communes.pat
    total = b.part_niveau + b.part_restauration + b.part_education
    notes = [
        (100 * (b.part_niveau * (b.niveau_inconnu if p.niveau is None else p.niveau) / 2
                + b.part_restauration * bool(p.restauration) + b.part_education * bool(p.education)) / total, p.nom)
        for p in pats
    ]
    return max(notes, default=(0.0, None))


def commune_soutiens(cfg: ConfigJauges, *, departement: int | None, interco: int | None, aap_mgp: bool) -> float:
    """Scores 0 à 2 du référentiel ; un territoire absent du référentiel compte 0."""
    b = cfg.communes.soutiens
    total = b.part_departement + b.part_interco + b.part_aap_mgp
    return 100 * (b.part_departement * (departement or 0) / 2 + b.part_interco * (interco or 0) / 2
                  + b.part_aap_mgp * aap_mgp) / total


def commune_cuisine(
    cfg: ConfigJauges, *, type_centrale: str | None, satellites: int | None, sur_place: int | None,
    part_regie: float | None, syndicat: bool = False,
) -> tuple[float | None, str | None]:
    """Cuisine centrale principale, sinon cuisines sur place (régie ou concédée), sinon syndicat de restauration."""
    b = cfg.communes.cuisine
    if type_centrale and type_centrale != "inconnu":
        return getattr(b, type_centrale), type_centrale
    if sur_place and sur_place >= (satellites or 0) and part_regie is not None:
        return (b.sur_place_regie, "sur_place_regie") if part_regie >= 0.5 else (b.sur_place_concedee,
                                                                                  "sur_place_concedee")
    if syndicat:
        return b.intercommunale, "syndicat"
    return None, None


def commune_associations(cfg: ConfigJauges, nombre: int, population: int | None) -> float:
    b = cfg.communes.associations
    densite = 1e4 * nombre / population if population else 0.0
    return 50 * min(1.0, nombre / b.nombre_plein) + 50 * min(1.0, densite / b.densite_plein_10k)


def commune_communications(
    cfg: ConfigJauges, themes: Sequence[str] | None, themes_sans_date: Sequence[str] = ()
) -> float | None:
    """Même barème que le critère « web » de la jauge Engagement ; None si le site n'a pas été visité."""
    if themes is None:
        return None
    w = cfg.engagement.web
    seuls = [t for t in themes_sans_date if t not in themes]
    return borne(100 * (len(themes) + w.poids_sans_date * len(seuls)) / w.themes_plein)


def commune_producteurs(valeurs_ecoles: Iterable[float | None]) -> float | None:
    """Moyenne de la jauge Producteurs des écoles de la commune (connues)."""
    connues = [v for v in valeurs_ecoles if v is not None]
    return round(sum(connues) / len(connues), 1) if connues else None


def commune(cfg: ConfigJauges, valeurs: Mapping[str, float | None], details: Mapping[str, Any] | None = None) -> Jauge:
    """Score d'une commune : moyenne pondérée de ses critères connus (config communes.sous_poids)."""
    d = details or {}
    return moyenne(
        [Critere(nom, valeurs.get(nom), poids, d.get(nom)) for nom, poids in cfg.communes.sous_poids.items()],
        cfg.donnees_insuffisantes.part_min_connue_jauge,
    )
