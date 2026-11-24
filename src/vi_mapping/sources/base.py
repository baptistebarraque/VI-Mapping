"""Socle commun des connecteurs : registre, contexte d'exécution, journal des collectes."""

from __future__ import annotations

import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import psycopg
from psycopg.types.json import Jsonb
from rich.console import Console

from ..config import ConfigIdf, SourceConfig, config_idf, config_sources
from ..db import Ligne, connexion, purger_absents
from ..db import enrichir as enrichir_table
from ..outils.http import ClientHttp

console = Console()

Compteurs = dict[str, int]
Statut = Literal["succes", "echec", "ignoree"]
DUREE = {"mensuelle": timedelta(days=28), "annuelle": timedelta(days=360)}


@dataclass
class Contexte:
    """Ce dont un connecteur a besoin. Tout s'exécute dans une seule transaction."""

    code: str
    conn: psycopg.Connection[Any]
    http: ClientHttp
    idf: ConfigIdf
    config: SourceConfig
    debut: datetime
    limite: int | None = None
    options: dict[str, Any] = field(default_factory=dict)

    def provenance(
        self, url: str | None = None, *, confiance: float | None = None, methode: str | None = None
    ) -> dict[str, Any]:
        """Colonnes obligatoires de chaque ligne."""
        return {
            "source": self.code,
            "url": url or self.config.url,
            "methode": methode or self.config.methode,
            "collecte_le": self.debut,
            "confiance": round(self.config.confiance if confiance is None else confiance, 2),
        }

    def provenance_json(self, url: str | None = None, *, confiance: float | None = None) -> dict[str, Any]:
        """Même information pour la colonne `provenances` des tables enrichies par plusieurs sources."""
        p = self.provenance(url, confiance=confiance)
        return {**p, "collecte_le": self.debut.isoformat(timespec="seconds")}

    @property
    def chute_max(self) -> float:
        """Baisse tolérée avant de refuser la mise à jour ; levée par --forcer (élections, refonte d'un jeu)."""
        return 1.0 if self.options.get("forcer") else 0.5

    def purger(self, table: str, filtre: str = "TRUE") -> int:
        """Supprime les lignes de cette source non revues pendant la collecte."""
        return purger_absents(self.conn, table, self.code, self.debut, filtre=filtre, chute_max=self.chute_max)

    def enrichir(self, table: str, lignes: Iterable[Ligne], cle: str, groupe: str) -> int:
        """Met à jour des lignes existantes d'une table (voir db.enrichir)."""
        return enrichir_table(self.conn, table, lignes, cle, groupe, chute_max=self.chute_max)

    def note(self, message: str) -> None:
        console.print(f"  [dim]{self.code}[/dim] {message}")


@dataclass(frozen=True)
class Connecteur:
    code: str
    fonction: Callable[[Contexte], Compteurs]
    depend_de: tuple[str, ...]


REGISTRE: dict[str, Connecteur] = {}


def connecteur(code: str, *, depend_de: Iterable[str] = ()) -> Callable[[Callable[[Contexte], Compteurs]], Any]:
    """Déclare la fonction de collecte d'une source de config/sources.yaml."""

    def enregistrer(f: Callable[[Contexte], Compteurs]) -> Callable[[Contexte], Compteurs]:
        if code not in config_sources():
            raise KeyError(f"{code} absent de config/sources.yaml")
        REGISTRE[code] = Connecteur(code, f, tuple(depend_de))
        return f

    return enregistrer


def ordre(codes: Iterable[str]) -> list[str]:
    """Trie les codes selon leurs dépendances (celles qui ne sont pas demandées sont ignorées)."""
    demandes = list(dict.fromkeys(codes))
    vus: list[str] = []

    def visiter(c: str) -> None:
        if c in vus:
            return
        for d in REGISTRE[c].depend_de:
            if d in demandes:
                visiter(d)
        vus.append(c)

    for c in demandes:
        visiter(c)
    return vus


def dernier_succes(conn: psycopg.Connection[Any], code: str) -> datetime | None:
    r = conn.execute(
        "SELECT max(fin) AS f FROM collecte_run WHERE source = %s AND statut = 'succes'", (code,)
    ).fetchone()
    return r["f"] if r else None


def sources_dues(conn: psycopg.Connection[Any]) -> list[str]:
    """Sources dont la dernière collecte réussie est plus vieille que leur fréquence."""
    maintenant = datetime.now(UTC)
    dues = []
    for code in REGISTRE:
        dernier = dernier_succes(conn, code)
        if dernier is None or maintenant - dernier > DUREE[config_sources()[code].frequence]:
            dues.append(code)
    return ordre(dues)


def executer(code: str, *, limite: int | None = None, options: dict[str, Any] | None = None) -> Statut:
    """Lance une collecte : transaction unique, journalisée, sans interrompre les suivantes en cas d'échec."""
    config = config_sources()[code]
    debut = datetime.now(UTC)
    with connexion() as journal:
        journal.autocommit = True
        run = journal.execute(
            "INSERT INTO collecte_run (source, debut, parametres) VALUES (%s, %s, %s) RETURNING id",
            (code, debut, Jsonb({"limite": limite, **(options or {})})),
        ).fetchone()["id"]  # type: ignore[index]

        def clore(statut: Statut, compteurs: Compteurs | None = None, message: str | None = None) -> Statut:
            journal.execute(
                "UPDATE collecte_run SET fin = now(), statut = %s, compteurs = %s, message = %s WHERE id = %s",
                (statut, Jsonb(compteurs or {}), message, run),
            )
            return statut

        if config.verrouillee:
            assert config.verification is not None
            message = f"Source verrouillée : {config.verification.constat}"
            console.print(f"[yellow]verrouillée[/yellow] {code} (voir docs/SOURCES.md)")
            return clore("ignoree", message=message)

        console.print(f"[bold]{code}[/bold] {config.libelle}")
        try:
            with connexion() as conn, ClientHttp() as http:
                ctx = Contexte(code, conn, http, config_idf(), config, debut, limite, options or {})
                compteurs = REGISTRE[code].fonction(ctx)
        except Exception as e:
            console.print(f"  [red]échec[/red] {type(e).__name__}: {e}")
            return clore("echec", message="".join(traceback.format_exception(e))[-4000:])
        duree = (datetime.now(UTC) - debut).total_seconds()
        console.print(f"  [green]ok[/green] {compteurs} en {duree:.0f} s")
        return clore("succes", compteurs)


def fusion_provenance(colonne: str = "provenances") -> str:
    """Fragment SQL : ajoute un groupe de provenance sans effacer les autres."""
    return f"{colonne} = {colonne} || jsonb_build_object(%(groupe)s::text, %(prov)s::jsonb)"
