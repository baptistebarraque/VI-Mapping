/** Fiche d'une collectivité : identité, cantine, dispositifs, élus, signaux du site, écoles. */

import type { Modele } from '../modele';
import { JAUGES, type Dispositif, type Fiche, type FicheCommune, type FicheEcole, type Meta } from '../types';
import { anneau, bloc, definition, etiquette, listeRepliee, metre, provenance, tableSources, vide, volet } from './commun';
import { h, lien } from './dom';
import {
  date, LIBELLE_DISPOSITIF, LIBELLE_GESTION, LIBELLE_GESTIONNAIRE, LIBELLE_JAUGE, LIBELLE_PAGE, LIBELLE_THEME,
  LIBELLE_VISITE, nombre, pluriel, pourcent,
} from './format';
import type { ContexteFiche } from './fiche-ecole';

/** Thèmes de délégation utiles au projet, les plus proches d'abord. */
const UTILES = ['restauration', 'scolaire', 'enfance_jeunesse', 'agriculture', 'transition_ecologique'];

/** Élus : le maire et les délégations utiles ; `court` : seulement l'école, la cantine et l'enfance. */
export function listeElus(c: FicheCommune, meta: Meta, court = false): HTMLElement {
  const retenus = court ? UTILES.slice(0, 3) : UTILES;
  const rang = (t: string[] | undefined): number => {
    const l = (t ?? []).map((x) => retenus.indexOf(x)).filter((x) => x >= 0);
    return l.length ? Math.min(...l) : 99;
  };
  const maires = (c.elus ?? []).filter((e) => e.fonction.startsWith('Maire'));
  const delegues = (c.elus ?? []).filter((e) => !maires.includes(e) && rang(e.themes) < 99)
    .sort((a, b) => rang(a.themes) - rang(b.themes));
  const adjoints = (c.elus ?? []).filter((e) => !maires.includes(e) && !delegues.includes(e));
  const ligne = (e: (typeof maires)[number]): HTMLElement => h(
    'li', {},
    h('b', {}, e.nom), ` — ${e.fonction}`,
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

/** Nom d'un PAT, qui ouvre sa fiche et montre son périmètre sur la carte. */
export const boutonPat = (d: Dispositif, texte: string, ctx: ContexteFiche): HTMLElement => h('button', {
  type: 'button', classe: 'lien fort', title: 'Voir ce PAT sur la carte', onclick: () => ctx.ouvrirPat(d.id),
}, texte);

export function listeDispositifs(c: FicheCommune, ctx: ContexteFiche, ecole?: FicheEcole): HTMLElement {
  const { meta } = ctx.modele;
  // Pour une école : PAT et appels à projets de la commune ; QPV et cité éducative sont les siens propres.
  const liste = (c.dispositifs ?? []).filter((d) => !ecole || d.type === 'pat' || d.type === 'laureat_aap');
  const laureats = new Set(liste.filter((d) => d.type === 'laureat_aap').map((d) => d.id.split(':')[1]));
  const lignes = liste.filter((d) => d.type !== 'laureat_aap').map((d) => h(
    'li', {},
    d.type === 'pat' ? boutonPat(d, d.nom, ctx) : h('b', {}, d.nom), ' ', etiquette(LIBELLE_DISPOSITIF[d.type]),
    h('span', { classe: 'sous' }, [
      d.type === 'pat' && (d.axe ? 'axe éducation alimentaire' : 'sans axe éducation alimentaire'),
      d.type === 'pat' && laureats.has(d.id.split(':')[1]) && 'lauréat de l’appel à projets du PNA',
      d.niveau, d.annee,
    ].filter(Boolean).join(' · ')),
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
    h('p', { classe: 'lieu' }, [meta.departements[c.dep], c.ept ?? c.epci].filter(Boolean).join(' · '),
      c.mere && [' · ', h('button', { type: 'button', classe: 'lien', onclick: () => c.mere && ctx.ouvrirCommune(c.mere.code) }, c.mere.nom)]),
    resumeEcoles(ecoles, modele, 'Aucune école du périmètre dans cette commune.'),
    bloc(
      'Collectivité',
      definition(
        ['Code Insee', c.code],
        c.siren ? ['Siren', c.siren] : null,
        c.epci ? ['Intercommunalité', [c.epci, c.ept].filter(Boolean).join(', ')] : null,
        ['Population', c.population === undefined ? 'inconnue'
          : `${nombre(c.population)} habitants${c.population_annee ? ` (${c.population_annee})` : ''}`],
        c.densite === undefined ? null : ['Densité', `${nombre(c.densite)} hab./km²`],
        ['Site de la mairie', lien(c.site, (c.site ?? '').replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')) ?? 'inconnu'],
        ['Acteurs recensés', [
          pluriel(c.nb.accueils, 'accueil'), pluriel(c.nb.assos, 'association de parents', 'associations de parents'),
          pluriel(c.nb.relais, 'relais local', 'relais locaux'), pluriel(c.nb.producteurs, 'producteur pris en compte', 'producteurs pris en compte'),
        ].join(' · ')],
      ),
      provenance(c.p, meta),
    ),
    blocCantine(c, meta),
    volet('Dispositifs et élus', null, listeDispositifs(c, ctx), listeElus(c, meta)),
    blocSignaux(c, meta),
    c.gestionnaires?.length ? volet('Gestionnaires périscolaires', c.gestionnaires.length, h('ul', { classe: 'liste' }, c.gestionnaires.map((g) => h(
      'li', {}, h('b', {}, g.nom), h('span', { classe: 'sous' },
        `${LIBELLE_GESTIONNAIRE[g.type] ?? g.type} · Siren ${g.siren} · ${pluriel(g.n, 'accueil')}`),
    )))) : null,
    blocEcoles(ecoles, ctx),
    tableSources(meta, c),
  );
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

function blocCantine(c: FicheCommune, meta: Meta): HTMLElement {
  const k = c.cantine;
  return bloc(
    'Cantine scolaire',
    k ? definition(
      ['Gestion', k.gestion ? LIBELLE_GESTION[k.gestion] : 'inconnue'],
      ['Bio', k.bio === undefined ? 'non déclaré' : `${pourcent(k.bio)} des achats${k.annee ? ` (${k.annee})` : ''}`],
      ['EGalim', k.egalim === undefined ? 'non déclaré' : `${pourcent(k.egalim)} durables et de qualité, bio compris`],
      ['Restaurants', `${pluriel(k.nb ?? 0, 'inscrit')} sur « ma cantine », ${pluriel(k.declarations ?? 0, 'déclaration')}`],
    ) : vide('Aucun restaurant scolaire public inscrit sur « ma cantine ».'),
    provenance(c.pg?.cantine, meta),
  );
}

function blocSignaux(c: FicheCommune, meta: Meta): HTMLElement {
  const signaux = (c.signaux ?? []).map((s) => h(
    'li', {},
    lien(s.p.u, s.titre ?? 'Page du site') ?? s.titre, ' ', etiquette(LIBELLE_THEME[s.theme] ?? s.theme),
    h('span', { classe: 'sous' }, `${LIBELLE_PAGE[s.type] ?? s.type} · ${s.date ? date(s.date) : 'sans date'}`),
    provenance(s.p, meta),
  ));
  const etat = c.visite ? `${LIBELLE_VISITE[c.visite.statut] ?? c.visite.statut} le ${date(c.visite.date)}`
    : c.site ? 'site pas encore visité' : 'aucun site connu';
  return volet(
    'Signaux du site de la mairie', c.nb_signaux,
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
  return volet('Écoles', ecoles.length, listeRepliee(ecoles.map((i) => {
    const s = modele.scores[i];
    return h('li', { classe: 'proche' },
      h('button', { type: 'button', classe: 'lien fort', onclick: () => ctx.ouvrirEcole(i) }, modele.t.nom[i]),
      h('span', { classe: 'trajet' }, s === null ? '–' : nombre(s)));
  }), 12));
}
