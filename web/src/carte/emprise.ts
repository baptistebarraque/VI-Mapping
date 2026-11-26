/** Emprises [ouest, sud, est, nord] : réunion, départements, zone. */

import type { Geometry, Position } from 'geojson';

import type { Meta } from '../types';

export type Emprise = [number, number, number, number];

export function reunir(emprises: Iterable<Emprise>): Emprise | null {
  let r: Emprise | null = null;
  for (const [o, s, e, n] of emprises) {
    r = r === null ? [o, s, e, n] : [Math.min(r[0], o), Math.min(r[1], s), Math.max(r[2], e), Math.max(r[3], n)];
  }
  return r;
}

/** Départements choisis ensemble : le cadre qui les contient tous ; aucun : toute la région. */
export const empriseDepartements = (meta: Meta, deps: readonly string[]): Emprise | null =>
  reunir(meta.communes.filter((c) => !deps.length || deps.includes(c.dep)).map((c) => c.bbox));

/** Emprise d'un polygone ou d'un multipolygone ; null pour les autres géométries. */
export function empriseZone(g: Geometry): Emprise | null {
  const anneaux: Position[][] = g.type === 'Polygon' ? g.coordinates : g.type === 'MultiPolygon' ? g.coordinates.flat() : [];
  return reunir(anneaux.flat().map(([x, y]): Emprise => [x, y, x, y]));
}
