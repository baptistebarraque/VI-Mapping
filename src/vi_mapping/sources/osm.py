"""Accueils de loisirs et relais locaux d'OpenStreetMap (extrait régional Geofabrik, licence ODbL)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import osmium

from ..db import point, upsert
from ..outils import motifs
from ..outils.texte import adresse_sans_personne, normaliser, sans_contact, site_web
from .base import Compteurs, Contexte, connecteur

# Objets qui portent le nom du lieu sans être le lieu (arrêt de bus, parking, jardin, limite…)
CLES_EXCLUES = ("highway", "public_transport", "natural", "boundary", "barrier", "railway", "place", "route")
VALEURS_EXCLUES = {
    "leisure": {"playground", "park", "pitch", "garden", "stadium", "swimming_pool", "resort", "track"},
    "amenity": {"school", "parking", "bicycle_parking", "polling_station", "townhall", "library", "restaurant"},
    "landuse": {"grass", "forest", "recreation_ground", "farmland", "residential"},
}
_JOURS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def horaires_jours(texte: str) -> dict[str, list[tuple[int, int]]]:
    """Plages horaires par jour d'un `opening_hours` simple, en minutes. Règle inconnue : ignorée."""
    jours: dict[str, list[tuple[int, int]]] = {}
    for regle in texte.split(";"):
        m = re.match(r"\s*((?:Mo|Tu|We|Th|Fr|Sa|Su)(?:[-,](?:Mo|Tu|We|Th|Fr|Sa|Su))*)\s+(.+)", regle)
        if not m:
            continue
        choisis: list[str] = []
        for bloc in m[1].split(","):
            a, _, b = bloc.partition("-")
            choisis += _JOURS[_JOURS.index(a): _JOURS.index(b) + 1] if b else [a]
        plages = [
            (int(h1) * 60 + int(m1), int(h2) * 60 + int(m2))
            for h1, m1, h2, m2 in re.findall(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", m[2])
        ]
        for j in choisis:
            jours[j] = plages
    return jours


def ouvertures(texte: str | None) -> tuple[bool | None, bool | None]:
    """(accueil du soir, accueil du mercredi) d'après les horaires ; None si on ne sait pas."""
    jours = horaires_jours(texte or "")
    if not jours:
        return None, None
    soir = [j for j in ("Mo", "Tu", "Th", "Fr") if any(fin >= 18 * 60 for _, fin in jours.get(j, []))]
    return len(soir) >= 2, bool(jours.get("We"))


def ignorer(tags: Any) -> bool:
    return any(c in tags for c in CLES_EXCLUES) or any(tags.get(c) in v for c, v in VALEURS_EXCLUES.items())


def adresse(tags: Any) -> str | None:
    if "addr:street" not in tags:
        return None
    debut = " ".join(t for t in (tags.get("addr:housenumber"), tags.get("addr:street")) if t)
    fin = " ".join(t for t in (tags.get("addr:postcode"), tags.get("addr:city")) if t)
    return adresse_sans_personne(f"{debut}, {fin}".strip(" ,"))


@connecteur("osm", depend_de=["ign_admin_express"])
def collecter(ctx: Contexte) -> Compteurs:
    chemin = ctx.http.telecharger(ctx.config.url, "ile-de-france.osm.pbf")
    accueils: list[dict[str, Any]] = []
    relais: list[dict[str, Any]] = []
    compte: Counter[str] = Counter()
    lecteur = (
        osmium.FileProcessor(str(chemin)).with_locations().with_areas()
        .with_filter(osmium.filter.KeyFilter("name"))
    )
    for o in lecteur:
        tags = o.tags
        nom = normaliser(tags.get("name"))
        accueil = motifs.est_accueil(nom)
        type_ = None
        if not accueil:
            type_ = motifs.type_relais(nom)
            if type_ is None and tags.get("amenity") == "social_centre":
                type_ = "centre_social"
            if type_ is None and tags.get("tourism") == "zoo" and tags.get("zoo") == "petting_zoo":
                type_ = "ferme_pedagogique"
        if (not accueil and type_ is None) or ignorer(tags):
            continue
        position, ref = emplacement(o)
        if position is None:
            continue
        commun = {
            "id": f"osm:{ref}",
            "nom": sans_contact(tags.get("name")),
            "adresse": adresse(tags),
            "geom": point(*position),
            **ctx.provenance(f"https://www.openstreetmap.org/{ref}"),
        }
        if accueil:
            soir, mercredi = ouvertures(tags.get("opening_hours"))
            accueils.append({
                **commun,
                "accueil_soir": soir if soir is not None else motifs.accueil_soir(nom),
                "accueil_mercredi": mercredi if mercredi is not None else motifs.accueil_mercredi(nom),
                "horaires": tags.get("opening_hours"),
                "exploitant": sans_contact(tags.get("operator")),
            })
        else:
            relais.append({**commun, "type": type_, "site_web": site_web(tags.get("website"))})
            compte[str(type_)] += 1
    upsert(ctx.conn, "accueil_periscolaire", accueils, ["id"])
    upsert(ctx.conn, "relais_local", relais, ["id"])
    for table in ("accueil_periscolaire", "relais_local"):
        # Commune par jointure spatiale ; hors région (extrait Geofabrik un peu plus large) : supprimé.
        ctx.conn.execute(
            f"UPDATE {table} t SET commune = c.code_insee FROM commune c "
            "WHERE t.source = %s AND ST_Intersects(c.geom, t.geom) AND c.code_insee <> '75056'", (ctx.code,)
        )
        compte["hors_idf"] += ctx.conn.execute(
            f"DELETE FROM {table} WHERE source = %s AND commune IS NULL", (ctx.code,)
        ).rowcount
    compte["accueils"] = len(accueils)
    compte["supprimes"] = ctx.purger("accueil_periscolaire") + ctx.purger("relais_local")
    return dict(compte)


def emplacement(o: Any) -> tuple[tuple[float, float] | None, str]:
    """Position (centre de l'emprise pour les surfaces) et référence « type/id » de l'objet."""
    if o.is_node():
        return (o.location.lon, o.location.lat), f"node/{o.id}"
    if o.is_area():
        ref = f"way/{o.orig_id()}" if o.from_way() else f"relation/{o.orig_id()}"
        xs, ys = [], []
        for anneau in o.outer_rings():
            for n in anneau:
                xs.append(n.lon)
                ys.append(n.lat)
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2) if xs else None, ref
    return None, ""  # ligne ouverte ou relation non surfacique
