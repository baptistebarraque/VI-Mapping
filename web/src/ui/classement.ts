/** Classement des écoles filtrées, de la mieux à la moins bien notée. */

import type { Modele } from '../modele';
import { JAUGES } from '../types';
import { h, remplacer } from './dom';
import { COURT_JAUGE, jaugeOuInsuffisant, nombre, pluriel } from './format';

const PAR_PAGE = 60;

export class Classement {
  readonly el: HTMLElement;
  private entete = h('p', { classe: 'compte', 'aria-live': 'polite' });
  private liste = h('ol', { classe: 'classement' });
  private suite: HTMLButtonElement;
  private affichees = 0;
  private choisie: number | null = null;

  constructor(
    private modele: Modele,
    private choisir: (i: number) => void,
    exporter: () => void,
  ) {
    this.suite = h('button', { type: 'button', classe: 'discret', onclick: () => this.ajouter() }, 'Afficher la suite');
    this.el = h(
      'div', { classe: 'panneau-classement' },
      h('div', { classe: 'barre' }, this.entete, h('button', { type: 'button', onclick: exporter }, 'Exporter en CSV')),
      h('p', { classe: 'note' },
        'À score égal, l’école la mieux documentée passe devant. Les cinq barres : ',
        JAUGES.map((j) => COURT_JAUGE[j].toLowerCase()).join(', '), '.'),
      this.liste, this.suite,
    );
  }

  maj(): void {
    const { visibles, n } = this.modele;
    const sans = visibles.reduce((s, i) => s + (this.modele.scores[i] === null ? 1 : 0), 0);
    remplacer(
      this.entete, h('b', {}, pluriel(visibles.length, 'école')), ` sur ${nombre(n)}`,
      sans > 0 && ` · ${nombre(sans)} sans score`,
    );
    this.affichees = 0;
    remplacer(this.liste);
    this.ajouter();
    if (!visibles.length) remplacer(this.liste, h('li', { classe: 'vide' }, 'Aucune école ne répond à ces filtres.'));
  }

  marquer(i: number | null): void {
    this.choisie = i;
    for (const b of this.liste.querySelectorAll<HTMLElement>('button[data-i]')) {
      if (Number(b.dataset.i) === i) b.setAttribute('aria-current', 'true');
      else b.removeAttribute('aria-current');
    }
  }

  private ajouter(): void {
    const { visibles } = this.modele;
    const fin = Math.min(this.affichees + PAR_PAGE, visibles.length);
    this.liste.append(...visibles.slice(this.affichees, fin).map((i, k) => this.ligne(i, this.affichees + k + 1)));
    this.affichees = fin;
    this.suite.hidden = fin >= visibles.length;
  }

  private ligne(i: number, rang: number): HTMLElement {
    const { t, meta, scores, connues } = this.modele;
    const s = scores[i];
    const detail = JAUGES.map((j) => `${COURT_JAUGE[j]} : ${jaugeOuInsuffisant(this.modele.valeur(j, i))}`).join('\n');
    return h(
      'li', {},
      h(
        'button', {
          type: 'button', 'data-i': i, 'aria-current': this.choisie === i && 'true', title: detail,
          onclick: () => this.choisir(i),
        },
        h('span', { classe: 'rang' }, rang),
        h('span', { classe: 'qui' }, h('b', {}, t.nom[i]), h('span', { classe: 'sous' }, meta.communes[t.commune[i]].nom)),
        h(
          'span', { classe: 'barres', 'aria-hidden': 'true' },
          JAUGES.map((j) => {
            const v = this.modele.valeur(j, i);
            return v === null ? h('i', { classe: 'inconnue' }) : h('i', { style: `height:${Math.max(v, 6)}%` });
          }),
        ),
        h(
          'span', { classe: 'note-ecole' },
          h('b', {}, s === null ? '–' : nombre(s)), h('span', { classe: 'sous' }, `${connues[i]}/5 jauges`),
        ),
      ),
    );
  }
}
