"""Aides de l'export : provenance compacte, nombres, écriture des fichiers JSON."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg

Ligne = Mapping[str, Any]
Connexion = psycopg.Connection[Any]


def prov(r: Ligne) -> dict[str, Any]:
    """Provenance d'une ligne : s(ource), u(rl), d(ate de collecte), c(onfiance). La méthode est dans meta.sources."""
    return {"s": r["source"], "u": r["url"], "d": r["collecte_le"].date(), "c": r["confiance"]}


def prov_groupes(provenances: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Même chose pour une colonne `provenances` : {groupe de champs: provenance}."""
    return {
        g: {"s": p["source"], "u": p["url"], "d": p["collecte_le"][:10], "c": p["confiance"]}
        for g, p in sorted(provenances.items())
    }


def sans_vide(objet: dict[str, Any]) -> dict[str, Any]:
    """Retire les valeurs absentes (None, liste ou dictionnaire vide) : le lecteur les traite comme inconnues."""
    return {k: v for k, v in objet.items() if v is not None and v != [] and v != {}}


def _defaut(x: Any) -> Any:
    if isinstance(x, Decimal):
        return int(x) if x == x.to_integral_value() else float(x)
    if isinstance(x, datetime):
        return x.isoformat(timespec="seconds")
    if isinstance(x, date):
        return x.isoformat()
    raise TypeError(f"{type(x).__name__} non sérialisable")


def ecrire(chemin: Path, objet: Any) -> int:
    """Écrit un JSON compact ; retourne sa taille en octets."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(objet, ensure_ascii=False, separators=(",", ":"), default=_defaut)
    return chemin.write_text(texte + "\n", encoding="utf-8")


def collection(features: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": list(features)}


def feature_point(lon: float, lat: float, proprietes: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
        "properties": sans_vide(proprietes),
    }


# Fiche principale d'un accueil ; le gestionnaire manquant vient d'un de ses doublons (autre source, même lieu).
ACCUEILS = """
    SELECT a.*, ST_X(a.geom) AS lon, ST_Y(a.geom) AS lat, coalesce(g.nom, a.exploitant, d.nom) AS gestionnaire,
           CASE WHEN a.exploitant IS NULL OR g.siren IS NOT NULL THEN coalesce(g.type, d.type) END AS gestionnaire_type,
           CASE WHEN a.exploitant IS NULL OR g.siren IS NOT NULL THEN coalesce(g.siren, d.siren) END AS siren
    FROM accueil_periscolaire a
    LEFT JOIN gestionnaire_perisco g ON g.siren = a.gestionnaire_siren
    LEFT JOIN LATERAL (
      SELECT coalesce(h.nom, b.exploitant) AS nom, h.type, h.siren
      FROM accueil_periscolaire b LEFT JOIN gestionnaire_perisco h ON h.siren = b.gestionnaire_siren
      WHERE b.doublon_de = a.id AND coalesce(h.nom, b.exploitant) IS NOT NULL
      ORDER BY h.siren IS NULL, b.id LIMIT 1) d ON true
    WHERE a.doublon_de IS NULL"""
