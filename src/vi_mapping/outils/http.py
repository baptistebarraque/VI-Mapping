"""Client HTTP des connecteurs : user-agent identifié, débit limité par hôte, reprises, cache conditionnel."""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from ..config import config_idf, contact, dossier_donnees

A_REESSAYER = {429, 500, 502, 503, 504}


def user_agent() -> str:
    h = config_idf().http
    suffixe = f" (+{c})" if (c := contact()) else ""
    return f"{h.nom_robot}/{h.version}{suffixe}"


class Cadence:
    """Impose un délai minimal entre deux requêtes vers un même hôte (sûr entre threads)."""

    def __init__(self, delai_s: float) -> None:
        self.delai_s = delai_s
        self._verrous: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._dernier: dict[str, float] = {}
        self._global = threading.Lock()

    def attendre(self, hote: str, delai_s: float | None = None) -> None:
        with self._global:
            verrou = self._verrous[hote]
        with verrou:
            reste = self._dernier.get(hote, 0) + (delai_s or self.delai_s) - time.monotonic()
            if reste > 0:
                time.sleep(reste)
            self._dernier[hote] = time.monotonic()


class ClientHttp:
    def __init__(self, *, delai_s: float | None = None) -> None:
        h = config_idf().http
        self._tentatives = h.tentatives
        self._cadence = Cadence(h.delai_min_s if delai_s is None else delai_s)
        self._client = httpx.Client(
            headers={"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"},
            timeout=httpx.Timeout(h.timeout_s, connect=20),
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ClientHttp:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------ requêtes
    def requete(self, methode: str, url: str, **kw: Any) -> httpx.Response:
        """Requête avec reprises ; lève httpx.HTTPStatusError pour toute réponse >= 400 finale."""
        hote = urlsplit(url).netloc
        derniere: Exception | None = None
        for essai in range(self._tentatives):
            self._cadence.attendre(hote)
            try:
                r = self._client.request(methode, url, **kw)
            except httpx.TransportError as e:
                derniere = e
            else:
                if r.status_code not in A_REESSAYER:
                    r.raise_for_status()
                    return r
                derniere = httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                attente = r.headers.get("retry-after", "")
                if attente.isdigit():
                    time.sleep(min(int(attente), 60))
                    continue
            time.sleep(min(2**essai, 20))
        assert derniere is not None
        raise derniere

    def get(self, url: str, **kw: Any) -> httpx.Response:
        return self.requete("GET", url, **kw)

    def json(self, url: str, **kw: Any) -> Any:
        return self.get(url, **kw).json()

    @contextmanager
    def flux(self, url: str) -> Iterator[httpx.Response]:
        """Lecture en flux, sans rien écrire sur disque (fichiers contenant des données personnelles)."""
        self._cadence.attendre(urlsplit(url).netloc)
        with self._client.stream("GET", url, timeout=httpx.Timeout(300, connect=20)) as r:
            r.raise_for_status()
            yield r

    def plage(self, url: str, debut: int, fin: int) -> bytes:
        """Octets [debut, fin] inclus, par requête Range."""
        r = self.get(url, headers={"Range": f"bytes={debut}-{fin}", "Accept-Encoding": "identity"})
        if r.status_code != 206:
            raise RuntimeError(f"{url} : le serveur ignore les requêtes partielles")
        return r.content

    def taille(self, url: str) -> int:
        return int(self.requete("HEAD", url, headers={"Accept-Encoding": "identity"}).headers["content-length"])

    # ------------------------------------------------------------------ fichiers open data
    def telecharger(self, url: str, nom: str) -> Path:
        """Télécharge vers data/brut/<nom> ; ne retélécharge pas un fichier inchangé (ETag / Last-Modified).

        Réservé aux fichiers sans donnée personnelle : les autres passent par flux() ou plage().
        """
        cible = dossier_donnees() / "brut" / nom
        cible.parent.mkdir(parents=True, exist_ok=True)
        fiche = cible.with_name(cible.name + ".meta.json")
        entetes: dict[str, str] = {}
        if cible.exists() and fiche.exists():
            meta = json.loads(fiche.read_text())
            if meta.get("url") == url:
                if meta.get("etag"):
                    entetes["If-None-Match"] = meta["etag"]
                elif meta.get("last_modified"):
                    entetes["If-Modified-Since"] = meta["last_modified"]
        derniere: Exception | None = None
        for essai in range(self._tentatives):
            self._cadence.attendre(urlsplit(url).netloc)
            try:
                with self._client.stream(
                    "GET", url, headers=entetes, timeout=httpx.Timeout(300, connect=20)
                ) as r:
                    if r.status_code == 304:
                        return cible
                    r.raise_for_status()
                    partiel = cible.with_name(cible.name + ".partiel")
                    with partiel.open("wb") as f:
                        for bloc in r.iter_bytes(1 << 20):
                            f.write(bloc)
                    partiel.replace(cible)
                    fiche.write_text(json.dumps({
                        "url": url,
                        "etag": r.headers.get("etag"),
                        "last_modified": r.headers.get("last-modified"),
                        "telecharge_le": datetime.now(UTC).isoformat(timespec="seconds"),
                    }))
                    return cible
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code not in A_REESSAYER:
                    raise
                derniere = e
                time.sleep(min(2**essai, 20))
        assert derniere is not None
        raise derniere
