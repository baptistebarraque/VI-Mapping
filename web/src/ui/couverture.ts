/** Rapport de couverture dans la fenêtre « Méthode et sources » : taux de remplissage par champ et par département. */

import type { Couverture, TableCouverte } from '../types';
import { h } from './dom';
import { nombre } from './format';

/** Jamais arrondi à 0 ou à 100 % : « 100 % » veut dire complet, « 0 % » vide. */
export function pourcent(taux: number | null): string {
  if (taux === null) return '–';
  if (taux > 0 && taux < 0.01) return '< 1 %';
  if (taux > 0.99 && taux < 1) return '> 99 %';
  return `${Math.round(100 * taux)} %`;
}

export function tableauxCouverture(c: Couverture): HTMLElement {
  return h(
    'details', { classe: 'bloc replie' },
    h('summary', {}, h('h3', {}, 'Taux de remplissage par département')),
    h('p', { classe: 'note' },
      'Part des lignes où le champ est connu. * : part des lignes concernées, une absence y veut dire « non ».'),
    c.tables.map((t) => h('details', { classe: 'bloc replie couverture' },
      h('summary', {}, h('h4', {}, t.libelle)), table(t, c.zones))),
  );
}

function table(t: TableCouverte, zones: string[]): HTMLElement {
  return h('div', {},
    h('div', { classe: 'defile' }, h(
      'table', { classe: 'table-sources table-couverture' },
      h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, 'Champ'), zones.map((z) => h('th', { scope: 'col' }, z)))),
      h('tbody', {},
        h('tr', {}, h('th', { scope: 'row' }, 'Nombre de lignes'), t.lignes.map((n) => h('td', {}, nombre(n)))),
        t.champs.map((x) => h('tr', {},
          h('th', { scope: 'row' }, x.nature === 'part' ? `${x.libelle} *` : x.libelle),
          x.taux.map((v) => h('td', {
            classe: x.nature === 'part' ? null : 'plein', style: `--taux: ${Math.round(100 * (v ?? 0))}%`,
          }, pourcent(v)))))),
    )),
    causes(t).map(([cause, champs]) => h('p', { classe: 'note' }, `${champs.join(', ')} : ${cause}.`)));
}

/** Champs incomplets regroupés par cause. */
function causes(t: TableCouverte): [string, string[]][] {
  const par = new Map<string, string[]>();
  for (const x of t.champs) {
    if (x.cause && (x.taux[0] ?? 0) < 0.9) par.set(x.cause, [...(par.get(x.cause) ?? []), x.libelle]);
  }
  return [...par];
}
