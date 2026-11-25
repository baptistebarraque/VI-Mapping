"""Base temporaire pour les tests d'intégration ; ils sont sautés si PostgreSQL + PostGIS n'est pas joignable."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from vi_mapping.config import url_base
from vi_mapping.db import connexion, migrer

Connexion = psycopg.Connection[dict[str, Any]]


@pytest.fixture(scope="session")
def url_temporaire() -> Iterator[str]:
    nom = f"vi_test_{os.getpid()}"
    try:
        admin = psycopg.connect(url_base(), autocommit=True, connect_timeout=3)
        admin.execute(f"CREATE DATABASE {nom}")  # type: ignore[arg-type]
    except psycopg.Error as e:
        pytest.skip(f"base indisponible : {type(e).__name__}")
    url = urlunsplit(urlsplit(url_base())._replace(path=f"/{nom}"))
    try:
        with connexion(url) as conn:
            migrer(conn)
        yield url
    finally:
        admin.execute(f"DROP DATABASE IF EXISTS {nom} WITH (FORCE)")  # type: ignore[arg-type]
        admin.close()


@pytest.fixture
def conn(url_temporaire: str) -> Iterator[Connexion]:
    """Connexion dont tout est annulé à la fin du test."""
    c = connexion(url_temporaire)
    try:
        yield c  # type: ignore[misc]
    finally:
        c.rollback()
        c.close()
