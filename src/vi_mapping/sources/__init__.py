"""Connecteurs : un module par source, déclaré avec @connecteur."""

from importlib import import_module
from pkgutil import iter_modules


def charger() -> None:
    """Importe les connecteurs (open data, scrapers) et les calculs pour remplir le registre."""
    from .. import calculs, scrapers

    for paquet, chemin in (
        (__name__, __path__), (scrapers.__name__, scrapers.__path__), (calculs.__name__, calculs.__path__)
    ):
        for m in iter_modules(chemin):
            if m.name not in ("base",) and not m.name.startswith("_"):
                import_module(f"{paquet}.{m.name}")
