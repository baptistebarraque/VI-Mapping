/** Fiche d'une collectivité : identité, cantine, dispositifs, élus, signaux du site, écoles. */

import { chargerActeurs } from '../donnees';
import type { Modele } from '../modele';
import {
  CRITERES_COMMUNES, JAUGES, type Acteur, type CritereCommune, type Dispositif, type Elu, type Fiche, type FicheCommune,
  type FicheEcole, type NatureFichier,
} from '../types';
import {
  ACTEUR_CRITERE, anneau, bloc, definition, etiquette, listeRepliee, metre, provenance, tableSources, vide, volet,
} from './commun';
import { blocContact } from './contact';
import { bouton, boutonActeur, boutonEcole, montrerBloc, type ContexteFiche } from './contexte';
import { h, lien, remplacer } from './dom';
import {
  date, LIBELLE_CATEGORIE_ALIMENTATION, LIBELLE_CRITERE_COMMUNE, LIBELLE_CUISINE, LIBELLE_DISPOSITIF, LIBELLE_GESTION,
  LIBELLE_GESTIONNAIRE, LIBELLE_JAUGE, LIBELLE_NATURE, LIBELLE_ORGANISME, LIBELLE_PAGE, LIBELLE_RELAIS, LIBELLE_THEME,
  LIBELLE_VISITE, nombre, pluriel, pourcent,
} from './format';

/** Soutiens, lauréats MGP et syndicats : bloc à part, pas dans la liste des dispositifs. */
const SOUTIENS = new Set<Dispositif['type']>(['soutien_territorial', 'laureat_aap_mgp', 'syndicat_restauration']);

/** Thèmes de délégation utiles au projet, les plus proches d'abord. */
const UTILES = ['restauration', 'scolaire', 'enfance_jeunesse', 'agriculture', 'transition_ecologique'];

/** Élus : le maire et les délégations utiles ; `court` : seulement l'école, la cantine et l'enfance. */
export function listeElus(c: FicheCommune, ctx: ContexteFiche, court = false): HTMLElement {
  const { meta } = ctx.modele;
  const retenus = court ? UTILES.slice(0, 3) : UTILES;
  const rang = (t: string[] | undefined): number => {
    const l = (t ?? []).map((x) => retenus.indexOf(x)).filter((x) => x >= 0);
    return l.length ? Math.min(...l) : 99;
  };
  const maires = (c.elus ?? []).filter((e) => e.fonction.startsWith('Maire'));
  const delegues = (c.elus ?? []).filter((e) => !maires.includes(e) && rang(e.themes) < 99)
    .sort((a, b) => rang(a.themes) - rang(b.themes));
  const adjoints = (c.elus ?? []).filter((e) => !maires.includes(e) && !delegues.includes(e));
  const ligne = (e: Elu): HTMLElement => h(
    'li', {},
    boutonActeur(ctx, 'elu', `${c.code}:${e.id}`, e.nom), ` — ${e.fonction}`,
    e.delegation && h('span', { classe: 'sous' }, e.delegation),
    provenance(e.pd ?? e.p, meta),
  );
  const connues = (c.elus ?? []).some((e) => e.delegation);
  return h(
    'div', {},
    h('h4', {}, 'Élus'),
    maires.length || delegues.length ? h('ul', { classe: 'liste' }, [...maires, ...delegues].map(ligne))
      : vide('Aucun élu trouvé.'),
    !connues && vide('Délégations inconnues : site de la mairie pas encore visité, ou sans page d’élus lisible.'),
    !court && adjoints.length > 0 && h(
      'details', { classe: 'replie' },
      h('summary', {}, `${pluriel(adjoints.length, 'autre élu cité', 'autres élus cités')}`),
      h('ul', { classe: 'liste' }, adjoints.map(ligne)),
    ),
  );
}

/** Nom d'un dispositif, qui ouvre sa fiche et montre son périmètre sur la carte. */
export const boutonDispositif = (d: Dispositif, ctx: ContexteFiche): HTMLElement => bouton(
  ctx, d.type === 'pat' ? { type: 'pat', id: d.id } : { type: 'acteur', nature: 'dispositif', id: d.id }, d.nom, true,
);

