/**
 * Couleurs de la charte Vraiment irrésistibles (brochure d'octobre 2026), choisies par rôle.
 * Écoles : une rampe verte du clair au foncé. Autres points : deux familles de couleur, distinguées entre elles par
 * la forme — violet pour la vie scolaire (accueils, associations), rouge pour l'alimentation (producteurs, relais).
 * Rampe des écoles et couple violet-rouge vérifiés (vision normale et daltonienne). Les couleurs des cinq jauges
 * (style.css) ne se suffisent pas à elles seules : l'ordre est fixe, et le nom est écrit à côté ou dans l'infobulle.
 */

import type { Coloration, VariableIris } from './etat';

export const RAMPE_ECOLES = ['#7fc475', '#52a94f', '#2f8a3c', '#176a2f', '#0b4722'] as const;
export const BORNES_SCORE = [50, 60, 70, 80] as const;
export const BORNES_JAUGE = [20, 40, 60, 80] as const;
export const bornesDe = (c: Coloration): readonly number[] => (c === 'score' ? BORNES_SCORE : BORNES_JAUGE);

export const INCONNU = '#8f877d';
export const SURFACE = '#ffffff';
export const ENCRE = '#1d1b1a';
export const ENCRE_2 = '#5c5650';
export const VIE_SCOLAIRE = '#574f7a';
export const ALIMENTATION = '#ee2c30';
/** Zones : violet des collectivités pour les PAT, rose des écoles pour les cités éducatives. */
export const ZONE_PAT = '#574f7a';
export const ZONE_CITE = '#ed1e79';

/** Rampe jaune, couleur des familles (deuxième échelle séquentielle) pour les IRIS. */
export const RAMPE_IRIS = ['#fff0a8', '#ffdc4a', '#eebb00', '#bb8b00', '#836000'] as const;
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
