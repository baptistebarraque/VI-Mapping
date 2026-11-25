/** Briques partagées par les fiches : jauge, provenance, blocs. */

import type { Meta, Provenance } from '../types';
import { h, lien, type Enfant } from './dom';
import { date, dixieme, LIBELLE_METHODE } from './format';

/** Jauge horizontale 0-100. Sans valeur : piste vide, « données insuffisantes ». */
export function metre(valeur: number | null, libelle: string): HTMLElement {
  return h(
    'div',
    {
      classe: valeur === null ? 'metre metre-vide' : 'metre',
      role: 'meter', 'aria-label': libelle, 'aria-valuemin': 0, 'aria-valuemax': 100,
      'aria-valuenow': valeur ?? undefined,
      'aria-valuetext': valeur === null ? 'données insuffisantes' : `${Math.round(valeur)} sur 100`,
    },
    valeur !== null && h('div', { classe: 'metre-plein', style: `width:${valeur}%` }),
  );
}

export function nomSource(code: string, meta: Meta): string {
  return meta.sources[code]?.libelle ?? code;
}

/** « Source · méthode · collecté le … · confiance … » : présent sous chaque donnée. */
export function provenance(p: Provenance | undefined, meta: Meta, prefixe = ''): HTMLElement | null {
  if (!p) return null;
  const s = meta.sources[p.s];
  return h(
    'p', { classe: 'provenance' },
    prefixe, lien(p.u, nomSource(p.s, meta)) ?? nomSource(p.s, meta),
    s && ` · ${LIBELLE_METHODE[s.methode]}`, ` · ${date(p.d)} · confiance ${dixieme(p.c)}`,
  );
}

export function bloc(titre: string, ...contenu: Enfant[]): HTMLElement {
  return h('section', { classe: 'bloc' }, h('h3', {}, titre), ...contenu);
}

export const vide = (texte: string): HTMLElement => h('p', { classe: 'vide' }, texte);

/** Standard et adresse générique (mairie, école) : jamais une personne. */
export function contact(c: { tel?: string; email?: string }): HTMLElement {
  return h('span', {},
    c.tel && h('a', { href: `tel:${c.tel.replaceAll(' ', '')}` }, c.tel),
    c.tel && c.email && ' · ',
    c.email && h('a', { href: `mailto:${c.email}` }, c.email));
}
export const etiquette = (texte: string): HTMLElement => h('span', { classe: 'etiquette' }, texte);

export function definition(...paires: ([string, Enfant] | null | false | undefined)[]): HTMLElement {
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
