/** Classement des écoles filtrées, de la mieux à la moins bien notée. */

import { PREMIERS_DEFAUT, PREMIERS_MAX } from '../etat';
import type { Modele } from '../modele';
import { JAUGES } from '../types';
import legumes from '../images/legumes-vi.png';
import { pastille } from './commun';
import { h, identifiant, remplacer } from './dom';
import { COURT_JAUGE, jaugeOuInsuffisant, nombre, pluriel } from './format';

const PAR_PAGE = 60;

export class Classement {
  readonly el: HTMLElement;
  private entete = h('p', { classe: 'compte', 'aria-live': 'polite' });
  private liste = h('ol', { classe: 'classement' });
  private suite: HTMLButtonElement;
  private limiter: HTMLButtonElement;
  private nombre: HTMLInputElement;
  private affichees = 0;
  private choisie: number | null = null;

  constructor(
    private modele: Modele,
    private choisir: (i: number) => void,
    exporter: () => void,
    private premiers: { lire: () => number | null; changer: (n: number | null) => void },
  ) {
    const id = identifiant('premiers');
    this.limiter = h('button', {
      type: 'button', classe: 'puce',
      title: 'Garder seulement le début du classement',
      onclick: () => this.premiers.changer(this.premiers.lire() === null ? this.saisi() : null),
    }, 'Seulement les');
    this.nombre = h('input', {
      id, type: 'number', min: 1, max: PREMIERS_MAX, step: 1, inputmode: 'numeric', value: PREMIERS_DEFAUT,
      'aria-label': 'Nombre d’écoles gardées en tête du classement',
      oninput: () => {
        if (this.premiers.lire() !== null && this.nombre.value !== '') this.premiers.changer(this.saisi());
      },
      onchange: () => {
        this.nombre.value = String(this.saisi());
      },
    });
    this.suite = h('button', { type: 'button', classe: 'discret', onclick: () => this.ajouter() }, 'Afficher la suite');
    this.el = h(
      'div', { classe: 'panneau-classement' },
      h('div', { classe: 'barre' }, this.entete, h('button', { type: 'button', classe: 'discret', onclick: exporter }, 'Exporter en CSV')),
      h('div', { classe: 'premiers' }, this.limiter, this.nombre, h('label', { for: id }, 'premières')),
      h('ul', { classe: 'cle', 'aria-label': 'Les cinq barres' },
        JAUGES.map((j) => h('li', {}, pastille(j), COURT_JAUGE[j]))),
      this.liste, this.suite,
    );
  }

  maj(): void {
    const { visibles, n } = this.modele;
    const sans = visibles.reduce((s, i) => s + (this.modele.scores[i] === null ? 1 : 0), 0);
    const limite = this.premiers.lire();
    this.limiter.setAttribute('aria-pressed', String(limite !== null));
    if (limite !== null && document.activeElement !== this.nombre) this.nombre.value = String(limite);
    remplacer(
      this.entete, h('b', {}, pluriel(visibles.length, 'école')),
      limite === null ? visibles.length < n && ` sur ${nombre(n)}` : ` sur ${pluriel(this.modele.nbFiltrees, 'filtrée')}`,
      sans > 0 && ` · ${nombre(sans)} sans score`,
    );
    this.affichees = 0;
    remplacer(this.liste);
    this.ajouter();
    if (!visibles.length) remplacer(this.liste, h('li', { classe: 'vide dessin' },
      h('img', { src: legumes, alt: '', width: 209, height: 103 }), 'Aucune école ne répond à ces filtres.'));
  }

  private saisi(): number {
    const x = Math.round(this.nombre.valueAsNumber);
    return Number.isFinite(x) ? Math.min(PREMIERS_MAX, Math.max(1, x)) : PREMIERS_DEFAUT;
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
        h('span', { classe: 'qui' }, h('b', {}, t.nom[i]), h('span', { classe: 'sous' }, `${meta.communes[t.commune[i]].nom} · ${connues[i]}/5 jauges`)),
        h(
          'span', { classe: 'barres', 'aria-hidden': 'true' },
          JAUGES.map((j) => {
            const v = this.modele.valeur(j, i);
            return v === null ? h('i', { classe: 'inconnue' }) : h('i', { classe: `j-${j}`, style: `height:${Math.max(v, 6)}%` });
          }),
        ),
        h('span', { classe: 'note-ecole' }, s === null ? '–' : nombre(s)),
      ),
    );
  }
}
