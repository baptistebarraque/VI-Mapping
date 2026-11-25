"""Extraction d'une page : titre, texte utile, liens, date. Aucun contenu n'est conservé en base."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urldefrag, urljoin

from selectolax.lexbor import LexborHTMLParser

from ..outils.texte import normaliser, propre

HORS_CONTENU = (
    "script, style, noscript, svg, iframe, form, nav, header, footer, aside, "
    "[role=navigation], [role=banner], [role=contentinfo], .menu, .navbar, .breadcrumb, .cookie, .cookies, "
    "#menu, #header, #footer, .footer, .sidebar, .widget, .related"
)
BLOCS = {"p", "li", "div", "td", "th", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "br", "dt", "dd",
         "figcaption", "blockquote", "span"}
_META_DATES = [
    "article:modified_time", "og:updated_time", "dcterms.modified", "dc.date.modified", "last-modified",
    "datemodified", "article:published_time", "dcterms.date", "dc.date", "datepublished", "date",
]
_NOMS_MOIS = (
    "janvier", "fevrier", "mars", "avril", "mai", "juin",
    "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
)
_MOIS = {m: i for i, m in enumerate(_NOMS_MOIS, 1)}
_JSON_LD = re.compile(r'"date(?:Modified|Published)"\s*:\s*"(\d{4}-\d{2}-\d{2})')
_ISO = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
_TEXTE_DATE = re.compile(
    r"\b(?:publie|mis a jour|mise a jour|modifie|derniere modification|derniere mise a jour|mise en ligne"
    r"|poste|actualise)(?: le| du| l)? ?(?:lundi |mardi |mercredi |jeudi |vendredi |samedi |dimanche )?"
    rf"(\d{{1,2}})(?:er)? (\d{{1,2}}|{'|'.join(_NOMS_MOIS)}) (20\d{{2}})"
)


@dataclass(frozen=True)
class Contenu:
    titre: str
    titres: str                        # titre + h1/h2, normalisés
    texte: str                         # texte utile normalisé
    lignes: tuple[str, ...]            # texte utile, une ligne par bloc (pour les délégations)
    liens: tuple[tuple[str, str], ...]  # (url absolue, libellé)
    date: date | None
    date_origine: str | None
    noindex: bool


def extraire(html: str, url: str, *, aujourdhui: date | None = None) -> Contenu:
    aujourdhui = aujourdhui or date.today()
    arbre = LexborHTMLParser(html)
    meta = {}
    for m in arbre.css("meta"):
        a = m.attributes
        cle = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
        if cle and cle not in meta:
            meta[cle] = a.get("content") or ""
    balise = arbre.css_first("title")
    titre = propre(meta.get("og:title")) or (propre(balise.text()) if balise else None) or ""

    base = arbre.css_first("base[href]")
    racine = urljoin(url, base.attributes["href"] or "") if base else url
    liens = []
    for a in arbre.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if href and not href.lower().startswith(("mailto:", "tel:", "javascript:", "#")):
            try:
                liens.append((urldefrag(urljoin(racine, href))[0], propre(a.text(separator=" ")) or ""))
            except ValueError:
                continue

    jour, origine = _date_meta(arbre, meta, html, aujourdhui)
    for n in arbre.css(HORS_CONTENU):
        n.decompose()
    corps = arbre.css_first("main, [role=main], #content, #main, article") or arbre.body
    if corps is not None and arbre.body is not None and len(corps.text()) < 200:
        corps = arbre.body
    lignes = _lignes(corps) if corps is not None else []
    titres = " ".join([titre, *(t.text(separator=" ") for t in arbre.css("h1, h2")[:12])])
    texte = normaliser(" \n".join(lignes))
    if jour is None and (jour := date_dans_texte(texte, aujourdhui)):
        origine = "texte"
    return Contenu(
        titre=titre[:200], titres=normaliser(titres), texte=texte, lignes=tuple(lignes), liens=tuple(liens),
        date=jour, date_origine=origine, noindex="noindex" in meta.get("robots", "").lower(),
    )


def _lignes(corps) -> list[str]:  # type: ignore[no-untyped-def]
    brut = corps.text(separator="\n", strip=False)
    return [t for t in (propre(x) for x in brut.split("\n")) if t]


def _jour(annee: int, mois: int, j: int, aujourdhui: date) -> date | None:
    try:
        d = date(annee, mois, j)
    except ValueError:
        return None
    return d if date(2005, 1, 1) <= d <= aujourdhui else None


def iso(texte: str | None, aujourdhui: date) -> date | None:
    m = _ISO.search(texte or "")
    return _jour(int(m[1]), int(m[2]), int(m[3]), aujourdhui) if m else None


def _date_meta(arbre, meta: dict[str, str], html: str, aujourdhui: date) -> tuple[date | None, str | None]:  # type: ignore[no-untyped-def]
    for cle in _META_DATES:
        if d := iso(meta.get(cle), aujourdhui):
            return d, "meta"
    dates = [d for d in (iso(t, aujourdhui) for t in _JSON_LD.findall(html)) if d]
    if dates:
        return max(dates), "meta"
    for t in arbre.css("main time[datetime], article time[datetime], time[pubdate]")[:3]:
        if d := iso(t.attributes.get("datetime"), aujourdhui):
            return d, "meta"
    return None, None


def date_dans_texte(texte: str, aujourdhui: date) -> date | None:
    """Date annoncée dans un texte normalisé : « publié le 12 mars 2026 », « mis à jour le 3 04 2026 »."""
    dates = []
    for j, mois, annee in _TEXTE_DATE.findall(texte):
        m = _MOIS.get(mois) or (int(mois) if mois.isdigit() else 0)
        if d := _jour(int(annee), m, int(j), aujourdhui):
            dates.append(d)
    return max(dates) if dates else None


def date_la_plus_recente(html: str, contenu: Contenu, aujourdhui: date) -> date | None:
    """Dernière activité visible d'un site : la plus récente des dates affichées (articles d'un blog, etc.)."""
    dates = [contenu.date] if contenu.date else []
    dates += [d for d in (iso(t, aujourdhui) for t in _JSON_LD.findall(html)) if d]
    dates += [d for d in (iso(t, aujourdhui) for t in re.findall(r'<time[^>]+datetime="([^"]+)"', html)) if d]
    for j, mois, annee in re.findall(rf"\b(\d{{1,2}})(?:er)? ({'|'.join(_MOIS)}) (20\d{{2}})\b", contenu.texte):
        if d := _jour(int(annee), _MOIS[mois], int(j), aujourdhui):
            dates.append(d)
    for j, mois, annee in re.findall(r"\b(\d{2})/(\d{2})/(20\d{2})\b", " ".join(contenu.lignes)):
        if d := _jour(int(annee), int(mois), int(j), aujourdhui):
            dates.append(d)
    return max(dates) if dates else None
