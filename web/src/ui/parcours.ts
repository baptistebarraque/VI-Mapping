/** Flèches de la fiche d'une école : précédente et suivante dans le classement filtré. */

import type { Modele } from '../modele';
import { h } from './dom';
import { nombre } from './format';

export class Parcours {
  readonly el: HTMLElement;
  private place = h('span', { classe: 'place', 'aria-live': 'polite' });
  private precedente: HTMLButtonElement;
  private suivante: HTMLButtonElement;
  private ecole: number | null = null;

  constructor(
    private modele: Modele,
    private choisir: (i: number) => void,
  ) {
    this.precedente = this.fleche('‹', 'École précédente du classement', -1);
    this.suivante = this.fleche('›', 'École suivante du classement', 1);
    this.el = h(
      'div', { classe: 'parcours', role: 'group', 'aria-label': 'Parcourir le classement', hidden: true },
      this.precedente, this.place, this.suivante,
    );
  }

  /** `i` : école affichée ; null si la fiche n'est pas celle d'une école. */
  maj(i: number | null): void {
    this.ecole = i;
    this.el.hidden = i === null;
    if (i === null) return;
    const rang = this.modele.visibles.indexOf(i);
    const total = this.modele.visibles.length;
    this.place.textContent = rang < 0 ? 'hors filtres' : `${nombre(rang + 1)} / ${nombre(total)}`;
    this.precedente.disabled = this.modele.voisine(i, -1) === null;
    this.suivante.disabled = this.modele.voisine(i, 1) === null;
  }

  private fleche(signe: string, libelle: string, pas: 1 | -1): HTMLButtonElement {
    return h('button', {
      type: 'button', classe: 'fleche', 'aria-label': libelle, title: libelle,
      onclick: () => {
        const v = this.ecole === null ? null : this.modele.voisine(this.ecole, pas);
        if (v !== null) this.choisir(v);
      },
    }, signe);
  }
}
