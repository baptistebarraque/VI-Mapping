/** Coordonnées d'une instance : écrire, appeler, copier. La provenance est toujours écrite dessous. */

import type { Cible } from '../etat';
import type { Contact } from '../types';
import { etiquette, provenance, vide } from './commun';
import { bouton, type ContexteFiche } from './contexte';
import { h, lien, type Enfant } from './dom';

/** Contact de secours : la mairie ou l'école à qui écrire quand l'acteur ne publie pas d'adresse. */
export interface Relais {
  cible: Cible;
  nom: string;
  motif: string;
  contact: Contact;
}

export const mailto = (email: string, sujet?: string): string =>
  `mailto:${email}${sujet ? `?subject=${encodeURIComponent(sujet)}` : ''}`;
const tel = (numero: string): string => `tel:${numero.replaceAll(' ', '')}`;

/** Bouton qui copie un texte et le dit. */
export function boutonCopier(texte: () => string, libelle: string, classe = 'lien'): HTMLButtonElement {
  const b = h('button', {
    type: 'button', classe,
    onclick: () => {
      navigator.clipboard.writeText(texte()).then(() => dire('Copié'), () => dire('Copie impossible'));
    },
  }, libelle);
  let minuterie = 0;
  function dire(x: string): void {
    b.textContent = x;
    b.setAttribute('aria-live', 'polite');
    window.clearTimeout(minuterie);
    minuterie = window.setTimeout(() => {
      b.textContent = libelle;
    }, 1800);
  }
  return b;
}

function coordonnees(c: Contact, sujet: string | undefined): Enfant {
  const actions = [
    c.email && h('a', { classe: 'bouton fort', href: mailto(c.email, sujet) }, 'Écrire'),
    c.tel && h('a', { classe: 'bouton', href: tel(c.tel) }, c.tel),
    lien(c.formulaire, 'Formulaire'),
    lien(c.site, 'Site web'),
  ].filter((x): x is HTMLAnchorElement => Boolean(x));
  for (const a of actions) a.classList.add('bouton');
  return [
    c.service && h('p', { classe: 'note' }, c.service.charAt(0).toUpperCase() + c.service.slice(1)),
    h('p', { classe: 'actions' }, actions),
    c.email && h('p', { classe: 'courriel' }, h('a', { href: mailto(c.email, sujet) }, c.email), ' ',
      boutonCopier(() => c.email as string, 'Copier')),
  ];
}

function ligneRelais(r: Relais, ctx: ContexteFiche, sujet: string | undefined): HTMLElement {
  const c = r.contact;
  return h(
    'li', {},
    bouton(ctx, r.cible, r.nom, true), ' ', etiquette(r.motif),
    h('span', { classe: 'sous' },
      c.email && h('a', { href: mailto(c.email, sujet) }, c.email),
      c.email && c.tel && ' · ',
      c.tel && h('a', { href: tel(c.tel) }, c.tel),
      !c.email && c.formulaire && [c.tel && ' · ', lien(c.formulaire, 'formulaire')]),
    provenance(c.p, ctx.modele.meta),
  );
}

export interface OptionsContact {
  sujet?: string;
  relais?: Relais[];
  absence?: string;
}

export function blocContact(c: Contact | undefined, ctx: ContexteFiche, o: OptionsContact = {}): HTMLElement {
  const relais = (o.relais ?? []).filter((r) => r.contact.email || r.contact.tel || r.contact.formulaire);
  return h(
    'section', { classe: 'contact', 'aria-label': 'Contact' },
    c ? [coordonnees(c, o.sujet), provenance(c.p, ctx.modele.meta)] : vide(o.absence ?? 'Aucun contact publié par les sources.'),
    !c?.email && relais.length > 0 && [
      h('p', { classe: 'note' }, c ? 'Sans e-mail publié, écrire à :' : 'À défaut, écrire à :'),
      h('ul', { classe: 'liste' }, relais.map((r) => ligneRelais(r, ctx, o.sujet))),
    ],
  );
}
