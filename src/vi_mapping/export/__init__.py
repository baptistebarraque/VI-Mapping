"""Export des données vers la carte : fichiers JSON statiques, remplacés d'un bloc."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..config import RACINE, config_idf, config_jauges
from . import meta as meta_
from . import points, zones
from .commun import Connexion, ecrire
from .ecoles import ecoles
from .fiches import Fiches


def dossier_export() -> Path:
    return Path(os.environ.get("VI_EXPORT_DIR", RACINE / "web" / "public" / "donnees"))


def exporter(conn: Connexion, dossier: Path, note: Callable[[str], None] = lambda _: None) -> dict[str, int]:
    """Écrit tous les fichiers dans un dossier provisoire, puis le met à la place de l'ancien."""
    provisoire = dossier.with_name(dossier.name + ".nouveau")
    shutil.rmtree(provisoire, ignore_errors=True)
    tailles: dict[str, int] = {}

    def fichier(nom: str, objet: Any) -> None:
        tailles[nom] = ecrire(provisoire / nom, objet)

    idf, cfg = config_idf(), config_jauges()
    communes = meta_.communes(conn)
    fichier("meta.json", meta_.meta(conn, idf, cfg, communes))
    fichier("ecoles.json", ecoles(conn, cfg, {c["code"]: i for i, c in enumerate(communes)}))
    producteurs, rang_producteur = points.producteurs(conn, cfg)
    relais, rang_relais = points.relais(conn)
    fichier("points/producteurs.geojson", producteurs)
    fichier("points/relais.geojson", relais)
    fichier("points/accueils.geojson", points.accueils(conn))
    fichier("points/assos.geojson", points.assos(conn))
    note("points exportés")
    fichier("zones/communes.geojson", zones.communes(conn))
    fichier("zones/iris.geojson", zones.iris(conn))
    for type_, nom in (("pat", "pat"), ("qpv", "qpv"), ("cite_educative", "cites")):
        fichier(f"zones/{nom}.geojson", zones.dispositifs(conn, type_))
    note("zones exportées")
    tailles["fiches"] = 0
    for code, fiche in Fiches(conn, rang_producteur, rang_relais).composer():
        tailles["fiches"] += ecrire(provisoire / "fiches" / f"{code}.json", fiche)

    ancien = dossier.with_name(dossier.name + ".ancien")
    shutil.rmtree(ancien, ignore_errors=True)
    if dossier.exists():
        dossier.rename(ancien)
    provisoire.rename(dossier)
    shutil.rmtree(ancien, ignore_errors=True)
    return tailles
