/** Fenêtre « Méthode et sources » : lecture du score, sources utilisées, sources écartées. */

import { JAUGES, type Meta, type Source } from '../types';
import { h, lien, type Enfant } from './dom';
import { date, LIBELLE_CRITERE, LIBELLE_JAUGE, LIBELLE_METHODE, nombre } from './format';

export function ouvrirDialogue(el: HTMLDialogElement): void {
  if (!el.open) el.showModal();
}

export function dialogueSources(meta: Meta, couverture: () => Promise<HTMLElement>): HTMLDialogElement {
  const emplacement = h('div', {});
  const fermer = h('button', { type: 'button', classe: 'discret', onclick: () => el.close() }, 'Fermer');
  const sources = Object.values(meta.sources);
  const utilisees = sources.filter((s) => !s.verrouillee && s.methode !== 'calcul');
  const ecartees = sources.filter((s) => s.verrouillee);
  const el = h(
    'dialog', {
      classe: 'dialogue', 'aria-label': 'Méthode et sources',
      onclick: (e: MouseEvent) => {
        if (e.target === el) el.close(); // clic sur le fond
      },
    },
    h('div', { classe: 'dialogue-corps' },
      h('div', { classe: 'barre' }, h('h2', {}, 'Méthode et sources'), fermer),
      h('p', { classe: 'note' }, `Données exportées le ${date(meta.genere_le)}. Aucune saisie manuelle.`),
      methode(meta),
      emplacement,
      h('h3', {}, 'Sources utilisées'),
      tableau(['Source', 'Producteur', 'Méthode', 'Licence', 'Mise à jour', 'Dernière collecte'], utilisees.map((s) => [
        lien(s.url, s.libelle) ?? s.libelle, s.producteur, LIBELLE_METHODE[s.methode], s.licence, s.frequence,
        s.collecte ? date(s.collecte) : 'pas encore collectée',
      ])),
      h('h3', {}, 'Sources écartées'),
      h('p', { classe: 'note' }, 'Conditions d’utilisation ou droits de fouille qui interdisent la collecte automatique.'),
      tableau(['Source', 'Constat', 'Remplacée par'], ecartees.map((s) => [
        lien(s.url, s.libelle) ?? s.libelle, s.constat, remplacement(s, meta),
      ]))),
  );
  let chargee = false;
  const ouvrir = el.showModal.bind(el);
  el.showModal = () => {
    ouvrir();
    if (chargee) return;
    chargee = true;
    couverture().then((x) => emplacement.append(x)).catch(() => {
      chargee = false; // nouvel essai à la prochaine ouverture
    });
  };
  return el;
}

function remplacement(s: Source, meta: Meta): string {
  return (s.remplacement ?? []).map((c) => meta.sources[c]?.libelle ?? c).join(', ') || 'aucune';
}

export function tableau(entetes: string[], lignes: Enfant[][]): HTMLElement {
  return h('div', { classe: 'defile' }, h(
    'table', { classe: 'table-sources' },
    h('thead', {}, h('tr', {}, entetes.map((t) => h('th', { scope: 'col' }, t)))),
    h('tbody', {}, lignes.map((l) => h('tr', {}, l.map((x) => h('td', {}, x))))),
  ));
}

function methode(meta: Meta): HTMLElement {
  return h(
    'details', { classe: 'bloc replie', open: true },
    h('summary', {}, h('h3', {}, 'Comment lire le score')),
    h('ul', { classe: 'liste' },
      h('li', {}, 'Chaque jauge va de 0 à 100 : moyenne de ses critères connus, pondérée par leur sous-poids.'),
      h('li', {}, 'Un critère ou une jauge sans donnée sort de la moyenne. Il ne compte pas 0.'),
      h('li', {}, `Le score s’affiche si les jauges connues pèsent au moins ${nombre(100 * meta.part_min_score)} % du total.`),
      h('li', {}, 'Une école peu documentée peut avoir un bon score sur peu de critères : regardez « n/5 jauges ».'),
      h('li', {}, 'Une absence dans les sources ouvertes n’est pas une absence sur le terrain.')),
    tableau(['Jauge', 'Poids par défaut', 'Critères (sous-poids)'], JAUGES.map((j) => [
      LIBELLE_JAUGE[j], `${nombre(meta.poids[j])} %`,
      Object.entries(meta.sous_poids[j]).map(([c, p]) => `${LIBELLE_CRITERE[c] ?? c} (${nombre(p)})`).join(', '),
    ])),
  );
}
