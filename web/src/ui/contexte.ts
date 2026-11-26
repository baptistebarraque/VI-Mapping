/** Ce dont une fiche a besoin pour se dessiner et pour ouvrir les autres ; boutons vers une instance. */

import type { Cible, Etat } from '../etat';
import type { Modele } from '../modele';
import type { ModeleCommunes } from '../modele-communes';
import type { CollectionPoints, Nature, ProprietesProducteur, ProprietesRelais } from '../types';
import { h, type Enfant } from './dom';

export interface ContexteFiche {
  modele: Modele;
  communes: ModeleCommunes;
  etat: Etat;
  producteurs: CollectionPoints<ProprietesProducteur>;
  relais: CollectionPoints<ProprietesRelais>;
  /** Ouvre la fiche d'une instance et la montre sur la carte. */
  ouvrir: (c: Cible) => void;
  /** Carnet de contacts limité à ces communes. */
  ouvrirCarnet: (codes: string[], titre: string) => void;
}

/** Texte qui ouvre la fiche de l'instance. */
export const bouton = (ctx: Pick<ContexteFiche, 'ouvrir'>, c: Cible, texte: Enfant, fort = false): HTMLElement => h('button', {
  type: 'button', classe: fort ? 'lien fort' : 'lien', onclick: () => ctx.ouvrir(c),
}, texte);

export const boutonActeur = (
  ctx: ContexteFiche, nature: Nature, id: string | undefined, texte: string, fort = true,
): HTMLElement | string => (id === undefined ? texte : bouton(ctx, { type: 'acteur', nature, id }, texte, fort));

export function boutonCommune(ctx: ContexteFiche, code: string | undefined, fort = false): HTMLElement | string | null {
  const c = ctx.modele.meta.communes.find((x) => x.code === code);
  return c ? bouton(ctx, { type: 'commune', code: c.code }, c.nom, fort) : null;
}

export function boutonEcole(ctx: ContexteFiche, uai: string): HTMLElement | string {
  const i = ctx.modele.rang.get(uai);
  return i === undefined ? uai : bouton(ctx, { type: 'ecole', uai }, ctx.modele.t.nom[i], true);
}

/** Déplie un bloc de la fiche ouverte, désigné par son titre, et y fait défiler. */
export function montrerBloc(depuis: Element, titre: string): void {
  const fiche = depuis.closest('.fiche');
  const bloc = [...(fiche?.querySelectorAll('.bloc') ?? [])]
    .find((b) => b.querySelector(':scope > h3, :scope > summary > h3')?.textContent === titre);
  if (!bloc) return;
  if (bloc instanceof HTMLDetailsElement) bloc.open = true;
  bloc.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
}
