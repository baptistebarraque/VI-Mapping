/** Recherche d'une commune : accents, tirets, ordre des suggestions. */

import { describe, expect, test } from 'vitest';

import { chercherCommunes, normaliser } from '../src/recherche';

const communes = [
  { code: '93066', nom: 'Saint-Denis' },
  { code: '93070', nom: 'Saint-Ouen-sur-Seine' },
  { code: '92035', nom: 'La Garenne-Colombes' },
  { code: '93008', nom: 'Bobigny' },
  { code: '91228', nom: 'Évry-Courcouronnes' },
  { code: '77186', nom: 'Fontenay-Trésigny' },
  { code: '94033', nom: 'Fontenay-sous-Bois' },
];
const noms = (q: string): string[] => chercherCommunes(communes, q).map((k) => communes[k].nom);

describe('normaliser', () => {
  test('sans accents, tirets ni apostrophes', () => {
    expect(normaliser('  Évry-Courcouronnes ')).toBe('evry courcouronnes');
    expect(normaliser('L’Haÿ-les-Roses')).toBe('l hay les roses');
  });
});

describe('chercherCommunes', () => {
  test('ignore accents, casse et tirets', () => {
    expect(noms('saint denis')).toEqual(['Saint-Denis']);
    expect(noms('EVRY')).toEqual(['Évry-Courcouronnes']);
    expect(noms('tresigny')).toEqual(['Fontenay-Trésigny']);
  });

  test('début du nom, puis début d’un mot, puis milieu', () => {
    expect(noms('saint')).toEqual(['Saint-Denis', 'Saint-Ouen-sur-Seine']);
    expect(noms('colombes')).toEqual(['La Garenne-Colombes']);
    expect(noms('bign')).toEqual(['Bobigny']);
    expect(noms('fontenay')).toEqual(['Fontenay-Trésigny', 'Fontenay-sous-Bois']);
  });

  test('code Insee', () => {
    expect(noms('9306')).toEqual(['Saint-Denis']);
    expect(noms('93')).toEqual(['Bobigny', 'Saint-Denis', 'Saint-Ouen-sur-Seine']);
  });

  test('requête vide ou sans résultat', () => {
    expect(noms('  ')).toEqual([]);
    expect(noms('marseille')).toEqual([]);
  });

  test('nombre de suggestions limité', () => {
    expect(chercherCommunes(communes, 'e', 3)).toHaveLength(3);
  });
});
