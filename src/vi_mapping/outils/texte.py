"""Normalisation de textes et nettoyage des données personnelles."""

from __future__ import annotations

import re
import unicodedata

_EMAIL = re.compile(r"[\w.+-]+\s?(?:@|\[at\]|\(at\))\s?[\w-]+(?:\.[\w-]+)+", re.I)
_TEL = re.compile(r"(?<!\d)(?:(?:\+|00)33[\s.\-]?(?:\(0\)\s?)?|0)[1-9](?:[\s.\-]?\d{2}){4}(?!\d)")
# « chez M. Dupont », « c/o Mme X », « Mme X » en complément d'adresse
_CHEZ = re.compile(
    r"\b(?:chez|c/o|c/ ?o\.?|a l.attention de|attn?\.?)\b[^,;]*"
    r"|\b(?:m|mr|mme|mlle|monsieur|madame|mademoiselle)\b\.?\s+[^,;]*",
    re.I,
)
_ESPACES = re.compile(r"\s+")


def sans_accents(texte: str) -> str:
    texte = texte.replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae")
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def normaliser(texte: str | None) -> str:
    """Minuscules, sans accents ni ponctuation, espaces simples."""
    if not texte:
        return ""
    t = sans_accents(reparer(texte)).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return _ESPACES.sub(" ", t).strip()


_CONTROLES_C1 = re.compile(r"[\x80-\x9f]")


def reparer(texte: str) -> str:
    """Rend leur valeur windows-1252 aux caractères de contrôle C1 (« d\x92élèves », « \x9cuvre »)."""
    return _CONTROLES_C1.sub(lambda m: m.group().encode("latin-1").decode("cp1252", "replace"), texte)


def propre(texte: str | None) -> str | None:
    """Espaces réduits, caractères réparés ; None si vide."""
    if texte is None:
        return None
    t = _ESPACES.sub(" ", reparer(str(texte))).strip()
    return t or None


def sans_contact(texte: str | None) -> str | None:
    """Retire e-mails et numéros de téléphone d'un texte libre."""
    if texte is None:
        return None
    return propre(_TEL.sub("", _EMAIL.sub("", texte)))


def contient_contact(texte: str | None) -> bool:
    return bool(texte) and bool(_EMAIL.search(texte) or _TEL.search(texte))


def adresse_sans_personne(texte: str | None) -> str | None:
    """Retire d'une adresse les mentions de personnes (« chez Mme X ») et les contacts."""
    if texte is None:
        return None
    t = sans_contact(_CHEZ.sub("", texte))
    return propre(t.strip(" ,;-")) if t else None


_PETITS_MOTS = {
    "de", "du", "des", "la", "le", "les", "et", "en", "sur", "sous", "aux", "au", "a", "à", "pour", "lès", "ou",
}
_ELISIONS = {"d'", "l'", "qu'", "n'", "s'", "jusqu'"}


def titre(texte: str | None) -> str | None:
    """« ECOLE D'APPLICATION » -> « Ecole d'Application » (laisse intacts les textes déjà en casse mixte)."""
    t = propre(texte)
    if t is None or t != t.upper():
        return t
    mots = []
    for i, mot in enumerate(t.lower().replace("’", "'").split(" ")):
        morceaux = []
        for j, m in enumerate(re.split(r"(?<=[-'/])", mot)):
            nu = m.strip("-")
            petit = (nu in _PETITS_MOTS or nu in _ELISIONS) and (i > 0 or j > 0)
            # première lettre, même précédée de « ( » ou de guillemets
            morceaux.append(m if petit else re.sub(r"[^\W\d_]", lambda x: x.group().upper(), m, count=1))
        mots.append("".join(morceaux))
    return " ".join(mots)


_TYPES_VOIE = {
    "all": "allée", "av": "avenue", "bd": "boulevard", "bld": "boulevard", "car": "carrefour", "che": "chemin",
    "chs": "chaussée", "cite": "cité", "cor": "corniche", "crs": "cours", "dom": "domaine", "esp": "esplanade",
    "fg": "faubourg", "gr": "grande rue", "ham": "hameau", "hle": "halle", "imp": "impasse", "ld": "lieu-dit",
    "lot": "lotissement", "mar": "marché", "mte": "montée", "pas": "passage", "pl": "place", "pln": "plaine",
    "plt": "plateau", "prom": "promenade", "prv": "parvis", "qua": "quartier", "quai": "quai", "res": "résidence",
    "rle": "ruelle", "roc": "rocade", "rpt": "rond-point", "rte": "route", "rue": "rue", "sen": "sentier",
    "sq": "square", "tpl": "terre-plein", "tra": "traverse", "vla": "villa", "vlge": "village", "za": "ZA",
    "zac": "ZAC", "zi": "ZI", "zup": "ZUP", "parc": "parc", "pte": "porte", "cour": "cour", "ave": "avenue",
}


def nom_voie(type_: str | None, libelle: str | None) -> str | None:
    """« RUE », « DE LA SABLIERE » → « rue de la Sabliere »."""
    nom = titre(libelle)
    if nom and type_:
        nom = re.sub(r"^(?:De|Du|Des|D['’]|La|Le|Les|L['’])(?=[\s'’A-ZÀ-Ý]|$)", lambda m: m.group().lower(), nom)
    return propre(" ".join(m for m in (type_voie(type_), nom) if m))


def type_voie(abrege: str | None) -> str | None:
    """« AV » -> « avenue » ; mot inconnu rendu en minuscules."""
    t = propre(abrege)
    return _TYPES_VOIE.get(t.lower(), t.lower()) if t else None


_HOTE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")
_RESEAUX_SOCIAUX = re.compile(
    r"(^|\.)(facebook|fb|instagram|twitter|x|linkedin|youtube|tiktok|threads|whatsapp|linktr|helloasso)\.(com|fr|ee|me)$"
)


def site_web(brut: str | None, *, reseaux_sociaux: bool = False) -> str | None:
    """Adresse http(s) valable tirée d'un champ libre ; None pour un e-mail, un texte ou un réseau social."""
    t = (propre(brut) or "").strip(" .;,")
    if not t or "@" in t or " " in t:
        return None
    if "://" not in t:
        t = f"https://{t}"
    schema, _, reste = t.partition("://")
    hote = re.split(r"[/?#:]", reste, maxsplit=1)[0].lower()
    if schema.lower() not in ("http", "https") or not _HOTE.match(hote):
        return None
    if not reseaux_sociaux and _RESEAUX_SOCIAUX.search(hote):
        return None
    return f"{schema.lower()}://{hote}{reste[len(hote):]}"
