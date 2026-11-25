/** Fiche d'un projet alimentaire territorial : labellisation, périmètre, écoles couvertes. */

import type { ProprietesPat } from '../types';
import { bloc, definition, listeRepliee, provenance, vide } from './commun';
import { h, lien } from './dom';
import { blocEcoles, resumeEcoles } from './fiche-commune';
import type { ContexteFiche } from './fiche-ecole';
import { ouiNonInconnu, pluriel } from './format';

export function fichePat(p: ProprietesPat, ctx: ContexteFiche): HTMLElement {
  const { modele } = ctx;
  const { meta } = modele;
  const couvertes = new Set(p.communes ?? []);
  const communes = meta.communes.filter((c) => couvertes.has(c.code)).sort((a, b) => a.nom.localeCompare(b.nom, 'fr'));
  const ecoles = [...new Set(communes.flatMap((c) => modele.parCommune.get(c.code) ?? []))];
  const departements = [...new Set(communes.map((c) => c.dep))].sort().map((d) => meta.departements[d]);
  return h(
    'article', { classe: 'fiche' },
    h('p', { classe: 'surtitre' }, 'Projet alimentaire territorial'),
    h('h2', {}, p.nom),
    h('p', { classe: 'lieu' }, departements.join(', ')),
    p.communes && resumeEcoles(ecoles, modele, 'Aucune école dans ce périmètre.'),
    bloc(
      'Projet',
      definition(
        ['Reconnaissance', [p.niveau, p.annee].filter(Boolean).join(', ') || 'inconnue'],
        ['Axe éducation alimentaire', ouiNonInconnu(p.axe)],
        ['Lauréat de l’appel à projets du PNA', p.laureat ? 'oui' : 'non'],
        lien(p.u, 'x') && ['Fiche du projet', lien(p.u, 'france-pat.fr')],
      ),
      provenance(p, meta),
    ),
    bloc(
      'Communes d’Île-de-France couvertes',
      p.communes === undefined ? vide('Liste absente de cet export : relancez « vi exporter ».') : h(
        'div', {},
        h('p', { classe: 'note' }, pluriel(communes.length, 'commune')),
        listeRepliee(communes.map((c) => h('li', { classe: 'proche' },
          h('button', { type: 'button', classe: 'lien fort', onclick: () => ctx.ouvrirCommune(c.code) }, c.nom),
          h('span', { classe: 'trajet' }, pluriel(modele.parCommune.get(c.code)?.length ?? 0, 'école')))), 8)),
    ),
    blocEcoles(ecoles, ctx),
  );
}
