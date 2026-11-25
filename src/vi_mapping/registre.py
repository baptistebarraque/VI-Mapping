"""Registre des sources en Markdown (docs/SOURCES.md), tiré de config/sources.yaml."""

from __future__ import annotations

from .config import SourceConfig, config_sources

INTRODUCTION = """\
# Sources

Produit depuis `config/sources.yaml` par `uv run vi sources --markdown > docs/SOURCES.md`.

Aucune saisie manuelle. Open data et API d'abord, scraping ensuite, et seulement là où robots.txt et les conditions
d'utilisation le permettent. Chaque ligne en base porte `source`, `url`, `methode`, `collecte_le` et `confiance`.

## Règles du robot

- **Identifié** : nom, version et contact (`VI_CONTACT`) dans le user-agent. Sans contact, un échantillon par mois.
- **robots.txt** lu avant chaque site. Illisible (401, 403, 429, 5xx) : le site n'est pas visité.
- **Réserve de fouille** (TDM : en-tête, balise, `tdmrep.json`) respectée.
- **Cadence** : un délai entre deux pages d'un même site, allongé si robots.txt le demande. Nombre de pages plafonné.
- **Anti-robot, captcha, refus** : arrêt immédiat, sans nouvelle tentative ni contournement, et trace dans `crawl_site`.
- **Réseaux sociaux** jamais visités. **Contenu** des pages jamais conservé : URL, titre, date, thème seulement.

## Données personnelles

- Élus municipaux seulement (RNE) : nom, fonction, début de mandat, délégation. Aucune étiquette politique.
- Aucun e-mail ni téléphone en base (`uv run vi verifier` le contrôle).
- Adresses « chez M. ou Mme X » nettoyées. Exploitants individuels sans nom commercial anonymisés.
- Familles : données agrégées par IRIS.
"""

GROUPES = (
    ("Open data et API", lambda s: not s.verrouillee and s.methode in ("api", "csv")),
    ("Scraping", lambda s: not s.verrouillee and s.methode == "scraping"),
    ("Calculs", lambda s: s.methode == "calcul"),
)


def _ligne(code: str, s: SourceConfig) -> str:
    libelle = f"[{s.libelle}]({s.url})" if s.url.startswith("http") else f"{s.libelle} (`{s.url}`)"
    return f"| `{code}` | {libelle} | {s.producteur} | {s.alimente} | {s.methode} | {s.frequence} | {s.licence} |"


def markdown() -> str:
    sources = config_sources()
    t = [INTRODUCTION]
    for titre, filtre in GROUPES:
        choisies = {c: s for c, s in sources.items() if filtre(s)}
        t += [f"## {titre}", "", "| Code | Source | Producteur | Alimente | Méthode | Mise à jour | Licence |",
              "|---|---|---|---|---|---|---|", *(_ligne(c, s) for c, s in choisies.items()), ""]
        for c, s in choisies.items():
            if s.verification:
                t.append(f"- `{c}`, vérifié le {s.verification.le:%d/%m/%Y} : {_phrase(s.verification.constat)}")
        if t[-1]:
            t.append("")
    t += ["## Sources verrouillées", "",
          "Leurs conditions interdisent l'extraction automatique. Le moteur refuse de les collecter, et tous les "
          "robots refusent leurs domaines, tant que `autorisation` (date et référence d'un accord écrit) n'est pas "
          "renseignée dans `config/sources.yaml`.", ""]
    for c, s in sources.items():
        if s.verrouillee and (v := s.verification):
            t += [f"### {s.libelle}", "", f"- Code : `{c}`. Aurait alimenté : {s.alimente}."]
            t.append(f"- Conditions ({v.cgu_url}), lues le {v.le:%d/%m/%Y} : {_phrase(v.constat)}" if v.cgu_url
                     else f"- Lu le {v.le:%d/%m/%Y} : {_phrase(v.constat)}")
            if v.robots:
                t.append(f"- robots.txt : {v.robots}.")
            if v.anti_robot:
                t.append(f"- Anti-robot : {v.anti_robot}.")
            t.append(f"- Domaines refusés : {', '.join(s.hotes)}.")
            if v.remplacement:
                t.append(f"- Remplacée par : {', '.join(f'`{x}`' for x in v.remplacement)}.")
            if v.demarche:
                t.append(f"- Démarche : {v.demarche}")
            t.append("")
    return "\n".join(t).rstrip() + "\n"


def _phrase(texte: str) -> str:
    return " ".join(texte.split())
