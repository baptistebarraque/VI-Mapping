/** Emprises : cadrage sur un département ou une zone. */

import { expect, test } from 'vitest';

import { empriseDepartements, empriseZone, reunir } from '../src/carte/emprise';
import type { Meta } from '../src/types';

const meta = {
  communes: [
    { code: '93048', dep: '93', bbox: [2.4, 48.8, 2.5, 48.9] },
    { code: '93066', dep: '93', bbox: [2.3, 48.9, 2.4, 49.0] },
    { code: '75112', dep: '75', bbox: [2.2, 48.7, 2.4, 48.8] },
  ],
} as unknown as Meta;

test('département : réunion des emprises de ses communes', () => {
  expect(empriseDepartements(meta, ['93'])).toEqual([2.3, 48.8, 2.5, 49.0]);
  expect(empriseDepartements(meta, ['77'])).toBeNull();
});

test('plusieurs départements : un cadre qui les contient tous ; aucun : toute la région', () => {
  expect(empriseDepartements(meta, ['75', '93'])).toEqual([2.2, 48.7, 2.5, 49.0]);
  expect(empriseDepartements(meta, ['75', '77'])).toEqual([2.2, 48.7, 2.4, 48.8]);
  expect(empriseDepartements(meta, [])).toEqual([2.2, 48.7, 2.5, 49.0]);
});

test('rien à réunir', () => {
  expect(reunir([])).toBeNull();
});

test('zone : polygone et multipolygone', () => {
  const carre = (x: number, y: number): number[][] => [[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1], [x, y]];
  expect(empriseZone({ type: 'Polygon', coordinates: [carre(2, 48)] })).toEqual([2, 48, 3, 49]);
  expect(empriseZone({ type: 'MultiPolygon', coordinates: [[carre(2, 48)], [carre(5, 47)]] })).toEqual([2, 47, 6, 49]);
  expect(empriseZone({ type: 'Point', coordinates: [2, 48] })).toBeNull();
});
