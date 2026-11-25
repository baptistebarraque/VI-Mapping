/** Étape 1 : classement des communes, puis écoles des communes retenues. */

import { beforeEach, describe, expect, test } from 'vitest';

import { etatInitial, filtresVides, type Filtres } from '../src/etat';
import { Modele } from '../src/modele';
import { ModeleCommunes } from '../src/modele-communes';
import { meta, table, tableCommunes } from './exemple';

let ecoles: Modele;
let communes: ModeleCommunes;

const codes = (f: Partial<Filtres> = {}): string[] => {
  communes.filtrer({ ...filtresVides(), ...f });
  return communes.visibles.map((k) => meta.communes[k].code);
};

beforeEach(() => {
  const e = etatInitial(meta);
  ecoles = new Modele(meta, table);
  ecoles.recalculerProducteurs(e.rayon);
  ecoles.recalculerScores(e.poids);
  communes = new ModeleCommunes(meta, tableCommunes, ecoles);
  communes.recalculerProducteurs();
  communes.recalculerScores(e.poidsCommunes);
});

describe('communes', () => {
  test('producteurs : moyenne de la jauge des écoles de la commune', () => {
    const montreuil = communes.rang.get('93048') as number;
    const attendu = [1, 2, 3].map((i) => ecoles.producteurs[i]).filter((v) => v !== null) as number[];
    expect(communes.producteurs[montreuil]).toBeCloseTo(attendu.reduce((a, b) => a + b, 0) / attendu.length, 1);
  });

  test('seules les communes qui ont des écoles sont classées, de la meilleure à la moins bonne', () => {
    expect(codes()).toEqual(['75112', '93048']);
    expect(codes({ departements: ['93'] })).toEqual(['93048']);
  });

  test('les poids changent le classement', () => {
    const poids = { ...etatInitial(meta).poidsCommunes, pat: 100, cuisine: 0, cantine_bio: 0, associations: 0,
      communications: 0, ecoles: 0, soutiens: 0, producteurs: 0 };
    communes.recalculerScores(poids);
    expect(codes()[0]).toBe('93048'); // PAT 100 contre 80
  });

  test('nombre minimal de critères connus', () => {
    expect(codes({ criteresMin: 7 })).toEqual(['75112']);
  });

  test('les premières communes, puis seulement leurs écoles', () => {
    codes();
    const retenues = communes.premieres(1);
    expect(retenues).toEqual(['75112']);
    ecoles.filtrer({ ...filtresVides(), retenues });
    expect(ecoles.visibles.map((i) => table.uai[i])).toEqual(['0750001A']);
    ecoles.filtrer({ ...filtresVides(), retenues: ['75056'] }); // Paris entier : tous ses arrondissements
    expect(ecoles.visibles.map((i) => table.uai[i])).toEqual(['0750001A']);
  });
});
