/** Point d'accès « relancer l'analyse » : demandes refusées, lecture du bilan. */

import { describe, expect, test } from 'vitest';

import { lireBilan, refus } from '../serveur/analyse.mjs';

const headers = { origin: 'http://localhost:5173', host: 'localhost:5173', 'x-vi-analyse': '1' };

describe('demandes', () => {
  test('acceptée depuis la carte', () => {
    expect(refus({ method: 'POST', headers }, '0750132L')).toBeNull();
  });

  test('refusées', () => {
    expect(refus({ method: 'GET', headers }, '0750132L')).toBe(405);
    expect(refus({ method: 'POST', headers: { ...headers, origin: 'https://exemple.fr' } }, '0750132L')).toBe(403);
    expect(refus({ method: 'POST', headers: { ...headers, origin: undefined } }, '0750132L')).toBe(403);
    expect(refus({ method: 'POST', headers: { ...headers, 'x-vi-analyse': undefined } }, '0750132L')).toBe(403);
  });

  test.each(['', '--help', '0750132', '0750132l', '0750132L/x', '0750132L;ls'])('école mal nommée : %s', (uai) => {
    expect(refus({ method: 'POST', headers }, uai)).toBe(400);
  });
});

test('bilan sur la dernière ligne', () => {
  expect(lireBilan('ok\n{"uai": "0750132L", "visite": "faite", "echecs": []}\n').visite).toBe('faite');
});
