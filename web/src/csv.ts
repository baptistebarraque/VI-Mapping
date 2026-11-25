/** Export CSV du classement (séparateur « ; », virgule décimale, BOM : s'ouvre tel quel dans un tableur français). */

import type { Modele } from './modele';
import { EDUCATION_PRIORITAIRE, JAUGES, SECTEURS, TYPES_ECOLE } from './types';

type Cellule = string | number | null | undefined;

/** Un texte qui commence par = + - @ serait lu comme une formule par un tableur : on le neutralise. */
export function cellule(x: Cellule): string {
  if (x === null || x === undefined) return '';
  if (typeof x === 'number') return String(x).replace('.', ',');
  const sur = /^[=+\-@\t\r]/.test(x) ? `'${x}` : x;
  return /[";\n\r]/.test(sur) ? `"${sur.replaceAll('"', '""')}"` : sur;
}

const ENTETE = [
  'rang', 'uai', 'ecole', 'commune', 'code_insee', 'departement', 'type', 'secteur', 'eleves', 'ips',
  'education_prioritaire', 'score', ...JAUGES, 'jauges_connues', 'part_des_criteres_connus',
  'producteurs_dans_le_rayon_plafond_5', 'longitude', 'latitude',
];

export function classementCsv(m: Modele): string {
  const { t, meta } = m;
  const lignes = m.visibles.map((i, rang) => {
    const c = meta.communes[t.commune[i]];
    return [
      rang + 1, t.uai[i], t.nom[i], c.nom, c.code, c.dep, TYPES_ECOLE[t.type[i]], SECTEURS[t.secteur[i]], t.eleves[i],
      t.ips[i], EDUCATION_PRIORITAIRE[t.rep[i]], m.scores[i], ...JAUGES.map((j) => m.valeur(j, i)), m.connues[i],
      t.confiance[i], m.nbProducteurs[i], t.lon[i], t.lat[i],
    ];
  });
  return `﻿${[ENTETE, ...lignes].map((l) => l.map(cellule).join(';')).join('\r\n')}\r\n`;
}

export function telecharger(contenu: string, nom: string): void {
  const url = URL.createObjectURL(new Blob([contenu], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = nom;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
