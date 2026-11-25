/**
 * Couleurs, choisies par rôle et vérifiées (séparation en vision normale et daltonienne, contraste).
 * Écoles : une rampe bleue du clair au foncé. Autres points : deux familles de couleur, distinguées entre elles par
 * la forme — orange pour la vie scolaire (accueils, associations), vert pour l'alimentation (producteurs, relais).
 */

import type { Coloration, VariableIris } from './etat';

export const RAMPE_ECOLES = ['#86b6ef', '#5598e7', '#2a78d6', '#1c5cab', '#104281'] as const;
export const BORNES_SCORE = [50, 60, 70, 80] as const;
export const BORNES_JAUGE = [20, 40, 60, 80] as const;
export const bornesDe = (c: Coloration): readonly number[] => (c === 'score' ? BORNES_SCORE : BORNES_JAUGE);

export const INCONNU = '#898781';
export const SURFACE = '#fcfcfb';
export const ENCRE = '#0b0b0b';
export const ENCRE_2 = '#52514e';
export const VIE_SCOLAIRE = '#eb6834';
export const ALIMENTATION = '#1baf7a';

/** Rampe orange (deuxième échelle séquentielle) pour les IRIS. */
export const RAMPE_IRIS = ['#ffdacd', '#fcb69c', '#f7906b', '#e96632', '#be4b19'] as const;
export const OPACITE_IRIS = 0.6; // le fond de plan reste lisible dessous
export const BORNES_IRIS: Record<VariableIris, readonly number[]> = {
  familles: [200, 400, 600, 800],
  revenu: [18000, 22000, 26000, 30000],
  pauvrete: [10, 15, 20, 30],
};

export function classe(valeur: number, bornes: readonly number[]): number {
  let k = 0;
  while (k < bornes.length && valeur >= bornes[k]) k++;
  return k;
}
