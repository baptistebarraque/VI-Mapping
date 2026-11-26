/** Flèches de la fiche d'une école ou d'une commune : précédente et suivante dans son classement filtré. */

import { h } from './dom';
import { nombre } from './format';

/** Un classement à parcourir : ses rangs visibles, du premier au dernier, et comment ouvrir l'un d'eux. */
export interface Suite {
  nom: string; // « École », « Commune » : pour les libellés des flèches
  visibles: () => readonly number[];
  choisir: (k: number) => void;
}

export type Suites<T extends string> = Record<T, Suite>;

/** Voisine de `k` dans `liste` ; null en bout de liste ou si `k` n'y est pas (hors filtres). */
export function voisine(liste: readonly number[], k: number, pas: 1 | -1): number | null {
  const rang = liste.indexOf(k);
  return rang < 0 ? null : (liste[rang + pas] ?? null);
}

export class Parcours<T extends string> {
  readonly el: HTMLElement;
  private place = h('span', { classe: 'place', 'aria-live': 'polite' });
  private precedente: HTMLButtonElement;
  private suivante: HTMLButtonElement;
  private suite: Suite | null = null;
  private k = -1;

  constructor(private suites: Suites<T>) {
    this.precedente = this.fleche('‹', -1);
    this.suivante = this.fleche('›', 1);
    this.el = h(
      'div', { classe: 'parcours', role: 'group', 'aria-label': 'Parcourir le classement', hidden: true },
      this.precedente, this.place, this.suivante,
    );
  }

  /** Fiche affichée : son classement et son rang ; null si elle n'est dans aucun classement. */
  maj(cible: { type: T; k: number } | null): void {
    this.suite = cible && this.suites[cible.type];
    this.el.hidden = this.suite === null;
    if (!cible || !this.suite) return;
    this.k = cible.k;
    const liste = this.suite.visibles();
    const rang = liste.indexOf(cible.k);
    this.place.textContent = rang < 0 ? 'hors filtres' : `${nombre(rang + 1)} / ${nombre(liste.length)}`;
    this.place.title = rang < 0 ? 'Absente du classement filtré : élargir les filtres pour la parcourir' : '';
    for (const [b, pas, quoi] of [[this.precedente, -1, 'précédente'], [this.suivante, 1, 'suivante']] as const) {
      const libelle = `${this.suite.nom} ${quoi} du classement`;
      b.setAttribute('aria-label', libelle);
      b.title = libelle;
      b.disabled = voisine(liste, cible.k, pas) === null;
    }
  }

  private fleche(signe: string, pas: 1 | -1): HTMLButtonElement {
    return h('button', {
      type: 'button', classe: 'fleche',
      onclick: () => {
        const v = this.suite && voisine(this.suite.visibles(), this.k, pas);
        if (v !== null) this.suite?.choisir(v);
      },
    }, signe);
  }
}
