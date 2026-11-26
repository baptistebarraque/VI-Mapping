/** Fenêtre « Contacts » : qui joindre dans un territoire, e-mails à copier, export CSV avec les sources. */

import { adresses, cibleDe, contactsCsv, NATURES_CONTACT, type NatureContact, type Perimetre } from '../carnet';
import type { Cible } from '../etat';
import { telecharger } from '../csv';
import type { LigneContact, Meta } from '../types';
import { provenance, vide } from './commun';
import { boutonCopier, mailto } from './contact';
import { bouton } from './contexte';
import { h, remplacer } from './dom';
import { LIBELLE_NATURE, LIBELLE_ORGANISME, LIBELLE_RELAIS, nombre, pluriel } from './format';

const PAR_PAGE = 60;
const CCI_MAX = 40; // au-delà, la plupart des logiciels de messagerie coupent le lien
const COCHEES: readonly NatureContact[] = ['commune', 'organisme', 'pat'];

export class CarnetContacts {
  readonly el: HTMLDialogElement;
  private corps = h('div', {});
  private titre = h('p', { classe: 'note' });
  private natures = new Set<NatureContact>(COCHEES);
  private avecEmail = true;

  constructor(private meta: Meta, private ouvrirFiche: (c: Cible) => void) {
    this.el = h(
      'dialog', {
        classe: 'dialogue carnet', 'aria-label': 'Contacts',
        onclick: (e: MouseEvent) => {
          if (e.target === this.el) this.el.close(); // clic sur le fond
        },
      },
      h('div', { classe: 'dialogue-corps' },
        h('div', { classe: 'barre' }, h('h2', {}, 'Contacts'),
          h('button', { type: 'button', classe: 'discret', onclick: () => this.el.close() }, 'Fermer')),
        this.titre, this.corps),
    );
  }

  ouvrir(p: Perimetre, contacts: Promise<LigneContact[]>): void {
    remplacer(this.titre, p.titre);
    remplacer(this.corps, vide('Chargement des contacts…'));
    if (!this.el.open) this.el.showModal();
    contacts.then((l) => this.dessiner(p, l)).catch((e: unknown) => {
      console.error(e);
      remplacer(this.corps, vide('Contacts indisponibles : vérifiez la connexion.'));
    });
  }

  private dessiner(p: Perimetre, toutes: LigneContact[]): void {
    const presentes = NATURES_CONTACT.filter((n) => toutes.some((l) => l.n === n));
    if (!presentes.some((n) => this.natures.has(n))) presentes.forEach((n) => this.natures.add(n));
    const sortie = h('div', {});
    const maj = (): void => {
      const choisies = toutes.filter((l) => this.natures.has(l.n) && (!this.avecEmail || l.email));
      this.resultat(sortie, p, choisies);
    };
    remplacer(
      this.corps,
      h('fieldset', { classe: 'natures' }, h('legend', {}, 'Qui contacter'), presentes.map((n) => {
        const lignes = toutes.filter((l) => l.n === n);
        const avec = lignes.filter((l) => l.email).length;
        const case_ = h('input', {
          type: 'checkbox', checked: this.natures.has(n),
          onchange: () => {
            if (case_.checked) this.natures.add(n);
            else this.natures.delete(n);
            maj();
          },
        });
        return h('label', { classe: 'case' }, case_, h('span', {}, LIBELLE_NATURE[n][1],
          h('span', { classe: 'sous' }, avec === lignes.length ? pluriel(avec, 'e-mail') : `${pluriel(avec, 'e-mail')} sur ${nombre(lignes.length)}`)));
      })),
      this.caseEmail(maj), sortie,
    );
    maj();
  }

  private caseEmail(maj: () => void): HTMLElement {
    const c = h('input', {
      type: 'checkbox', checked: this.avecEmail,
      onchange: () => {
        this.avecEmail = c.checked;
        maj();
      },
    });
    return h('label', { classe: 'case' }, c, h('span', {}, 'Seulement avec un e-mail'));
  }

  private resultat(sortie: HTMLElement, p: Perimetre, lignes: LigneContact[]): void {
    const mails = adresses(lignes);
    const liste = h('ul', { classe: 'liste' });
    const suite = h('button', { type: 'button', classe: 'discret', onclick: () => ajouter() }, 'Afficher la suite');
    let affichees = 0;
    const ajouter = (): void => {
      liste.append(...lignes.slice(affichees, affichees + PAR_PAGE).map((l) => this.ligne(l)));
      affichees += PAR_PAGE;
      suite.hidden = affichees >= lignes.length;
    };
    ajouter();
    const nomFichier = `contacts-${p.titre.toLowerCase().normalize('NFD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}-${this.meta.genere_le.slice(0, 10)}.csv`;
    remplacer(
      sortie,
      h('div', { classe: 'actions' },
        mails.length > 0 && mails.length <= CCI_MAX && h('a', { classe: 'bouton fort', href: `mailto:?bcc=${mails.join(',')}` }, 'Écrire à tous en copie cachée'),
        mails.length > 0 && boutonCopier(() => mails.join('; '), `Copier ${pluriel(mails.length, 'e-mail')}`, mails.length > CCI_MAX ? 'fort' : ''),
        lignes.length > 0 && h('button', {
          type: 'button', onclick: () => telecharger(contactsCsv(lignes, this.meta, location.href), nomFichier),
        }, 'Exporter en CSV')),
      h('p', { classe: 'compte', 'aria-live': 'polite' }, h('b', {}, pluriel(lignes.length, 'contact')),
        ' · source, date et confiance sur chaque ligne et dans le CSV'),
      lignes.length ? [liste, suite] : vide('Aucun contact pour ces choix.'),
    );
  }

  private ligne(l: LigneContact): HTMLElement {
    const commune = this.meta.communes.find((c) => c.code === l.commune)?.nom;
    const nature = l.n === 'organisme' ? LIBELLE_ORGANISME[l.type as keyof typeof LIBELLE_ORGANISME]
      : l.n === 'relais' ? LIBELLE_RELAIS[l.type ?? ''] : LIBELLE_NATURE[l.n][0];
    return h(
      'li', {},
      bouton({
        ouvrir: (c) => {
          this.el.close();
          this.ouvrirFiche(c);
        },
      }, cibleDe(l), l.nom, true),
      h('span', { classe: 'sous' }, [nature, l.service, l.n === 'commune' ? null : commune].filter(Boolean).join(' · ')),
      h('span', { classe: 'sous' },
        l.email && h('a', { href: mailto(l.email) }, l.email), l.email && l.tel && ' · ',
        l.tel && h('a', { href: `tel:${l.tel.replaceAll(' ', '')}` }, l.tel)),
      provenance(l.p, this.meta),
    );
  }
}
