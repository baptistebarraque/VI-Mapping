/** Recherche d'une commune par son nom ou son code Insee, sans tenir compte des accents ni des tirets. */

import type { Commune } from './types';

/** « Saint-Ouen-sur-Seine » → « saint ouen sur seine » : minuscules, sans accents, tirets et apostrophes en espaces. */
export function normaliser(texte: string): string {
  return texte
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/**
 * Rangs (dans `communes`) de celles qui répondent à `requete`, les meilleures d'abord : nom qui commence par la
 * requête, puis un mot du nom qui commence par elle, puis nom qui la contient ; code Insee qui commence par elle.
 * À qualité égale, le nom le plus court, puis l'ordre alphabétique.
 */
export function chercherCommunes(communes: readonly Pick<Commune, 'code' | 'nom'>[], requete: string, max = 8): number[] {
  const q = normaliser(requete);
  if (!q) return [];
  const noms = communes.map((c) => normaliser(c.nom));
  const qualite = (k: number): number => {
    const n = noms[k];
    if (n.startsWith(q)) return 0;
    if (n.includes(` ${q}`)) return 1;
    if (n.includes(q)) return 2;
    if (/^\d/.test(q) && communes[k].code.toLowerCase().startsWith(q.replace(/ /g, ''))) return 3;
    return -1;
  };
  const trouvees: [number, number][] = [];
  communes.forEach((_, k) => {
    const x = qualite(k);
    if (x >= 0) trouvees.push([k, x]);
  });
  trouvees.sort(([a, qa], [b, qb]) =>
    qa - qb || noms[a].length - noms[b].length || communes[a].nom.localeCompare(communes[b].nom, 'fr') || a - b);
  return trouvees.slice(0, max).map(([k]) => k);
}
