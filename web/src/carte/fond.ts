/** Fond de plan : style vectoriel gris de l'IGN (Géoplateforme, sans clé). Repli sur un fond uni s'il ne répond pas. */

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

export async function chargerFond(): Promise<Fond> {
  try {
    const r = await fetch(STYLE_IGN, { signal: AbortSignal.timeout(10_000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const style = (await r.json()) as StyleSpecification;
    for (const source of Object.values(style.sources)) {
      if (source.type === 'vector') source.attribution = ATTRIBUTION;
    }
    const couches: LayerSpecification[] = style.layers;
    const derniere = couches.findLastIndex((c) => c.type !== 'symbol');
    return { style, avant: couches[derniere + 1]?.id };
  } catch (e) {
    console.warn('Fond IGN indisponible, fond uni :', e);
    return {
      style: {
        version: 8,
        sources: {},
        layers: [{ id: 'fond-uni', type: 'background', paint: { 'background-color': '#f0efec' } }],
      },
    };
  }
}