export function listeDispositifs(c: FicheCommune, ctx: ContexteFiche, ecole?: FicheEcole): HTMLElement {
  const { meta } = ctx.modele;
  // Pour une école : PAT et appels à projets de la commune ; QPV et cité éducative sont les siens propres.
  const liste = (c.dispositifs ?? []).filter((d) => !SOUTIENS.has(d.type))
    .filter((d) => !ecole || d.type === 'pat' || d.type === 'laureat_aap');
  const laureats = new Set(liste.filter((d) => d.type === 'laureat_aap').map((d) => d.id.split(':')[1]));
  const lignes = liste.filter((d) => d.type !== 'laureat_aap').map((d) => h(
    'li', {},
    boutonDispositif(d, ctx), ' ', etiquette(LIBELLE_DISPOSITIF[d.type]),
    h('span', { classe: 'sous' }, [
      d.type === 'pat' && (d.axe ? 'axe éducation alimentaire' : 'sans axe éducation alimentaire'),
      d.type === 'pat' && d.restauration !== undefined
        && (d.restauration ? 'axe restauration collective' : 'sans axe restauration collective'),
      d.type === 'pat' && laureats.has(d.id.split(':')[1]) && 'lauréat de l’appel à projets du PNA',
      d.niveau, d.annee,
    ].filter(Boolean).join(' · ')),
    d.priorites && h('span', { classe: 'sous' }, d.priorites),
    provenance(d.p, meta),
  ));
  return h('div', {}, h('h4', {}, 'Dispositifs'),
    lignes.length ? listeRepliee(lignes, 6) : vide('Aucun dispositif ne couvre la commune.'));
}

export function ficheCommune(code: string, fiche: Fiche, ctx: ContexteFiche): HTMLElement {
  const { modele } = ctx;
  const { meta } = modele;
  const c = fiche.commune;
  const ecoles = modele.parCommune.get(code) ?? [];
  return h(
    'article', { classe: 'fiche' },
    h('p', { classe: 'surtitre' }, c.type === 'arrondissement' ? 'Arrondissement' : 'Commune'),
    h('h2', {}, c.nom),
    h('p', { classe: 'lieu' }, lieu(c, ctx),
      c.mere && [' · ', bouton(ctx, { type: 'commune', code: c.mere.code }, c.mere.nom)]),
    blocContact(c.contact, ctx),
    resumeCommune(code, c, ctx),
    bloc(
      'Collectivité',
      definition(
        ['Code Insee', c.code],
        c.siren ? ['Siren', c.siren] : null,
        ...(c.organismes ?? []).map((o): [string, HTMLElement | string] => [
          LIBELLE_ORGANISME[o.type], boutonActeur(ctx, 'organisme', o.siren, o.nom, false)]),
        ['Population', c.population === undefined ? 'inconnue'
          : `${nombre(c.population)} habitants${c.population_annee ? ` (${c.population_annee})` : ''}`],
        c.densite === undefined ? null : ['Densité', `${nombre(c.densite)} hab./km²`],
      ),
      provenance(c.p, meta),
    ),
    blocCantine(c, ctx),
    blocSoutiens(c, ctx),
    blocAlimentation(c, ctx),
    volet(DISPOSITIFS, null, listeDispositifs(c, ctx), listeElus(c, ctx)),
    blocSignaux(c, ctx),
    voletActeurs('accueil', c.nb.accueils, code, ctx),
    c.gestionnaires?.length ? volet(LIBELLE_NATURE.gestionnaire[1], c.gestionnaires.length, h('ul', { classe: 'liste' }, c.gestionnaires.map((g) => h(
      'li', {}, boutonActeur(ctx, 'gestionnaire', g.siren, g.nom), h('span', { classe: 'sous' },
        `${LIBELLE_GESTIONNAIRE[g.type] ?? g.type} · Siren ${g.siren} · ${pluriel(g.n, 'accueil')}`),
    )))) : null,
    voletActeurs('asso', c.nb.assos, code, ctx),
    voletActeurs('relais', c.nb.relais, code, ctx),
    voletActeurs('producteur', c.nb.producteurs, code, ctx),
    ecoles.length ? volet('Jauges des écoles', null, resumeEcoles(ecoles, modele, '')) : vide('Aucune école du périmètre dans cette commune.'),
    blocEcoles(ecoles, ctx),
    h('p', { classe: 'pied' }, h('button', { type: 'button', onclick: () => ctx.ouvrirCarnet([code], c.nom) }, 'Contacts de la commune')),
    tableSources(meta, c),
  );
}

const DISPOSITIFS = 'Dispositifs et élus';
const SIGNAUX = 'Signaux du site de la mairie';
const CANTINE = 'Cantine scolaire';
const TERRITOIRE = 'Soutiens territoriaux';

