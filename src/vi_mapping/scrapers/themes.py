"""Thèmes recherchés sur les sites des mairies : motifs, choix des pages à visiter, délégations d'élus.

Tous les motifs s'appliquent à un texte normalisé (minuscules, sans accent ni ponctuation).
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from ..outils.texte import normaliser, propre, sans_contact

_PRODUITS = (
    r"(produits?|repas|menus?|aliments?|legumes?|fruits?|pain|viandes?|laitages?|denrees?|ingredients?|paniers?)"
)
THEMES: dict[str, re.Pattern[str]] = {
    "bio": re.compile(
        rf"\b{_PRODUITS} ((100|issus?|labellises?|locaux|et|de saison|frais|principalement|majoritairement) ){{0,3}}"
        r"(bio|biologiques?|de l agriculture biologique)\b"
        r"|\bagriculture biologique\b|\b\d{1,3} (de )?(produits |aliments |denrees |d aliments |de produits )?"
        r"(bio|biologiques?)\b|\b(cantines?|restauration|cuisine) (scolaire )?(100 )?bio\b|\bbio et (locale?|locaux)\b"
        r"|\bproduits? labellises? ab\b"
    ),
    "anti_gaspi": re.compile(r"\banti ?gaspi(llage)?\b|\bgaspillage alimentaire\b|\bzero gaspi(llage)?\b"),
    "potager": re.compile(
        r"\bpotagers?\b(?! du roi)|\bjardins? (pedagogiques?|scolaires?|d ecole|de l ecole)\b"
        r"|\bfermes? (pedagogiques?|urbaines?)\b"
    ),
    "education_gout": re.compile(
        r"\beducation (au gout|alimentaire|a l alimentation|nutritionnelle)\b|\bsemaine (nationale )?du gout\b"
        r"|\beveil (au|du) gout\b|\bclasses? du gout\b|\bateliers? (du gout|de cuisine|cuisine|culinaires?|nutrition)\b"
        r"|\bdecouverte (du gout|des saveurs|de nouvelles saveurs)\b|\blecons? de gout\b"
    ),
    "alimentation_durable": re.compile(
        r"\balimentation (plus )?(durable|responsable|saine|de qualite|locale|de proximite)\b|\begalim\b"
        r"|\bprojet alimentaire territorial\b|\bcircuits? courts?\b|\bprecarite alimentaire\b"
        r"|\b(menu|repas|journee)s? vegetarien(ne)?s?\b|\bplan alimentaire\b"
        r"|\bagriculture (locale|urbaine|de proximite)\b"
    ),
    "periscolaire_soir": re.compile(
        r"\baccueils? (peri ?scolaires? )?(du |de )?(matin et (du )?)?soirs?\b"
        r"|\bgarderies? (peri ?scolaires? )?(du )?soir\b"
        r"|\betudes? (surveillees?|dirigees?)\b|\baccueils? (pre et )?post ?scolaires?\b"
        r"|\baccueils? peri ?scolaires?\b|\bapres la classe\b|\bapres l ecole\b"
    ),
    "periscolaire_mercredi": re.compile(
        r"\bmercredis?\b.{0,90}\b(accueils?|centres?) de loisirs?\b"
        r"|\b(accueils?|centres?) de loisirs?\b.{0,90}\bmercredis?\b"
        r"|\bplan mercredi\b|\baccueils? (de loisirs? )?(du|le|les) mercredis?\b|\bmercredis? (loisirs?|educatifs?)\b"
    ),
}
ALIMENTAIRES = ("bio", "anti_gaspi", "potager", "education_gout", "alimentation_durable")

# Pages à visiter : (catégorie, motif sur l'URL et le libellé du lien, poids, pages au plus)
CATEGORIES: list[tuple[str, re.Pattern[str], int, int]] = [
    ("alimentation", re.compile(
        r"gaspi|potager|semaine du gout|\bgout\b|\beducation alimentaire|\begalim\b|alimentation|projet alimentaire"
        r"|circuits? courts?|\bbio\b|biologique|agricultur|\bamap\b"), 10, 7),
    ("cantine", re.compile(r"\bcantines?\b|restauration (scolaire|municipale|collective)|\brestaurants? scolaires?"
                           r"|\bmenus?\b|cuisine centrale|pause meridienne"), 9, 4),
    ("periscolaire", re.compile(r"peri ?scolaire|(accueils?|centres?) de loisirs?|garderie|\bmercredis?\b|\betudes?\b"
                                r"|temps de l enfant"), 8, 6),
    ("elus", re.compile(r"\belus?\b|\belues\b|equipe municipale|trombinoscope|\badjoints?\b|le maire et"
                        r"|bureau municipal|delegations?\b|conseillers municipaux|conseil municipal$"), 7, 5),
    ("ecole", re.compile(r"\becoles?\b|scolaire|\beducation\b|\benfance\b"), 4, 3),
    ("ecologie", re.compile(r"developpement durable|transition|environnement|ecologi|agenda 2030|agenda 21"), 3, 2),
]
_EXTENSIONS = re.compile(r"\.(pdf|jpe?g|png|gif|webp|svg|docx?|xlsx?|odt|zip|mp[34]|ics|xml|rss|css|js)$", re.I)
_A_EVITER = re.compile(
    r"/wp-(json|admin|login|content)|/feed/?$|[?&](print|share|replytocom|lang|format|tmpl|task|add-to-cart)="
    r"|/(login|connexion|compte|panier|recherche|search|mentions-legales|politique|cookies|plan-du-site)\b",
    re.I,
)


def est_document(url: str) -> bool:
    return bool(re.search(r"\.(pdf|docx?|odt)$", urlsplit(url).path, re.I))


def visitable(url: str) -> bool:
    return not _EXTENSIONS.search(urlsplit(url).path) and not _A_EVITER.search(url)


def mots_url(url: str) -> str:
    return normaliser(unquote(urlsplit(url).path))


# Séances, délibérations, permanences : pas des pages de présentation des élus
_ACTES = re.compile(
    r"\bseances?\b|\bdeliberations?\b|\bproces verb|\bcomptes? rendus?\b|\bordres? du jour\b|\bpermanences?\b"
    r"|\bconseil municipal (du|des) (enfants|jeunes|\d)|\barretes?\b|\bmarches? publics?\b|\brecrut|\boffres? d emploi"
)


def classer(url: str, libelle: str) -> tuple[str, int] | None:
    """(catégorie, poids) d'un lien à visiter, ou None s'il n'a pas l'air utile."""
    chemin, texte = mots_url(url), normaliser(libelle)[:150]
    for nom, motif, poids, _ in CATEGORIES:
        if motif.search(chemin) or motif.search(texte):
            if nom == "elus" and _ACTES.search(f"{chemin} {texte}"):
                continue
            return nom, poids
    return None


def themes_de(texte: str) -> dict[str, int]:
    """Nombre d'occurrences de chaque thème présent."""
    trouves = {t: len(m.findall(texte)) for t, m in THEMES.items()}
    return {t: n for t, n in trouves.items() if n}


