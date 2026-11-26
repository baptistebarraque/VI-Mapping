/** Filtre des couches par départements : propriété lue selon la source. */

import { expect, test } from 'vitest';

import { filtreDepartements } from '../src/carte/couches';

test('aucun département choisi : pas de filtre', () => {
  expect(filtreDepartements('communes', [])).toBeNull();
  expect(filtreDepartements('liens', ['93'])).toBeNull(); // source sans département
});

test('communes : leur propriété dep', () => {
  expect(filtreDepartements('communes', ['75', '93'])).toEqual(['in', ['coalesce', ['get', 'dep'], ''], ['literal', ['75', '93']]]);
});

test('points et IRIS : les deux premiers chiffres de leur code commune', () => {
  expect(filtreDepartements('assos', ['93'])).toEqual(
    ['in', ['slice', ['coalesce', ['get', 'commune'], ''], 0, 2], ['literal', ['93']]],
  );
});

test('PAT, QPV, cités : au moins un de leurs départements', () => {
  expect(filtreDepartements('pat', ['75', '93'])).toEqual(['any',
    ['in', '75', ['coalesce', ['get', 'deps'], '']],
    ['in', '93', ['coalesce', ['get', 'deps'], '']],
  ]);
});
