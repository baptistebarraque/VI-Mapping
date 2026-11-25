"""Ligne de commande : `uv run vi --help`."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .config import config_sources
from .db import connexion
from .db import migrer as appliquer_migrations
from .sources import charger
from .sources.base import REGISTRE, a_collecter, dernier_succes, executer, ordre, sources_dues

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Collecte et carte V.i, Île-de-France.")
console = Console()


@app.command()
def migrer() -> None:
    """Crée ou met à jour le schéma, et synchronise le registre des sources."""
    with connexion() as conn:
        faits = appliquer_migrations(conn)
    console.print(f"Migrations appliquées : {', '.join(faits) or 'aucune (schéma à jour)'}")


@app.command()
def sources() -> None:
    """Liste les sources, leur statut et la dernière collecte réussie."""
    charger()
    t = Table("code", "méthode", "fréquence", "statut", "dernier succès", "libellé")
    with connexion() as conn:
        for code, s in config_sources().items():
            fait = dernier_succes(conn, code)
            statut = "[yellow]verrouillée[/yellow]" if s.verrouillee else "ouverte"
            if code not in REGISTRE and not s.verrouillee:
                statut = "[dim]interne[/dim]"
            t.add_row(code, s.methode, s.frequence, statut, f"{fait:%Y-%m-%d %H:%M}" if fait else "-", s.libelle)
    console.print(t)


@app.command()
def collecter(
    codes: Annotated[list[str] | None, typer.Argument(help="Codes des sources (voir `vi sources`)")] = None,
    tout: Annotated[bool, typer.Option("--tout", help="Toutes les sources")] = False,
    dus: Annotated[bool, typer.Option("--dus", help="Seulement celles arrivées à échéance")] = False,
    limite: Annotated[int | None, typer.Option(help="Nombre maximal de sites (scrapers)")] = None,
    forcer: Annotated[bool, typer.Option("--forcer", help="Accepter une forte baisse du nombre de lignes")] = False,
) -> None:
    """Collecte une ou plusieurs sources (idempotent)."""
    charger()
    if tout:
        choix = ordre(a_collecter())
    elif dus:
        with connexion() as conn:
            choix = sources_dues(conn)
    else:
        inconnus = [c for c in codes or [] if c not in REGISTRE and c not in config_sources()]
        if inconnus or not codes:
            raise typer.BadParameter(f"sources inconnues : {inconnus}" if inconnus else "aucune source demandée")
        choix = ordre([c for c in codes if c in REGISTRE]) + [c for c in codes if c not in REGISTRE]
    options = {"forcer": True} if forcer else {}
    echecs = [c for c in choix if executer(c, limite=limite, options=options) == "echec"]
    if echecs:
        console.print(f"[red]Échecs : {', '.join(echecs)}[/red]")
        raise typer.Exit(1)


@app.command()
def rattacher() -> None:
    """Rattache écoles, IRIS, QPV, accueils et associations ; repère les doublons."""
    charger()
    if executer("rattachements") == "echec":
        raise typer.Exit(1)


@app.command()
def proximite(
    forcer: Annotated[bool, typer.Option("--forcer", help="Recalculer même si rien n'a changé")] = False,
) -> None:
    """Calcule distances et temps par la route (OSRM) entre écoles, producteurs et relais."""
    charger()
    if executer("osrm", options={"forcer": True} if forcer else {}) == "echec":
        raise typer.Exit(1)