def type_page(url: str, titres: str) -> str:
    if est_document(url):
        return "document"
    chemin = mots_url(url)
    if re.search(r"\bmenus?\b", chemin) and re.search(r"\bcantine|restauration|scolaire", f"{chemin} {titres}"):
        return "menu"
    if re.search(r"\bagenda\b|\bevenements?\b|\bevents?\b", chemin):
        return "agenda"
    if re.search(r"\bactu|\bnews\b|\barticles?\b|\bblog\b|\bmagazine\b", chemin):
        return "actualite"
    return "page"


# ----------------------------------------------------------------- délégations des élus
DELEGATIONS: dict[str, re.Pattern[str]] = {
    "scolaire": re.compile(r"\bscolaires?\b|\becoles?\b|\beducation\b|\benseignement\b|\beducati(f|ve)s?\b"),
    "restauration": re.compile(
        r"\brestauration\b|\bcantines?\b|\balimentation\b|\balimentaires?\b|\bcuisine centrale\b"),
    "enfance_jeunesse": re.compile(r"\benfance\b|\bjeunesse\b|\bfamilles?\b|\bparentalite\b|\bperi ?scolaires?\b"),
    "transition_ecologique": re.compile(
        r"\btransition\b|\becologi\w*|\bdeveloppement durable\b|\benvironnement\w*|\bclimat\w*|\bbiodiversite\b"),
    "agriculture": re.compile(r"\bagricol\w*|\bagriculture\b|\bruralite\b|\bcircuits? courts?\b"),
    "vie_associative": re.compile(r"\bassociati(f|ve)s?\b|\bassociations?\b"),
}
_FONCTION = re.compile(
    r"\b(maire|adjointe?|adjoints|conseill\w+ (municipal\w* )?deleguee?|delegue\w*|delegation|en charge|chargee?)\b")


_HABILLAGE = re.compile(
    r"\b(en savoir plus|lire la suite|contacter?|voir (la fiche|plus)|plus d'infos?|envoyer un (message|mail|e-mail)"
    r"|prendre rendez-vous|sur rendez-vous|retour|biographie|écrire (à|au) \S+|lui écrire|présidente? (du|de) groupe)\b"
    r"|\b(courriel|e-mail|mail|téléphone|tél\.?|élus?,? élus de|élus de la|groupe politique|permanences?"
    r"|voir l['’]image|fiche de présentation|vous reçoit|(les )?conseill(er|ère)s? municipa(ux|les))\b.*$"
    r"|\bélus$|(?-i:\bVille de [A-ZÉÈ][\w'’-]+)$", re.I)