/** Département et intercommunalité, qui ouvrent leur fiche. */
function lieu(c: FicheCommune, ctx: ContexteFiche): (HTMLElement | string)[] {
  const trouver = (...types: string[]): { siren: string } | undefined =>
    (c.organismes ?? []).find((o) => types.includes(o.type));
  const interco = c.ept ?? c.epci;
  return [
    boutonActeur(ctx, 'organisme', trouver('departement')?.siren, ctx.modele.meta.departements[c.dep], false),
    ...(interco ? [' · ', boutonActeur(ctx, 'organisme', trouver(c.ept ? 'ept' : 'epci')?.siren, interco, false)] : []),
  ];
}

/** Acteurs de la commune, chargés quand on déplie. */
function voletActeurs(nature: NatureFichier, n: number, code: string, ctx: ContexteFiche): HTMLElement | null {
  if (!n) return null;
  const corps = h('div', {}, vide('Chargement…'));
  const el = volet(LIBELLE_NATURE[nature][1], n, corps);
  let demande = false;
  el.addEventListener('toggle', () => {
    if (demande) return;
    demande = true;
    chargerActeurs(nature).then((tous) => {
      const siens = Object.entries(tous).filter(([, a]) => a.commune === code && (nature !== 'producteur' || a.eligible))
        .sort((x, y) => x[1].nom.localeCompare(y[1].nom, 'fr'));
      remplacer(corps, siens.length ? listeRepliee(siens.map(([id, a]) => ligneActeur(nature, id, a, ctx)), 8) : vide('Liste indisponible.'));
    }).catch(() => {
      demande = false;
      remplacer(corps, vide('Liste indisponible : vérifiez la connexion.'));
    });
  });
  return el;
}

function ligneActeur(nature: NatureFichier, id: string, a: Acteur, ctx: ContexteFiche): HTMLElement {
  const sous = nature === 'relais' ? LIBELLE_RELAIS[a.type ?? ''] : nature === 'producteur' ? a.activites?.join(', ')
    : nature === 'asso' ? a.federation : a.adresse;
  return h('li', {}, boutonActeur(ctx, nature, id, a.nom),
    a.contact?.email && [' ', etiquette('e-mail')], sous && h('span', { classe: 'sous' }, sous));
}

export function resumeEcoles(toutes: number[], modele: Modele, sinon: string): HTMLElement {
  const moyenne = modele.moyenne(toutes.map((i) => modele.scores[i]));
  if (!toutes.length) return vide(sinon);
  return h(
    'div', {},
    h('div', { classe: 'heros' },
      anneau(moyenne),
      h('div', {}, h('b', {}, 'Score moyen des écoles sur 100'),
        h('span', { classe: 'sous' }, pluriel(toutes.length, 'école'), ', toutes confondues'))),
    h('div', { classe: 'jauges' }, JAUGES.map((j) => {
      const valeurs = toutes.map((i) => modele.valeur(j, i));
      const v = modele.moyenne(valeurs);
      const n = valeurs.filter((x) => x !== null).length;
      return h('div', { classe: 'jauge simple' },
        h('span', { classe: 'nom' }, LIBELLE_JAUGE[j], h('span', { classe: 'sous' }, ` ${n}/${toutes.length} écoles`)),
        h('span', { classe: v === null ? 'valeur insuffisant' : 'valeur' }, v === null ? 'données insuffisantes' : nombre(v)),
        metre(v, LIBELLE_JAUGE[j], j));
    })),
  );
}

