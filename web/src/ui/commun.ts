/** Briques partagées par les fiches : jauge, provenance, blocs. */

import type { Meta, NomJauge, ParCritere, Provenance } from '../types';
import { h, lien, type Enfant } from './dom';
import { date, dixieme, LIBELLE_METHODE, nombre } from './format';

/** Jauge horizontale 0-100. Sans valeur : piste vide, « données insuffisantes ». */
export function metre(valeur: number | null, libelle: string, jauge: NomJauge): HTMLElement {
  return h(
    'div',
    {
      classe: `metre j-${jauge}${valeur === null ? ' metre-vide' : ''}`,
      role: 'meter', 'aria-label': libelle, 'aria-valuemin': 0, 'aria-valuemax': 100,
      'aria-valuenow': valeur ?? undefined,
      'aria-valuetext': valeur === null ? 'données insuffisantes' : `${Math.round(valeur)} sur 100`,
    },
    valeur !== null && h('div', { classe: 'metre-plein', style: `width:${valeur}%` }),
  );
}

/** Pastille de la couleur d'une jauge : collectivités, écoles, parents, producteurs, familles. */
export const pastille = (j: NomJauge): HTMLElement => h('i', { classe: `pastille j-${j}`, 'aria-hidden': 'true' });

/** Couleur d'un critère communal : celle de l'acteur qu'il décrit. */
export const ACTEUR_CRITERE: ParCritere<NomJauge> = {
  pat: 'engagement', soutiens: 'engagement', cuisine: 'engagement', cantine_bio: 'engagement',
  communications: 'engagement', producteurs: 'producteurs', associations: 'parents', ecoles: 'periscolaire',
};

/** Score dans un anneau rempli à sa hauteur. */
export const anneau = (score: number | null): HTMLElement => h(
  'span', { classe: 'anneau', style: `--score:${score ?? 0}` },
  h('span', { classe: 'chiffre' }, score === null ? '–' : nombre(score)),
);

export function nomSource(code: string, meta: Meta): string {
  return meta.sources[code]?.libelle ?? code;
}

/** « Source · méthode · collecté le … · confiance … » : présent sous chaque donnée. */
export function provenance(p: Provenance | undefined, meta: Meta, prefixe = ''): HTMLElement | null {
  if (!p) return null;
  const s = meta.sources[p.s];
  const nom = nomSource(p.s, meta).replace(/ \([^)]*\)$/, ''); // précision laissée au tableau des sources
  return h(
    'p', { classe: 'provenance' },
    prefixe, lien(p.u, nom) ?? nom,
    s && ` · ${LIBELLE_METHODE[s.methode]}`, ` · ${date(p.d)} · confiance ${dixieme(p.c)}`,
  );
}

export function bloc(titre: string, ...contenu: Enfant[]): HTMLElement {
  return h('section', { classe: 'bloc' }, h('h3', {}, titre), ...contenu);
}

/** Bloc replié : le détail ne s'affiche qu'à la demande. */
export function volet(titre: string, compte: number | null, ...contenu: Enfant[]): HTMLElement {
  return h(
    'details', { classe: 'bloc replie' },
    h('summary', {}, h('h3', {}, titre), compte !== null && h('span', { classe: 'compteur' }, nombre(compte))),
    ...contenu,
  );
}

export const vide = (texte: string): HTMLElement => h('p', { classe: 'vide' }, texte);

export const etiquette = (texte: string): HTMLElement => h('span', { classe: 'etiquette' }, texte);

export type Paire = [string, Enfant] | null | false | undefined | '' | 0;
export function definition(...paires: Paire[]): HTMLElement {
  return h('dl', { classe: 'definition' }, paires.map((p) => p && [h('dt', {}, p[0]), h('dd', {}, p[1])]));
}

/** Liste dont on ne montre d'abord que le début. */
export function listeRepliee(elements: HTMLElement[], visibles: number, classe = 'liste'): HTMLElement {
  const suite = elements.slice(visibles);
  const liste = h('ul', { classe }, elements.slice(0, visibles));
  if (!suite.length) return liste;
  const bouton = h('button', {
    type: 'button', classe: 'discret',
    onclick: () => {
      liste.append(...suite);
      bouton.remove();
    },
  }, `Afficher les ${suite.length} autres`);
  return h('div', {}, liste, bouton);
}

/** Toutes les provenances citées dans un objet, regroupées par source : dates et confiances extrêmes. */
export interface Resume {
  source: string;
  url: string | undefined;
  debut: string;
  fin: string;
  min: number;
  max: number;
  n: number;
}

export function resumerSources(...objets: unknown[]): Resume[] {
  const parSource = new Map<string, Resume>();
  const visiter = (x: unknown): void => {
    if (typeof x !== 'object' || x === null) return;
    const p = x as Partial<Provenance>;
    if (typeof p.s === 'string' && typeof p.u === 'string' && typeof p.d === 'string' && typeof p.c === 'number') {
      const r = parSource.get(p.s);
      if (!r) {
        parSource.set(p.s, { source: p.s, url: p.u, debut: p.d, fin: p.d, min: p.c, max: p.c, n: 1 });
      } else {
        if (r.url !== p.u) r.url = undefined;
        if (p.d < r.debut) r.debut = p.d;
        if (p.d > r.fin) r.fin = p.d;
        r.min = Math.min(r.min, p.c);
        r.max = Math.max(r.max, p.c);
        r.n++;
      }
    }
    for (const v of Object.values(x)) visiter(v);
  };
  objets.forEach(visiter);
  return [...parSource.values()].sort((a, b) => a.source.localeCompare(b.source));
}

export function tableSources(meta: Meta, ...objets: unknown[]): HTMLElement {
  const lignes = resumerSources(...objets);
  return h(
    'details', { classe: 'bloc replie' },
    h('summary', {}, h('h3', {}, 'Sources et dates de collecte')),
    h(
      'table', { classe: 'table-sources' },
      h('thead', {}, h('tr', {}, ...['Source', 'Méthode', 'Collecte', 'Confiance'].map((t) => h('th', { scope: 'col' }, t)))),
      h('tbody', {}, lignes.map((r) => h(
        'tr', {},
        h('td', {}, lien(r.url ?? meta.sources[r.source]?.url, nomSource(r.source, meta)) ?? nomSource(r.source, meta)),
        h('td', {}, LIBELLE_METHODE[meta.sources[r.source]?.methode ?? ''] ?? ''),
        h('td', {}, r.debut === r.fin ? date(r.fin) : `${date(r.debut)} – ${date(r.fin)}`),
        h('td', { classe: 'num' }, r.min === r.max ? dixieme(r.max) : `${dixieme(r.min)} – ${dixieme(r.max)}`),
      ))),
    ),
  );
}