# Étiquette ou liste politique : donnée sensible sans utilité ici, jamais conservée
_ETIQUETTE = re.compile(
    r"\b([ée]lue?s? )?(de l['’]|de la |de )?(majorité|opposition)( municipale)?\b(\s*[«\"“].*$)?"
    r"|\bgroupe (majoritaire|d'opposition)\b|\bsociété civile\b"
    r"|(?-i:\bGroupe\s+[«\"“]?\s?(?!Scolaire)[A-ZÉ]).*$|\bliste\s+[«\"“].*$|(?-i:\bListe\s+[A-ZÉ]).*$"
    r"|\bparti (socialiste|communiste( français)?|radical\w*|animaliste|pirate)\b|\bles républicains\b"
    r"|\b(la )?france insoumise\b|\b(europe écologie|eelv)( les verts)?\b"
    r"|\bles (écologistes|verts|centristes)\b|\brenaissance\b|\bmodem\b|\bhorizons\b|\brassemblement national\b"
    r"|\breconquête\b|\bplace publique\b|\bgénération[.·]?s\b|\bdivers (gauche|droite|centre)\b|\bsans étiquette\b"
    r"|\b(PS|PCF|LR|LFI|UDI|RN|DVG|DVD|DVC)\b",
    re.I,
)
_DEBUT_FONCTION = re.compile(
    r"(\b\d{1,2}\s?(?:er|ère|re|e|ème|ᵉ|ᵉʳ|ʳᵉ)?\s+)?\b(premi(?:er|ère)\s+|deuxième\s+)?"
    r"(adjointe?s?|maire|conseill\w+|délégu\w+|délégation|en charge|chargée?)\b", re.I)


def delegations_de(texte: str) -> list[str]:
    n = normaliser(texte)
    return [t for t, m in DELEGATIONS.items() if m.search(n)]


def lire_delegations(lignes: tuple[str, ...], elus: dict[str, tuple[str, str]]) -> dict[str, tuple[str, list[str]]]:
    """Délégation de chaque élu nommé dans la page : {id: (texte court, thèmes)}.

    `elus` : {id: (prénom normalisé, nom normalisé)}. On lit la fin de la ligne qui porte le nom et les trois
    lignes suivantes, sans dépasser le nom d'un autre élu.
    """
    normales = [normaliser(x) for x in lignes]
    noms = {
        id_: re.compile(rf"\b({re.escape(p)} {re.escape(n)}|{re.escape(n)} {re.escape(p)})\b")
        for id_, (p, n) in elus.items() if p and n
    }
    tous = re.compile("|".join(m.pattern for m in noms.values())) if noms else None
    resultat: dict[str, tuple[str, list[str]]] = {}
    if tous is None:
        return resultat
    porteuses = [i for i, ligne in enumerate(normales) if len(ligne) < 400 and tous.search(ligne)]
    for i in porteuses:
        for id_, motif in noms.items():
            m = motif.search(normales[i])
            if not m or id_ in resultat:
                continue
            # Plusieurs élus sur la même ligne : impossible d'attribuer la délégation.
            if len(set(tous.findall(normales[i]))) > 1 and len(list(tous.finditer(normales[i]))) > 1:
                continue
            suite = [lignes[i]]
            for j in range(i + 1, min(i + 4, len(lignes))):
                if tous.search(normales[j]):
                    break
                suite.append(lignes[j])
            # Le rôle précède parfois le nom (« Adjointe à l'éducation : Prénom NOM »).
            texte = delegation_propre(" ".join(suite), elus[id_])
            themes = delegations_de(texte)
            if themes and _FONCTION.search(normaliser(" ".join(suite))):
                resultat[id_] = (texte, themes)
    return resultat


def delegation_propre(texte: str, elu: tuple[str, str]) -> str:
    """Fonction et délégation seules : sans le nom de l'élu, sans contact ni étiquette politique ; 200 caractères."""
    mots = set(f"{elu[0]} {elu[1]}".split())
    gardes = [
        m for m in (sans_contact(texte) or "").split(" ")
        if not (normaliser(m) and set(normaliser(m).split()) <= mots)
    ]
    propre_ = _ETIQUETTE.sub(" ", _HABILLAGE.sub(" ", propre(" ".join(gardes)) or ""))
    if (m := _DEBUT_FONCTION.search(propre_)) and m.start() < 60:
        propre_ = propre_[m.start():]
    # « … à l'éducation 3ème adjointe » : le titre de l'élu suivant
    if suivant := re.search(r"\s\d{1,2}\s?(?:er|ère|e|ème|ᵉ|ʳᵉ)\s+adjoint", propre_[20:]):
        propre_ = propre_[: 20 + suivant.start()]
    # « … au personnel. Prénom NOM Conseillère municipale, déléguée à la santé » : la délégation d'une autre personne
    if suivant := re.search(r"\bconseill(?:er|ère)\s+municipale?\b", propre_[30:], re.I):
        propre_ = re.sub(r"(?:\s+[A-ZÉÈ][\w'’-]+){1,3}\s*$", "", propre_[: 30 + suivant.start()].rstrip())
    propre_ = re.sub(r"\s+(?:les )?adjoints?(?: au maire)?$", "", propre_, flags=re.I)
    propre_ = re.sub(r"^(?:M\.|Mme|Mlle|Monsieur|Madame)\s*", "", propre(propre_) or "").strip(" :,;–-|•")
    return re.sub(r"\s+\d{1,2}$", "", propre_)[:200].rstrip()
