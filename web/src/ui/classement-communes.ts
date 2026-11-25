/** Classement des communes (étape 1) : score propre, critères, communes retenues pour l'étape des écoles. */

import type { ModeleCommunes } from '../modele-communes';
import { CRITERES_COMMUNES } from '../types';
import { h, identifiant, remplacer } from './dom';
import { COURT_CRITERE_COMMUNE, jaugeOuInsuffisant, nombre, pluriel } from './format';

const PAR_PAGE = 60;
const RETENUES_DEFAUT = 10;

export interface Retenues {
  lire: () => string[];
  changer: (codes: string[]) => void;
}

export class ClassementCommunes {
  readonly el: HTMLElement;
  private entete = h('p', { classe: 'compte', 'aria-live': 'polite' });
  private etatRetenues = h('p', { classe: 'note', 'aria-live': 'polite' });
  private liste = h('ol', { classe: 'classement communes' });
  private suite: HTMLButtonElement;
  private nombre: HTMLInputElement;
  private voir: HTMLButtonElement;
  private effacer: HTMLButtonElement;
  private affichees = 0;
  private choisie: string | null = null;

  constructor(
    private modele: ModeleCommunes,
    private choisir: (code: string) => void,
    private retenues: Retenues,
    voirEcoles: () => void,
    exporter: () => void,
  ) {
    const id = identifiant('retenir');
    this.nombre = h('input', {
      id, type: 'number', min: 1, max: 200, step: 1, inputmode: 'numeric', value: RETENUES_DEFAUT,
      'aria-label': 'Nombre de communes à retenir en tête du classement',
    });
    const retenir = h('button', {
      type: 'button', classe: 'puce', title: 'Retenir les premières communes du classement',
      onclick: () => {
        const n = Math.min(200, Math.max(1, Math.round(this.nombre.valueAsNumber) || RETENUES_DEFAUT));
        this.retenues.changer(this.modele.premieres(n));
      },
    }, 'Retenir les');
    this.voir = h('button', { type: 'button', onclick: voirEcoles }, 'Voir leurs écoles →');
    this.effacer = h('button', { type: 'button', classe: 'discret', onclick: () => this.retenues.changer([]) },
      'Effacer');
    this.suite = h('button', { type: 'button', classe: 'discret', onclick: () => this.ajouter() }, 'Afficher la suite');
    this.el = h(
      'div', { classe: 'panneau-classement' },
      h('div', { classe: 'barre' }, this.entete, h('button', { type: 'button', onclick: exporter }, 'Exporter en CSV')),
      h('p', { classe: 'note' },
        'Étape 1 : choisir les communes les plus favorables, puis passer à leurs écoles. Les huit barres : ',
        CRITERES_COMMUNES.map((c) => COURT_CRITERE_COMMUNE[c].toLowerCase()).join(', '), '.'),
      h('div', { classe: 'premiers' }, retenir, this.nombre, h('label', { for: id }, 'premières')),
      h('div', { classe: 'retenues' }, this.etatRetenues, this.effacer, this.voir),
      this.liste, this.suite,
    );
  }

  maj(): void {
    const { visibles, scores } = this.modele;
    const sans = visibles.reduce((s, k) => s + (scores[k] === null ? 1 : 0), 0);
    remplacer(this.entete, h('b', {}, pluriel(visibles.length, 'commune')), sans > 0 && ` · ${nombre(sans)} sans score`);
    this.majRetenues();
    this.affichees = 0;
    remplacer(this.liste);
    this.ajouter();
    if (!visibles.length) remplacer(this.liste, h('li', { classe: 'vide' }, 'Aucune commune ne répond à ces filtres.'));
  }

  /** Les cases et le résumé seulement : cocher une commune ne redessine pas la liste. */
  majRetenues(): void {
    const retenues = new Set(this.retenues.lire());
    remplacer(this.etatRetenues, retenues.size
      ? [h('b', {}, pluriel(retenues.size, 'commune retenue', 'communes retenues')), ' pour l’étape des écoles']
      : 'Aucune commune retenue : l’étape des écoles les prend toutes.');
    this.voir.disabled = retenues.size === 0;
    this.effacer.hidden = retenues.size === 0;
    for (const c of this.liste.querySelectorAll<HTMLInputElement>('input[data-code]')) {
      c.checked = retenues.has(c.dataset.code ?? '');
    }
  }

  marquer(code: string | null): void {
    this.choisie = code;
    for (const b of this.liste.querySelectorAll<HTMLElement>('button[data-code]')) {
      if (b.dataset.code === code) b.setAttribute('aria-current', 'true');
      else b.removeAttribute('aria-current');
    }
  }

  private ajouter(): void {
    const { visibles } = this.modele;
    const fin = Math.min(this.affichees + PAR_PAGE, visibles.length);
    this.liste.append(...visibles.slice(this.affichees, fin).map((k, x) => this.ligne(k, this.affichees + x + 1)));
    this.affichees = fin;
    this.suite.hidden = fin >= visibles.length;
    this.majRetenues();
  }

  private ligne(k: number, rang: number): HTMLElement {
    const { meta, scores, connus, t } = this.modele;
    const c = meta.communes[k];
    const s = scores[k];
    const detail = CRITERES_COMMUNES.map(
      (x) => `${COURT_CRITERE_COMMUNE[x]} : ${jaugeOuInsuffisant(this.modele.valeur(x, k))}`,
    ).join('\n');
    const case_ = h('input', {
      type: 'checkbox', 'data-code': c.code, 'aria-label': `Retenir ${c.nom}`,
      onchange: () => {
        const l = this.retenues.lire().filter((x) => x !== c.code);
        this.retenues.changer(case_.checked ? [...l, c.code] : l);
      },
    });
    return h(
      'li', {},
      h('label', { classe: 'retenir' }, case_),
      h(
        'button', {
          type: 'button', 'data-code': c.code, 'aria-current': this.choisie === c.code && 'true', title: detail,
          onclick: () => this.choisir(c.code),
        },
        h('span', { classe: 'rang' }, rang),
        h('span', { classe: 'qui' }, h('b', {}, c.nom),
          h('span', { classe: 'sous' }, [meta.departements[c.dep], t.pat_nom[k]].filter(Boolean).join(' · '))),
        h(
          'span', { classe: 'barres', 'aria-hidden': 'true' },
          CRITERES_COMMUNES.map((x) => {
            const v = this.modele.valeur(x, k);
            return v === null ? h('i', { classe: 'inconnue' }) : h('i', { style: `height:${Math.max(v, 6)}%` });
          }),
        ),
        h(
          'span', { classe: 'note-ecole' },
          h('b', {}, s === null ? '–' : nombre(s)),
          h('span', { classe: 'sous' }, `${connus[k]}/${CRITERES_COMMUNES.length} critères`),
        ),
      ),
    );
  }
}
