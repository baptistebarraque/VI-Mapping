"""Ligne de commande : `uv run vi --help`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .config import RACINE, config_sources, dossier_donnees
from .db import connexion
from .db import migrer as appliquer_migrations
from .sources import charger
from .sources.base import REGISTRE, a_collecter, calculer_tout, dernier_succes, executer, ordre, sources_dues

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Collecte et carte V.i, Île-de-France.")
console = Console()


@app.command()
def migrer() -> None:
    """Crée ou met à jour le schéma, et synchronise le registre des sources."""
    with connexion() as conn:
        faits = appliquer_migrations(conn)
    console.print(f"Migrations appliquées : {', '.join(faits) or 'aucune (schéma à jour)'}")


@app.command()
def sources(
    markdown: Annotated[bool, typer.Option("--markdown", help="Registre pour docs/SOURCES.md")] = False,
) -> None:
    """Liste les sources, leur statut et la dernière collecte réussie."""
    if markdown:
        from .registre import markdown as registre

        typer.echo(registre(), nl=False)
        return
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
    sans_calcul: Annotated[bool, typer.Option("--sans-calcul", help="Ne pas recalculer ensuite")] = False,
) -> None:
    """Collecte une ou plusieurs sources (idempotent), puis refait rattachements, distances et jauges."""
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
    if choix and not sans_calcul:
        echecs += calculer_tout()
    if echecs:
        console.print(f"[red]Échecs : {', '.join(echecs)}[/red]")
        raise typer.Exit(1)


@app.command()
def maj(
    limite: Annotated[int | None, typer.Option(help="Nombre maximal de sites (scrapers)")] = None,
) -> None:
    """Mise à jour planifiée : sources arrivées à échéance, calculs, contrôles, rapport de couverture et export."""
    charger()
    with connexion() as verrou:
        verrou.autocommit = True
        pris = verrou.execute("SELECT pg_try_advisory_lock(hashtext('vi maj')) AS pris").fetchone()
        if not pris or not pris["pris"]:
            console.print("[yellow]Une mise à jour est déjà en cours.[/yellow]")
            raise typer.Exit(1)
        choix = sources_dues(verrou)
        console.print(f"Sources à échéance : {', '.join(choix) or 'aucune'}")
        echecs = [c for c in choix if executer(c, limite=limite) == "echec"]
        echecs += calculer_tout()
        if not afficher_controles():
            # La carte garde son dernier export valable.
            console.print("[red]Contrôles en erreur : rapport et export non refaits.[/red]")
            raise typer.Exit(1)
        # Hors du dépôt : une tâche planifiée ne doit pas modifier de fichier versionné.
        couverture(dossier_donnees() / "rapports")
        exporter(None)
    if echecs:
        console.print(f"[red]Échecs : {', '.join(echecs)}[/red]")
        raise typer.Exit(1)


def afficher_controles() -> bool:
    from .verifications import verifier as controles

    t = Table("contrôle", "résultat", "exemples")
    valide = True
    with connexion() as conn:
        for c in controles(conn):
            couleur = "green" if c.conforme else "red" if c.gravite == "erreur" else "yellow"
            etat = "ok" if c.conforme else f"{c.gravite} : {c.nombre}"
            t.add_row(c.nom, f"[{couleur}]{etat}[/{couleur}]", ", ".join(c.exemples))
            valide = valide and (c.conforme or c.gravite != "erreur")
    console.print(t)
    return valide


@app.command()
def verifier() -> None:
    """Contrôle la base : données personnelles, périmètre, provenance, cohérence des calculs."""
    charger()
    if not afficher_controles():
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


@app.command()
def jauges() -> None:
    """Recalcule les cinq jauges et le score de chaque école (config/jauges.yaml)."""
    charger()
    if executer("jauges") == "echec":
        raise typer.Exit(1)


@app.command()
def exporter(
    dossier: Annotated[Path | None, typer.Option(help="Dossier de destination (web/public/donnees)")] = None,
) -> None:
    """Écrit les fichiers JSON lus par la carte."""
    from .export import dossier_export
    from .export import exporter as ecrire_export

    destination = dossier or dossier_export()
    with connexion() as conn:
        tailles = ecrire_export(conn, destination, lambda m: console.print(f"  [dim]export[/dim] {m}"))
    for nom, octets in tailles.items():
        console.print(f"  {nom:28} {octets / 1e6:8.2f} Mo")
    console.print(f"[green]ok[/green] {destination}")


@app.command()
def couverture(
    dossier: Annotated[Path | None, typer.Option(help="Dossier du rapport (docs)")] = None,
) -> None:
    """Écrit le rapport de couverture : taux de remplissage par champ et par département."""
    from .couverture import mesurer, rendu

    destination = dossier or RACINE / "docs"
    destination.mkdir(parents=True, exist_ok=True)
    with connexion() as conn:
        r = mesurer(conn)
    for nom, texte in (("rapport_couverture.md", rendu.markdown(r)), ("rapport_couverture.csv", rendu.csv_long(r))):
        (destination / nom).write_text(texte, encoding="utf-8")
        console.print(f"[green]ok[/green] {destination / nom}")


@app.command()
def sauvegarder(fichier: Annotated[Path, typer.Argument(help="Archive à écrire (.zip)")]) -> None:
    """Écrit une archive portable et publiable de la base."""
    from .sauvegarde import sauvegarder as ecrire

    with connexion() as conn:
        ecrire(conn, fichier)
    console.print(f"[green]ok[/green] {fichier} ({fichier.stat().st_size / 1e6:.0f} Mo)")


@app.command()
def restaurer(
    fichier: Annotated[Path, typer.Argument(help="Archive écrite par « vi sauvegarder »")],
    remplacer: Annotated[bool, typer.Option("--remplacer", help="Effacer les données présentes")] = False,
) -> None:
    """Crée le schéma et recharge une archive, au lieu de tout collecter."""
    from .sauvegarde import restaurer as recharger

    with connexion() as conn:
        try:
            compte = recharger(conn, fichier, remplacer=remplacer)
        except RuntimeError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e
    console.print(f"[green]ok[/green] {compte}")
