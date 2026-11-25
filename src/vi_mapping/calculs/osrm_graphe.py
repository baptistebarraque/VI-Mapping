"""Graphe routier OSRM : construction à partir de l'extrait OpenStreetMap régional, puis matrices en mémoire.

Aucun serveur à installer : les outils sont fournis par le paquet `osrm-bindings` (extra `route`).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from ..config import ConfigIdf, dossier_donnees
from ..outils.http import ClientHttp

PLAFOND_TABLE = 4_000_000  # cases par matrice ; au-delà OSRM refuserait la requête
ETAPES = (("osrm-contract", []),)


def _paquet() -> Path:
    try:
        import osrm
    except ImportError as e:
        raise RuntimeError("OSRM absent : installer l'extra « route » (uv sync --extra route)") from e
    return Path(osrm.__file__).parent


def _lancer(outil: str, *arguments: str) -> None:
    binaire = _paquet() / "bin" / outil
    r = subprocess.run([str(binaire), *arguments], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"{outil} a échoué : {(r.stderr or r.stdout)[-800:]}")


def preparer(http: ClientHttp, idf: ConfigIdf) -> tuple[Path, str]:
    """Chemin du graphe et identifiant de sa version ; reconstruit seulement si l'extrait OSM a changé."""
    pbf = http.telecharger(idf.proximite.osm_url, "ile-de-france.osm.pbf")
    meta = json.loads(pbf.with_name(pbf.name + ".meta.json").read_text())
    version = hashlib.sha1(
        f"{meta.get('etag')}|{meta.get('last_modified')}|{idf.proximite.profil}".encode()
    ).hexdigest()[:12]
    racine = dossier_donnees() / "osrm"
    dossier = racine / version
    graphe = dossier / "idf.osrm"
    temoin = dossier / "pret.json"
    if not temoin.exists():
        shutil.rmtree(dossier, ignore_errors=True)
        dossier.mkdir(parents=True)
        profil = _paquet() / "share" / "profiles" / f"{idf.proximite.profil}.lua"
        _lancer("osrm-extract", "-p", str(profil), "-o", str(graphe), str(pbf))
        _lancer("osrm-contract", str(graphe))
        temoin.write_text(json.dumps({"version": version, "osm": meta}))
        for ancien in racine.iterdir():  # une seule version conservée
            if ancien.is_dir() and ancien != dossier:
                shutil.rmtree(ancien, ignore_errors=True)
    return graphe, version


class Matrices:
    """Distances et durées entre listes de points."""

    def __init__(self, graphe: Path) -> None:
        _paquet()
        import osrm

        self._osrm = osrm
        config = osrm.EngineConfig(
            storage_config=str(graphe), use_shared_memory=False, algorithm="CH", max_locations_distance_table=-1,
        )
        self._moteur = osrm.OSRM(config)

    def calculer(
        self, departs: list[tuple[float, float]], arrivees: list[tuple[float, float]]
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        """(km, minutes) pour chaque couple ; NaN s'il n'y a pas d'itinéraire."""
        points = [self._osrm.Coordinate(p) for p in (*departs, *arrivees)]
        parametres = self._osrm.TableParameters(
            coordinates=points,
            sources=list(range(len(departs))),
            destinations=list(range(len(departs), len(points))),
            annotations=["duration", "distance"],
        )
        r = self._moteur.Table(parametres)
        durees = np.array([[np.nan if v is None else v for v in ligne] for ligne in r["durations"]], dtype=float)
        metres = np.array([[np.nan if v is None else v for v in ligne] for ligne in r["distances"]], dtype=float)
        return metres / 1000, durees / 60