function blocCantine(c: FicheCommune, ctx: ContexteFiche): HTMLElement {
  const { meta } = ctx.modele;
  const k = c.cantine;
  return bloc(
    CANTINE,
    k ? definition(
      ['Gestion', k.gestion ? LIBELLE_GESTION[k.gestion] : 'inconnue'],
      ['Bio', k.bio === undefined ? 'non déclaré' : `${pourcent(k.bio)} des achats${k.annee ? ` (${k.annee})` : ''}`],
      ['EGalim', k.egalim === undefined ? 'non déclaré' : `${pourcent(k.egalim)} durables et de qualité, bio compris`],
      ['Restaurants', `${pluriel(k.nb ?? 0, 'inscrit')} sur « ma cantine », ${pluriel(k.declarations ?? 0, 'déclaration')}`],
      k.satellites !== undefined || k.sur_place !== undefined ? ['Production', [
        k.satellites ? `${pluriel(k.satellites, 'satellite')} (repas livrés)` : null,
        k.sur_place ? `${pluriel(k.sur_place, 'cuisine sur place', 'cuisines sur place')}` : null,
        k.regie !== undefined ? `${pourcent(100 * k.regie)} en régie` : null,
        k.repas ? `${nombre(k.repas)} repas par jour` : null,
      ].filter(Boolean).join(' · ') || 'inconnue'] : null,
      k.centrale ? ['Cuisine centrale', h('span', {}, boutonActeur(ctx, 'cuisine', k.centrale.siret, k.centrale.nom), h('span', { classe: 'sous' }, [
        LIBELLE_CUISINE[k.centrale.type] ?? k.centrale.type,
        k.centrale.commune && `à ${k.centrale.commune}`,
        k.centrale.gestion && LIBELLE_GESTION[k.centrale.gestion],
        k.centrale.cantines && `livre ${pluriel(k.centrale.cantines, 'cantine')} scolaire${k.centrale.cantines > 1 ? 's' : ''} en Île-de-France`,
        k.centrale.bio !== undefined && `${pourcent(k.centrale.bio)} de bio`,
      ].filter(Boolean).join(' · ')), provenance(k.centrale.p, meta))] : null,
    ) : vide('Aucun restaurant scolaire public inscrit sur « ma cantine ».'),
    provenance(c.pg?.cantine, meta),
  );
}

/** Score propre de la commune (étape 1), recalculé selon les poids et le rayon choisis. */
function resumeCommune(code: string, c: FicheCommune, ctx: ContexteFiche): HTMLElement | null {
  const m = ctx.communes;
  const k = m.rang.get(code);
  if (k === undefined) return null;
  const s = m.scores[k];
  const details = new Map((c.score?.criteres ?? []).map((x) => [x.code, x.detail]));
  const texte = (x: CritereCommune): string | null => {
    const d = details.get(x) as unknown;
    if (x === 'producteurs') return m.valeur(x, k) === null ? null : 'moyenne des écoles';
    if (d === undefined || d === null) return null;
    if (x === 'cuisine') return LIBELLE_CUISINE[d as string] ?? String(d);
    if (x === 'cantine_bio') return `${pourcent(d as number)} de bio`;
    if (x === 'associations') return pluriel(d as number, 'association');
    if (x === 'ecoles') return pluriel(d as number, 'élève');
    if (x === 'communications') return (d as string[]).map((t) => LIBELLE_THEME[t] ?? t).join(', ') || 'aucun thème récent';
    if (x === 'soutiens') {
      const v = d as { departement?: number; aap_mgp?: boolean };
      return [v.departement !== undefined && v.departement !== null && `département ${v.departement}/2`,
        v.aap_mgp && 'lauréat AAP MGP'].filter(Boolean).join(' · ') || null;
    }
    return String(d);
  };
  /** Un critère mène à ce qui l'explique : la fiche s'il n'y en a qu'une, sinon le bloc qui les liste. */
  const pats = (c.dispositifs ?? []).filter((d) => d.type === 'pat');
  const blocs: Record<CritereCommune, string> = {
    pat: DISPOSITIFS, soutiens: TERRITOIRE, cuisine: CANTINE, cantine_bio: CANTINE, communications: SIGNAUX,
    producteurs: LIBELLE_NATURE.producteur[1], associations: LIBELLE_NATURE.alimentation[1], ecoles: LIBELLE_NATURE.ecole[1],
  };
  const suivre = (x: CritereCommune, depuis: Element): void => {
    const centrale = c.cantine?.centrale?.siret;
    if (x === 'pat' && pats.length === 1) ctx.ouvrir({ type: 'pat', id: pats[0].id });
    else if (x === 'cuisine' && centrale) ctx.ouvrir({ type: 'acteur', nature: 'cuisine', id: centrale });
    else montrerBloc(depuis, x === 'producteurs' && !c.nb.producteurs ? LIBELLE_NATURE.ecole[1] : blocs[x]);
  };
  return h(
    'div', {},
    h('div', { classe: 'heros' },
      anneau(s),
      h('div', {}, h('b', {}, s === null ? 'Données insuffisantes' : 'Score de la commune sur 100'),
        h('span', { classe: 'sous' }, `${m.connus[k]}/${CRITERES_COMMUNES.length} critères connus`))),
    h('div', { classe: 'jauges' }, CRITERES_COMMUNES.map((x) => {
      const v = m.valeur(x, k);
      return h('button', { type: 'button', classe: 'jauge simple', onclick: (e: MouseEvent) => suivre(x, e.currentTarget as Element) },
        h('span', { classe: 'nom' }, LIBELLE_CRITERE_COMMUNE[x], texte(x) && h('span', { classe: 'sous' }, ` ${texte(x)}`)),
        h('span', { classe: v === null ? 'valeur insuffisant' : 'valeur' }, v === null ? 'inconnu' : nombre(v)),
        metre(v, LIBELLE_CRITERE_COMMUNE[x], ACTEUR_CRITERE[x]));
    })),
  );
}

