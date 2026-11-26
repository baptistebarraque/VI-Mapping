/** Champ « Chercher une commune » de l'en-tête : suggestions au fil de la frappe, au clavier comme à la souris. */

import type { ModeleCommunes } from '../modele-communes';
import { chercherCommunes } from '../recherche';
import { h, identifiant, remplacer } from './dom';
import { nombre } from './format';

export function rechercheCommune(communes: ModeleCommunes, ouvrir: (code: string) => void): HTMLElement {
  const { meta } = communes;
  const idListe = identifiant('suggestions');
  let trouvees: number[] = [];
  let active = -1;

  const champ = h('input', {
    type: 'search', role: 'combobox', autocomplete: 'off', spellcheck: 'false',
    placeholder: 'Chercher une commune', 'aria-label': 'Chercher une commune par son nom ou son code Insee',
    'aria-autocomplete': 'list', 'aria-controls': idListe, 'aria-expanded': 'false',
    oninput: () => proposer(),
    onfocus: () => proposer(),
    onkeydown: (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (!trouvees.length) return proposer();
        const n = trouvees.length;
        const bas = e.key === 'ArrowDown';
        marquer(active < 0 ? (bas ? 0 : n - 1) : (active + (bas ? 1 : -1) + n) % n);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const k = trouvees[active < 0 ? 0 : active];
        if (k !== undefined) choisir(k);
      } else if (e.key === 'Escape') {
        if (!liste.hidden) e.preventDefault();
        fermer();
      }
    },
  });
  const liste = h('ul', { id: idListe, role: 'listbox', classe: 'suggestions', hidden: true, 'aria-label': 'Communes' });
  const el = h('div', { classe: 'recherche', role: 'search' }, champ, liste);
  // Un clic ailleurs ferme la liste ; mousedown sur une suggestion garde le focus dans le champ.
  document.addEventListener('pointerdown', (e) => {
    if (!el.contains(e.target as Node)) fermer();
  });

  function proposer(): void {
    trouvees = chercherCommunes(meta.communes, champ.value);
    active = -1;
    const rangs = new Map(communes.visibles.map((k, r) => [k, r + 1]));
    remplacer(liste, champ.value.trim() && !trouvees.length
      ? h('li', { classe: 'aucune' }, 'Aucune commune de ce nom en Île-de-France.')
      : trouvees.map((k, r) => {
        const c = meta.communes[k];
        const s = communes.scores[k];
        const rang = rangs.get(k);
        return h(
          'li', {
            id: `${idListe}-${r}`, role: 'option', 'aria-selected': 'false',
            onpointerdown: (e: PointerEvent) => e.preventDefault(),
            onclick: () => choisir(k),
          },
          h('span', { classe: 'qui' }, h('b', {}, c.nom), h('span', { classe: 'sous' }, [
            meta.departements[c.dep] ?? c.dep,
            rang ? `${rang === 1 ? '1re' : `${nombre(rang)}e`} sur ${nombre(communes.visibles.length)} au classement` : null,
            `${c.ecoles} école${c.ecoles > 1 ? 's' : ''}`,
          ].filter(Boolean).join(' · '))),
          h('span', { classe: 'note-ecole', title: 'Score de la commune sur 100' }, s === null ? '–' : nombre(s)),
        );
      }));
    const ouverte = liste.childElementCount > 0;
    liste.hidden = !ouverte;
    champ.setAttribute('aria-expanded', String(ouverte));
    champ.removeAttribute('aria-activedescendant');
  }

  function marquer(r: number): void {
    active = r;
    for (const [i, li] of [...liste.children].entries()) li.setAttribute('aria-selected', String(i === r));
    champ.setAttribute('aria-activedescendant', `${idListe}-${r}`);
    liste.children[r]?.scrollIntoView({ block: 'nearest' });
  }

  function fermer(): void {
    liste.hidden = true;
    champ.setAttribute('aria-expanded', 'false');
    champ.removeAttribute('aria-activedescendant');
    active = -1;
  }

  function choisir(k: number): void {
    champ.value = '';
    fermer();
    champ.blur();
    ouvrir(meta.communes[k].code);
  }

  return el;
}
