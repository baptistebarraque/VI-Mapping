/** Légende : échelle des écoles, symboles des couches affichées, échelle des IRIS. */

import {
  BORNES_IRIS, BORNES_SCORE, bornesDe, COLLECTIVITE, ENCRE_2, INCONNU, OPACITE_COMMUNES, OPACITE_IRIS, RAMPE_COMMUNES,
  RAMPE_ECOLES, RAMPE_IRIS, ZONE_CITE, ZONE_PAT,
} from '../couleurs';
import type { Etat } from '../etat';
import { h, remplacer, svg, type Enfant } from './dom';
import { LIBELLE_COLORATION, LIBELLE_COUCHE, LIBELLE_IRIS, VALEUR_IRIS } from './format';
import { rond, symbole, zone } from './symboles';

const tranches = (bornes: readonly number[], f: (x: number) => string): string[] => [
  `moins de ${f(bornes[0])}`,
  ...bornes.slice(0, -1).map((b, k) => `${f(b)} – ${f(bornes[k + 1])}`),
  `${f(bornes.at(-1) ?? 0)} et plus`,
];

const ligne = (signe: Node, texte: string): HTMLElement => h('li', {}, signe, h('span', {}, texte));

const carre = (couleur: string, opacite = OPACITE_IRIS): SVGElement => svg(
  'svg', { width: 16, height: 12, viewBox: '0 0 16 12', 'aria-hidden': 'true', class: 'symbole' },
  svg('rect', { x: 0, y: 0, width: 16, height: 12, rx: 2, fill: couleur, 'fill-opacity': opacite }),
);

/** Échelle en bandeau : une case par tranche, les bornes entre deux cases. */
const bandeau = (couleurs: readonly string[], bornes: readonly number[], opacite = 1): HTMLElement => h(
  'div', { classe: 'bandeau', role: 'img', 'aria-label': tranches(bornes, String).join(', ') },
  couleurs.map((c, k) => h('span', { style: `--case:color-mix(in srgb, ${c} ${100 * opacite}%, white)` }, k > 0 && h('b', {}, bornes[k - 1]))),
);

export function majLegende(el: HTMLDetailsElement, e: Etat): void {
  const c = e.couches;
  const blocs: Enfant[] = [];
  if (c.communes && e.etape === 'communes') {
    blocs.push(
      h('h2', {}, 'Communes — score de la commune'),
      bandeau(RAMPE_COMMUNES, BORNES_SCORE, OPACITE_COMMUNES),
    );
  } else if (c.communes && e.filtres.retenues.length) {
    blocs.push(h('ul', {}, ligne(carre(COLLECTIVITE, 0.3), 'Communes retenues à l’étape 1')));
  }
  if (c.ecoles) {
    blocs.push(
      h('h2', {}, `Écoles — ${LIBELLE_COLORATION[e.coloration].toLowerCase()}`),
      bandeau(RAMPE_ECOLES, bornesDe(e.coloration)),
      h(
        'ul', {},
        ligne(rond(INCONNU, { creux: true }), 'données insuffisantes'),
      ),
    );
  }
  const autres: HTMLElement[] = [];
  for (const s of ['accueils', 'assos'] as const) if (c[s]) autres.push(ligne(symbole(s), LIBELLE_COUCHE[s]));
  if (c.producteurs) {
    autres.push(ligne(symbole('producteurs'), 'Producteurs comptés dans la jauge'));
    autres.push(ligne(symbole('producteurs_autres'), 'Autres producteurs bio'));
  }
  if (c.relais) autres.push(ligne(symbole('relais'), LIBELLE_COUCHE.relais));
  if (c.pat) autres.push(ligne(zone(ZONE_PAT, `${ZONE_PAT}22`), LIBELLE_COUCHE.pat));
  if (c.cites) autres.push(ligne(zone(ZONE_CITE, `${ZONE_CITE}22`), LIBELLE_COUCHE.cites));
  if (c.qpv) autres.push(ligne(zone(ENCRE_2, 'none', true), LIBELLE_COUCHE.qpv));
  if (autres.length) blocs.push(h('h2', {}, 'Acteurs et zones'), h('ul', {}, autres));
  if (c.iris) {
    blocs.push(
      h('h2', {}, `IRIS — ${LIBELLE_IRIS[e.iris].toLowerCase()}`),
      h('ul', {}, tranches(BORNES_IRIS[e.iris], VALEUR_IRIS[e.iris]).map((t, k) => ligne(carre(RAMPE_IRIS[k]), t))),
    );
  }
  el.hidden = blocs.length === 0;
  remplacer(el, h('summary', {}, 'Légende'), ...blocs);
}