function blocSoutiens(c: FicheCommune, ctx: ContexteFiche): HTMLElement {
  const { meta } = ctx.modele;
  const liste = (c.dispositifs ?? []).filter((d) => SOUTIENS.has(d.type));
  const lignes = liste.map((d) => h(
    'li', {},
    boutonDispositif(d, ctx), ' ', etiquette(d.type === 'soutien_territorial' ? (d.score === undefined ? 'contexte' : `${d.score}/2`) : LIBELLE_DISPOSITIF[d.type]),
    (d.priorites || d.editions) && h('span', { classe: 'sous' }, d.editions ? `Éditions : ${d.editions}` : d.priorites),
    provenance(d.p, meta),
  ));
  return volet(TERRITOIRE, lignes.length,
    lignes.length ? h('ul', { classe: 'liste' }, lignes) : vide('Aucun soutien recensé.'));
}

function blocAlimentation(c: FicheCommune, ctx: ContexteFiche): HTMLElement {
  const { meta } = ctx.modele;
  const titre = LIBELLE_NATURE.alimentation[1];
  const a = c.alimentation;
  if (!a) return volet(titre, 0, vide('Aucune association recensée au RNA.'));
  const categories = Object.entries(a.categories).map(([k, n]) => `${LIBELLE_CATEGORIE_ALIMENTATION[k] ?? k} : ${n}`);
  return volet(
    titre, a.n,
    h('p', { classe: 'note' }, 'Siège dans la commune · ', categories.join(' · ')),
    listeRepliee(a.assos.map((x) => h(
      'li', {}, boutonActeur(ctx, 'alimentation', x.id, x.nom), ' ',
      etiquette(LIBELLE_CATEGORIE_ALIMENTATION[x.categorie] ?? x.categorie),
      (x.declaration || x.site) && h('span', { classe: 'sous' }, x.declaration && `Dernière déclaration : ${date(x.declaration)}`,
        x.declaration && x.site && ' · ', lien(x.site, 'site web')),
      provenance(x.p, meta),
    )), 6),
    h('p', { classe: 'note' }, 'Classement automatique par mots-clés du titre et de l’objet : à vérifier avant tout contact.'),
  );
}

function blocSignaux(c: FicheCommune, ctx: ContexteFiche): HTMLElement {
  const { meta } = ctx.modele;
  const signaux = (c.signaux ?? []).map((s) => h(
    'li', {},
    lien(s.p.u, s.titre ?? 'Page du site') ?? s.titre, ' ', etiquette(LIBELLE_THEME[s.theme] ?? s.theme),
    h('span', { classe: 'sous' }, `${LIBELLE_PAGE[s.type] ?? s.type} · ${s.date ? date(s.date) : 'sans date'}`),
    provenance(s.p, meta),
  ));
  const etat = c.visite ? `${LIBELLE_VISITE[c.visite.statut] ?? c.visite.statut} le ${date(c.visite.date)}`
    : c.site ? 'site pas encore visité' : 'aucun site connu';
  return volet(
    SIGNAUX, c.nb_signaux,
    h('p', { classe: 'note' }, etat.charAt(0).toUpperCase() + etat.slice(1),
      c.nb_signaux > signaux.length && ` · ${c.nb_signaux} signaux, les plus récents affichés`),
    signaux.length ? listeRepliee(signaux, 5) : vide('Aucun signal.'),
  );
}

export function blocEcoles(liste: number[], ctx: ContexteFiche): HTMLElement | null {
  const { modele } = ctx;
  const ecoles = [...liste].sort(
    (a, b) => (modele.scores[b] ?? -1) - (modele.scores[a] ?? -1) || modele.t.nom[a].localeCompare(modele.t.nom[b], 'fr'),
  );
  if (!ecoles.length) return null;
  return volet(LIBELLE_NATURE.ecole[1], ecoles.length, listeRepliee(ecoles.map((i) => {
    const s = modele.scores[i];
    return h('li', { classe: 'proche' },
      boutonEcole(ctx, modele.t.uai[i]),
      h('span', { classe: 'trajet' }, s === null ? '–' : nombre(s)));
  }), 12));
}
