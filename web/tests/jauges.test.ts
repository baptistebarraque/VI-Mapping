/** Mêmes vecteurs que tests/test_formules.py : la carte et le calcul Python doivent donner les mêmes valeurs. */

import { describe, expect, test } from 'vitest';

import vecteurs from '../../tests/vecteurs/jauges.json';
import { jaugeProducteurs, score } from '../src/jauges';
import type { ConfigProducteurs, ParJauge, Rayon } from '../src/types';

const config = vecteurs.config_producteurs as ConfigProducteurs;

describe('jauge producteurs', () => {
  test.each(vecteurs.producteurs)('$cas', (v) => {
    const j = jaugeProducteurs(v.prod, v.rayon as Rayon, config);
    expect(j.valeur).toBe(v.valeur);
    expect(j.nombre).toBe(v.nombre);
  });
});

describe('score global', () => {
  test.each(vecteurs.score)('$cas', (v) => {
    expect(score(v.valeurs as ParJauge<number | null>, v.poids, vecteurs.part_min_score)).toBe(v.score);
  });
});
