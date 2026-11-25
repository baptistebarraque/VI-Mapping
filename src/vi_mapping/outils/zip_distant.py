"""Lecture d'un membre d'une archive ZIP distante par requêtes partielles, sans rien écrire sur disque."""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections.abc import Iterator

from .http import ClientHttp

BLOC = 4 << 20
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


class FichierDistant(io.RawIOBase):
    """Fichier en lecture seule et positionnable, lu par blocs avec l'en-tête HTTP Range."""

    def __init__(self, http: ClientHttp, url: str) -> None:
        self._http, self._url = http, url
        self._taille = http.taille(url)
        self._pos = 0
        self._blocs: dict[int, bytes] = {}

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self._taille}[whence]
        self._pos = max(0, base + offset)
        return self._pos

    def readinto(self, tampon) -> int:  # type: ignore[no-untyped-def]
        if self._pos >= self._taille:
            return 0
        n = self._pos // BLOC
        if n not in self._blocs:
            if len(self._blocs) >= 4:  # quelques blocs en mémoire suffisent à une lecture séquentielle
                self._blocs.pop(next(iter(self._blocs)))
            debut = n * BLOC
            self._blocs[n] = self._http.plage(self._url, debut, min(debut + BLOC, self._taille) - 1)
        morceau = self._blocs[n][self._pos - n * BLOC :][: len(tampon)]
        tampon[: len(morceau)] = morceau
        self._pos += len(morceau)
        return len(morceau)


def ouvrir(http: ClientHttp, url: str) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BufferedReader(FichierDistant(http, url), 1 << 20))  # type: ignore[arg-type]


def lignes_csv(archive: zipfile.ZipFile, membre: str, *, delimiteur: str = ";") -> Iterator[dict[str, str]]:
    with archive.open(membre) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, "utf-8-sig", newline=""), delimiter=delimiteur)
