/** Filtres, classement, recalcul des scores. */

import { beforeEach, describe, expect, test } from 'vitest';

import { etatInitial, filtresVides, type Filtres } from '../src/etat';
import { Modele } from '../src/modele';
import { meta, table } from './exemple';

let m: Modele;

const uai = (f: Partial<Filtres> = {}): string[] => {
  m.filtrer({ ...filtresVides(), ...f });
  return m.visibles.map((i) => table.uai[i][6]);
};

beforeEach(() => {
  const e = etatInitial(meta);
  m = new Modele(meta, table);
  m.recalculerProducteurs(e.rayon);
  m.recalculerScores(e.poids);
});

describe('classement', () => {
  test('score décroissant, école sans score en dernier', () => {
    expect(uai().at(-1)).toBe('2');
    expect(m.scores[1]).toBeNull();
    expect(m.connues[1]).toBe(0);
  });

  test('à score égal, l’école la mieux documentée passe devant', () => {
    m.scores = [50, 50, 50, 50];
    expect(uai()[0]).toBe('1');
  });

  test('une jauge inconnue ne compte pas 0', () => {
    const poids = { engagement: 100, periscolaire: 0, parents: 100, producteurs: 0, familles: 0 };
    m.recalculerScores(poids);
    expect(m.scores[3]).toBe(80); // parents inconnus : la moyenne porte sur l'engagement seul
    expect(m.scores[0]).toBe(75);
  });
});

describe('filtres', () => {
  test('département et commune', () => {
    expect(uai({ departements: ['75'] })).toEqual(['1']);
    expect(uai({ commune: '93048' }).sort()).toEqual(['2', '3', '4']);
  });

  test('Paris entier rassemble ses arrondissements', () => {
    expect(uai({ commune: '75056' })).toEqual(['1']);
    expect(m.parCommune.get('75056')).toEqual([0]);
  });

  test('secteur, type et taille', () => {
    expect(uai({ secteur: 'prive' })).toEqual(['3']);
    expect(uai({ secteur: 'public' }).sort()).toEqual(['1', '2', '4']);
    expect(uai({ types: [0] })).toEqual(['2']);
    expect(uai({ elevesMin: 100 }).sort()).toEqual(['1', '4']); // effectif inconnu : écartée
    expect(uai({ elevesMax: 250 }).sort()).toEqual(['1', '3']);
  });

  test('seuil par jauge : une jauge inconnue est écartée, sauf demande contraire', () => {
    const seuils = { ...filtresVides().seuils, parents: 50 };
    expect(uai({ seuils })).toEqual(['1']);
    expect(uai({ seuils, garderInconnues: true }).sort()).toEqual(['1', '2', '3', '4']);
  });

  test('nombre de jauges connues', () => {
    expect(uai({ connuesMin: 5 })).toEqual(['1']);
    expect(uai({ connuesMin: 4 }).sort()).toEqual(['1', '4']);
  });
});

test('le rayon change la jauge producteurs', () => {
  const large = m.producteurs[2];
  m.recalculerProducteurs({ km: 30, minutes: 45, mode: 'ou' });
  expect(m.producteurs[2]).toBe(0); // producteur connu, hors rayon
  m.recalculerProducteurs({ km: 50, minutes: 90, mode: 'ou' });
  expect(m.producteurs[2]).toBeGreaterThan(large ?? 0);
  expect(m.producteurs[1]).toBeNull(); // école sans proximité calculée
});

test('moyenne sans les inconnues', () => {
  expect(m.moyenne([10, null, 20])).toBe(15);
  expect(m.moyenne([null])).toBeNull();
});
