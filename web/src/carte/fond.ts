/**
 * Fond de plan : style vectoriel gris de l'IGN (Géoplateforme, sans clé), adouci et tiré vers le crème de la charte.
 * Repli sur un fond uni s'il ne répond pas.
 */

import type { LayerSpecification, StyleSpecification } from '@maplibre/maplibre-gl-style-spec';

const STYLE_IGN = 'https://data.geopf.fr/annexes/ressources/vectorTiles/styles/PLAN.IGN/gris.json';
const ATTRIBUTION =
  '<a href="https://geoservices.ign.fr/" target="_blank" rel="noopener noreferrer">© IGN – Géoplateforme</a>';
export const POLICE = ['Source Sans Pro Regular'];

export interface Fond {
  style: StyleSpecification;
  /** Première couche de libellés : les zones se glissent dessous. Absente avec le fond uni. */
  avant?: string;
}

const CREME = [251, 248, 242] as const;
/** Libellés et tracés sans utilité ici : numéros de route, altitudes, relief, limites de parcs… */
const INUTILES =
  /num[ée]ro de route|bornes postales|courbe|\bcot[eé]\b|\boro\b|\bocs\b|\bbois\b|limite (militaire|parc)|hydrographique|liaison maritime/i;

/** Mélange une couleur du style (#rrggbb, rgb ou rgba) avec le crème, et garde sa transparence. */
export function adoucir(couleur: string, part: number): string {
  const hexa = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(couleur);
  const fonction = /^rgba?\(([^)]+)\)$/i.exec(couleur);
  const [r, v, b, a = 1] = hexa ? hexa.slice(1).map((x) => parseInt(x, 16)) : (fonction?.[1].split(',').map(Number) ?? []);
  if (![r, v, b, a].every(Number.isFinite)) return couleur;
  const melange = [r, v, b].map((x, k) => Math.round(x + (CREME[k] - x) * part));
  return `rgba(${melange.join(', ')}, ${a})`;
}

function adoucirTout<T>(x: T, part: number): T {
  if (typeof x === 'string') return adoucir(x, part) as T;
  if (Array.isArray(x)) return x.map((y) => adoucirTout(y, part)) as T;
  if (typeof x === 'object' && x !== null) {
    return Object.fromEntries(Object.entries(x).map(([k, y]) => [k, adoucirTout(y, part)])) as T;
  }
  return x;
}

function rechauffer(couches: LayerSpecification[]): LayerSpecification[] {
  return couches.filter((c) => !INUTILES.test(c.id)).map((c) => {
    if (!c.paint) return c;
    const part = c.type === 'symbol' ? 0.35 : 0.5;
    const paint = Object.entries(c.paint).map(([cle, v]) => [cle, cle.endsWith('-color') ? adoucirTout(v, part) : v]);
    return { ...c, paint: Object.fromEntries(paint) } as LayerSpecification;
  });
}

export async function chargerFond(): Promise<Fond> {
  try {
    const r = await fetch(STYLE_IGN, { signal: AbortSignal.timeout(10_000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const style = (await r.json()) as StyleSpecification;
    for (const source of Object.values(style.sources)) {
      if (source.type === 'vector') source.attribution = ATTRIBUTION;
    }
    const couches = rechauffer(style.layers);
    style.layers = couches;
    const derniere = couches.findLastIndex((c) => c.type !== 'symbol');
    return { style, avant: couches[derniere + 1]?.id };
  } catch (e) {
    console.warn('Fond IGN indisponible, fond uni :', e);
    return {
      style: {
        version: 8,
        sources: {},
        layers: [{ id: 'fond-uni', type: 'background', paint: { 'background-color': '#f6f1e8' } }],
      },
    };
  }
}
