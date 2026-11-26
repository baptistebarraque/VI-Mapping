/** Infobulle au survol et choix au clic quand plusieurs instances sont au même endroit. */

import type { Modele } from '../modele';
import { JAUGES, type Nature } from '../types';
import { pastille } from './commun';
import { h } from './dom';
import { COURT_JAUGE, LIBELLE_NATURE, LIBELLE_RELAIS, nombre, pluriel } from './format';

export type TypePoint = 'accueils' | 'assos' | 'producteurs' | 'relais';
type Proprietes = Record<string, unknown>;
const texte = (x: unknown): string | undefined => (x === undefined || x === null || x === '' ? undefined : String(x));

/** Nature de la fiche d'un point, selon sa couche. */
export const NATURE_POINT: Record<TypePoint, Nature> = {
  accueils: 'accueil', assos: 'asso', producteurs: 'producteur', relais: 'relais',
};

export const surtitrePoint = (type: TypePoint, p: Proprietes): string =>
  (type === 'relais' ? LIBELLE_RELAIS[String(p.type)] : undefined) ?? LIBELLE_NATURE[NATURE_POINT[type]][0];

/** `autres` : nombre de points superposés à celui-ci. */
export function infobulle(type: TypePoint | 'ecoles', p: Proprietes, modele: Modele, autres = 0): HTMLElement {
  const suite = autres > 0 && h('span', { classe: 'sous' }, `et ${pluriel(autres, 'autre point', 'autres points')} au même endroit`);
  if (type !== 'ecoles') {
    return h('div', {}, h('strong', {}, texte(p.nom)), h('span', { classe: 'sous' }, surtitrePoint(type, p)), suite);
  }
  const i = p.i as number;
  const s = modele.scores[i];
  return h(
    'div', {},
    h('strong', {}, modele.t.nom[i]),
    h('span', { classe: 'sous' }, modele.meta.communes[modele.t.commune[i]].nom),
    h('span', { classe: 'sous' }, h('b', {}, s === null ? 'Données insuffisantes' : nombre(s)), s !== null && ' sur 100'),
    h('ul', { classe: 'mini' }, JAUGES.map((j) => {
      const v = modele.valeur(j, i);
      return h('li', {}, h('span', {}, pastille(j), COURT_JAUGE[j]), v === null ? h('span', { classe: 'sous' }, 'insuffisant') : h('b', {}, nombre(v)));
    })),
    suite,
  );
}

/** Une instance de la carte, à ouvrir. */
export interface Choix {
  surtitre: string;
  nom: string;
  valeur?: string;
  ouvrir: () => void;
}

/** Plusieurs instances sous le pointeur (points superposés, zones qui se recouvrent) : on choisit laquelle ouvrir. */
export function popupChoix(titre: string, choix: Choix[]): HTMLElement {
  return h('div', {}, h('p', { classe: 'surtitre' }, titre), h(
    'ul', { classe: 'liste' }, choix.map((c) => h('li', { classe: 'proche' },
      h('span', {}, h('button', { type: 'button', classe: 'lien fort', onclick: c.ouvrir }, c.nom),
        h('span', { classe: 'sous' }, c.surtitre)),
      c.valeur !== undefined && h('span', { classe: 'trajet' }, c.valeur))),
  ));
}
