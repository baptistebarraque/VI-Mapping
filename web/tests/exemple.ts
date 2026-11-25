/** Petit jeu d'écoles pour les tests : trois communes, dont un arrondissement de Paris. */

import type { Meta, TableEcoles } from '../src/types';

export const meta = {
  genere_le: '2026-11-25T08:00:00',
  departements: { '75': 'Paris', '93': 'Seine-Saint-Denis' },
  poids: { engagement: 25, periscolaire: 25, parents: 15, producteurs: 20, familles: 15 },
  rayon: { km: 30, minutes: 45, mode: 'ou' },
  km_max: 50,
  part_min_score: 0.3,
  producteurs: { sous_poids: { plus_proche: 60, nombre: 40 }, minutes_plein: 15, km_plein: 10, nombre_plein: 5 },
  communes: [
    { code: '75056', nom: 'Paris', dep: '75' },
    { code: '75112', nom: 'Paris 12e', dep: '75', mere: '75056' },
    { code: '93048', nom: 'Montreuil', dep: '93' },
  ],
  sources: {},
} as unknown as Meta;

/** A : complète ; B : sans jauge connue ; C : deux jauges, privée ; D : comme A, à Montreuil, moins documentée. */
export const table: TableEcoles = {
  uai: ['0750001A', '0930002B', '0930003C', '0930004D'],
  nom: ['École A', 'École B', '=Cité; "C"', 'École D'],
  commune: [1, 2, 2, 2],
  type: [1, 0, 2, 1],
  secteur: [0, 0, 1, 0],
  eleves: [200, null, 90, 310],
  ips: [100.5, null, null, 98],
  rep: [0, 1, 0, 2],
  cite: [0, 0, 0, 1],
  lon: [2.4, 2.44, 2.45, 2.46],
  lat: [48.84, 48.86, 48.87, 48.88],
  engagement: [80, null, 50, 80],
  periscolaire: [60, null, null, 60],
  parents: [70, null, null, null],
  producteurs: [null, null, null, null],
  familles: [40, null, 50, 40],
  score: [null, null, null, null],
  confiance: [0.9, 0.1, 0.4, 0.7],
  prod: [[5, 10, 20, 30], null, [40, 60], [5, 10, 20, 30]],
};
