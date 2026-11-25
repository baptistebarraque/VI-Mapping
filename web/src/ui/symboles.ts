/** Symboles des points : mêmes tracés dans la légende (SVG) et sur la carte (canvas). Boîte de 24 × 24. */

import { ALIMENTATION, SURFACE, VIE_SCOLAIRE } from '../couleurs';
import { svg } from './dom';

export type Symbole = 'accueils' | 'assos' | 'producteurs' | 'producteurs_autres' | 'relais';

export const TRACES: Record<Symbole, string> = {
  accueils: 'M5.5 5.5h13v13h-13z',
  assos: 'M12 3.2 20.8 12 12 20.8 3.2 12z',
  producteurs: 'M12 3.6 21 19.4H3z',
  producteurs_autres: 'M12 3.6 21 19.4H3z',
  relais: 'M9 3.5h6V9h5.5v6H15v5.5H9V15H3.5V9H9z',
};

export const COULEURS: Record<Symbole, { fond: string; trait: string; anneau: string }> = {
  accueils: { fond: VIE_SCOLAIRE, trait: VIE_SCOLAIRE, anneau: SURFACE },
  assos: { fond: VIE_SCOLAIRE, trait: VIE_SCOLAIRE, anneau: SURFACE },
  producteurs: { fond: ALIMENTATION, trait: ALIMENTATION, anneau: SURFACE },
  producteurs_autres: { fond: SURFACE, trait: ALIMENTATION, anneau: SURFACE },
  relais: { fond: ALIMENTATION, trait: ALIMENTATION, anneau: SURFACE },
};

/** Image pour la carte : anneau clair de 2 px autour de la forme, pour rester lisible sur les autres marques. */
export function imageSymbole(nom: Symbole, taille = 24, echelle = 2): ImageData {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = taille * echelle;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas 2D indisponible');
  ctx.scale(echelle, echelle);
  const forme = new Path2D(TRACES[nom]);
  const c = COULEURS[nom];
  ctx.lineJoin = 'round';
  ctx.lineWidth = 5;
  ctx.strokeStyle = c.anneau;
  ctx.stroke(forme);
  ctx.fillStyle = c.fond;
  ctx.fill(forme);
  ctx.lineWidth = 1.8;
  ctx.strokeStyle = c.trait;
  ctx.stroke(forme);
  return ctx.getImageData(0, 0, canvas.width, canvas.height);
}

/** Hachures à 45° des quartiers prioritaires. */
export function imageHachures(couleur: string, pas = 8, echelle = 2): ImageData {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = pas * echelle;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas 2D indisponible');
  ctx.scale(echelle, echelle);
  ctx.strokeStyle = couleur;
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (const d of [-pas, 0, pas]) {
    ctx.moveTo(d - 1, pas + 1);
    ctx.lineTo(d + pas + 1, -1);
  }
  ctx.stroke();
  return ctx.getImageData(0, 0, canvas.width, canvas.height);
}

export function symbole(nom: Symbole, taille = 16): SVGElement {
  const c = COULEURS[nom];
  return svg(
    'svg', { width: taille, height: taille, viewBox: '0 0 24 24', 'aria-hidden': 'true', class: 'symbole' },
    svg('path', { d: TRACES[nom], fill: c.fond, stroke: c.trait, 'stroke-width': 1.8, 'stroke-linejoin': 'round' }),
  );
}

export function rond(couleur: string, options: { creux?: boolean; taille?: number } = {}): SVGElement {
  const taille = options.taille ?? 14;
  return svg(
    'svg', { width: taille, height: taille, viewBox: '0 0 24 24', 'aria-hidden': 'true', class: 'symbole' },
    svg('circle', options.creux
      ? { cx: 12, cy: 12, r: 8.5, fill: SURFACE, stroke: couleur, 'stroke-width': 3 }
      : { cx: 12, cy: 12, r: 10, fill: couleur }),
  );
}

/** Échantillon d'une zone : contour et lavis, ou hachures. */
export function zone(trait: string, fond: string, hachures = false, taille = 16): SVGElement {
  const enfants: Node[] = [
    svg('rect', { x: 2, y: 4, width: 20, height: 16, rx: 3, fill: fond, stroke: trait, 'stroke-width': 2 }),
  ];
  if (hachures) {
    enfants.push(svg('path', { d: 'M4 14 12 5M6 19 18 5M13 19l8-9', stroke: trait, 'stroke-width': 1.4, fill: 'none' }));
  }
  return svg(
    'svg', { width: taille, height: taille, viewBox: '0 0 24 24', 'aria-hidden': 'true', class: 'symbole' }, ...enfants,
  );
}
