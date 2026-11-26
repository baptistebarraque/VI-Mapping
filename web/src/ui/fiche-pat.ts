/** Fiche d'un projet alimentaire territorial : contact du porteur, labellisation, périmètre, écoles couvertes. */

import type { Carnet } from '../donnees';
import type { ProprietesPat } from '../types';
import { bloc, definition, provenance, tableSources } from './commun';
import { blocContact } from './contact';
import { boutonActeur, boutonCommune, type ContexteFiche } from './contexte';
import { h, lien } from './dom';
import { collectivite, mairie, voletCommunes } from './fiche-acteur';
import { blocEcoles, resumeEcoles } from './fiche-commune';
import { ouiNonInconnu } from './format';

export function fichePat(p: ProprietesPat, carnet: Carnet, ctx: ContexteFiche): HTMLElement {
  const { modele } = ctx;
  const { meta } = modele;
  const codes = p.communes ?? [];
  const couvertes = new Set(codes);
  const communes = meta.communes.filter((c) => couvertes.has(c.code));
  const ecoles = [...new Set(communes.flatMap((c) => modele.parCommune.get(c.code) ?? []))];
  const departements = [...new Set(communes.map((c) => c.dep))].sort().map((d) => meta.departements[d]);
  const porteur = p.organisme ? boutonActeur(ctx, 'organisme', p.organisme, p.porteur ?? 'Voir la collectivité', false)
    : boutonCommune(ctx, p.commune) ?? p.porteur;
  return h(
    'article', { classe: 'fiche' },
    h('p', { classe: 'surtitre' }, 'Projet alimentaire territorial'),
    h('h2', {}, p.nom),
    h('p', { classe: 'lieu' }, departements.join(', ')),
    blocContact(p.contact, ctx, {
      relais: [...collectivite(carnet, p.organisme, 'porteur'), ...mairie(carnet, p.commune, 'porteur')],
    }),
    resumeEcoles(ecoles, modele, 'Aucune école dans ce périmètre.'),
    bloc(
      'Projet',
      definition(
        porteur && ['Porteur', porteur],
        p.contact?.service && ['Service', p.contact.service],
        ['Reconnaissance', [p.niveau, p.annee].filter(Boolean).join(', ') || 'inconnue'],
        ['Axe éducation alimentaire', ouiNonInconnu(p.axe)],
        ['Axe restauration collective', ouiNonInconnu(p.restauration)],
        ['Lauréat de l’appel à projets du PNA', p.laureat ? 'oui' : 'non'],
        p.priorites && ['Priorités', p.priorites],
        lien(p.u, 'x') && ['Fiche du projet', lien(p.u, new URL(p.u).hostname.replace('www.', ''))],
      ),
      provenance(p, meta),
    ),
    voletCommunes(codes, ctx, 'Communes d’Île-de-France couvertes'),
    blocEcoles(ecoles, ctx),
    codes.length > 0 && h('p', { classe: 'pied' }, h('button', {
      type: 'button', onclick: () => ctx.ouvrirCarnet(codes, p.nom),
    }, 'Contacts de ce territoire')),
    tableSources(meta, p),
  );
}
