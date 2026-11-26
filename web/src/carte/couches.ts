/** Sources et couches de la carte, du dessous (zones) au dessus (écoles). */

import type { ExpressionSpecification, FilterSpecification, LayerSpecification } from '@maplibre/maplibre-gl-style-spec';

import {
  ALIMENTATION, BORNES_IRIS, BORNES_SCORE, bornesDe, ENCRE, ENCRE_2, INCONNU, OPACITE_COMMUNES,
  OPACITE_IRIS, RAMPE_COMMUNES, RAMPE_ECOLES, RAMPE_IRIS, SURFACE, VIE_SCOLAIRE, ZONE_CITE, ZONE_PAT,
} from '../couleurs';
import type { Coloration, Couche, VariableIris } from '../etat';
import { POLICE } from './fond';

export const SOURCES = [
  'iris', 'communes', 'pat', 'cites', 'qpv', 'relais', 'producteurs', 'accueils', 'assos', 'ecoles', 'liens', 'selection',
] as const;
export type NomSource = (typeof SOURCES)[number];
/** Zones qui ont une fiche : source, et propriété qui les identifie. */
export const ZONES_FICHE = { pat: 'id', cites: 'id', qpv: 'id', iris: 'iris' } as const;
export type ZoneFiche = keyof typeof ZONES_FICHE;
const COULEUR_ZONE: Record<ZoneFiche, string> = { pat: ZONE_PAT, cites: ZONE_CITE, qpv: ENCRE_2, iris: ENCRE };
export const IDENTIFIANT: Partial<Record<NomSource, string>> = { communes: 'code', iris: 'iris' };

const survol = (oui: number, non: number): ExpressionSpecification => [
  'case', ['boolean', ['feature-state', 'survol'], false], oui, non,
];
const selonZoom = (...paliers: number[]): ExpressionSpecification =>
  ['interpolate', ['linear'], ['zoom'], ...paliers] as unknown as ExpressionSpecification;

/** Couleur d'une école selon la valeur `v` (-1 : données insuffisantes). */
export function couleurEcole(coloration: Coloration): ExpressionSpecification {
  const bornes = bornesDe(coloration);
  const paliers = bornes.flatMap((b, k) => [b, RAMPE_ECOLES[k + 1]]);
  return [
    'case', ['<', ['get', 'v'], 0], SURFACE, ['step', ['get', 'v'], RAMPE_ECOLES[0], ...paliers],
  ] as unknown as ExpressionSpecification;
}

/**
 * Communes, aux deux étapes : couleur selon le score (état « score » de chaque commune, -1 : inconnu, transparent).
 */
export function peintureCommunes(): { couleur: ExpressionSpecification; opacite: ExpressionSpecification } {
  const score: ExpressionSpecification = ['coalesce', ['feature-state', 'score'], -1];
  const paliers = BORNES_SCORE.flatMap((b, k) => [b, RAMPE_COMMUNES[k + 1]]);
  return {
    couleur: ['case', ['<', score, 0], SURFACE, ['step', score, RAMPE_COMMUNES[0], ...paliers]] as unknown as
      ExpressionSpecification,
    opacite: ['case', ['<', score, 0], 0, survol(OPACITE_COMMUNES + 0.2, OPACITE_COMMUNES)] as unknown as
      ExpressionSpecification,
  };
}

export function couleurIris(variable: VariableIris): ExpressionSpecification {
  const paliers = BORNES_IRIS[variable].flatMap((b, k) => [b, RAMPE_IRIS[k + 1]]);
  return [
    'case', ['has', variable], ['step', ['get', variable], RAMPE_IRIS[0], ...paliers], 'rgba(0,0,0,0)',
  ] as unknown as ExpressionSpecification;
}

const etiquette = (id: string, source: NomSource, minzoom: number, maxzoom = 24): LayerSpecification => ({
  id, source, type: 'symbol', minzoom, maxzoom,
  layout: { 'text-field': ['get', 'nom'], 'text-font': POLICE, 'text-size': 12, 'text-max-width': 9 },
  paint: { 'text-color': ENCRE, 'text-halo-color': SURFACE, 'text-halo-width': 1.6 },
});

const points = (source: 'relais' | 'accueils' | 'assos'): LayerSpecification => ({
  id: source, source, type: 'symbol',
  layout: {
    'icon-image': `s-${source}`, 'icon-allow-overlap': true, 'icon-ignore-placement': true,
    'icon-size': selonZoom(8, 0.4, 11, 0.55, 14, 0.85, 17, 1),
  },
});

export const ZONES: LayerSpecification[] = [
  {
    id: 'iris', source: 'iris', type: 'fill',
    paint: { 'fill-color': couleurIris('familles'), 'fill-opacity': OPACITE_IRIS },
  },
  {
    id: 'iris-trait', source: 'iris', type: 'line', minzoom: 10,
    paint: { 'line-color': SURFACE, 'line-width': selonZoom(10, 0.4, 14, 1.4) },
  },
  {
    id: 'communes', source: 'communes', type: 'fill',
    paint: { 'fill-color': ENCRE, 'fill-opacity': survol(0.06, 0) },
  },
  {
    id: 'communes-trait', source: 'communes', type: 'line',
    paint: { 'line-color': INCONNU, 'line-width': selonZoom(8, 0.4, 12, 1.2), 'line-opacity': 0.7 },
  },
  { id: 'pat', source: 'pat', type: 'fill', paint: { 'fill-color': ZONE_PAT, 'fill-opacity': 0.1 } },
  {
    id: 'pat-trait', source: 'pat', type: 'line',
    paint: { 'line-color': ZONE_PAT, 'line-width': 1.75, 'line-offset': 1 },
  },
  { id: 'cites', source: 'cites', type: 'fill', paint: { 'fill-color': ZONE_CITE, 'fill-opacity': 0.12 } },
  { id: 'cites-trait', source: 'cites', type: 'line', paint: { 'line-color': ZONE_CITE, 'line-width': 2 } },
  { id: 'qpv', source: 'qpv', type: 'fill', paint: { 'fill-pattern': 'hachures' } },
  { id: 'qpv-trait', source: 'qpv', type: 'line', paint: { 'line-color': ENCRE_2, 'line-width': 1.5 } },
  ...(Object.keys(ZONES_FICHE) as ZoneFiche[]).flatMap((z): LayerSpecification[] => [
    {
      id: `${z}-choisi`, source: z, type: 'fill', filter: ['==', ['get', ZONES_FICHE[z]], ''],
      paint: { 'fill-color': COULEUR_ZONE[z], 'fill-opacity': 0.18 },
    },
    {
      id: `${z}-choisi-trait`, source: z, type: 'line', filter: ['==', ['get', ZONES_FICHE[z]], ''],
      paint: { 'line-color': COULEUR_ZONE[z], 'line-width': 3.5 },
    },
  ]),
  {
    id: 'communes-choisie', source: 'communes', type: 'line', filter: ['==', ['get', 'code'], ''],
    paint: { 'line-color': ENCRE, 'line-width': 2.5 },
  },
];

export const MARQUES: LayerSpecification[] = [
  etiquette('pat-nom', 'pat', 8, 12),
  etiquette('cites-nom', 'cites', 11),
  etiquette('qpv-nom', 'qpv', 12.5),
  {
    id: 'liens', source: 'liens', type: 'line',
    paint: {
      'line-color': ['match', ['get', 'famille'], 'alimentation', ALIMENTATION, VIE_SCOLAIRE],
      'line-width': 1.75, 'line-opacity': 0.7,
    },
    layout: { 'line-cap': 'round' },
  },
  points('relais'),
  {
    id: 'producteurs', source: 'producteurs', type: 'symbol',
    layout: {
      'icon-image': ['case', ['get', 'compte'], 's-producteurs', 's-producteurs_autres'],
      'icon-allow-overlap': true, 'icon-ignore-placement': true,
      'icon-size': selonZoom(8, 0.45, 11, 0.6, 14, 0.9, 17, 1),
      'symbol-sort-key': ['case', ['get', 'compte'], 1, 0],
    },
  },
  points('accueils'),
  points('assos'),
  {
    id: 'ecoles', source: 'ecoles', type: 'circle',
    layout: { 'circle-sort-key': ['get', 'v'] },
    paint: {
      'circle-color': couleurEcole('score'),
      'circle-radius': selonZoom(8, 2.6, 10, 3.6, 12, 5.5, 14, 8, 17, 11),
      'circle-stroke-color': [
        'case', ['boolean', ['feature-state', 'survol'], false], ENCRE, ['<', ['get', 'v'], 0], INCONNU, SURFACE,
      ],
      'circle-stroke-width': [
        'interpolate', ['linear'], ['zoom'],
        8, ['case', ['<', ['get', 'v'], 0], 1, 0.4],
        11, ['case', ['<', ['get', 'v'], 0], 1.4, 1],
        13, 2,
      ],
    },
  },
  {
    // Acteur choisi alors que sa couche est masquée : son symbole reste visible.
    id: 'selection-symbole', source: 'selection', type: 'symbol', filter: ['has', 'symbole'],
    layout: {
      'icon-image': ['concat', 's-', ['get', 'symbole']], 'icon-allow-overlap': true, 'icon-ignore-placement': true,
      'icon-size': selonZoom(8, 0.6, 14, 0.9, 17, 1),
    },
  },
  {
    id: 'selection', source: 'selection', type: 'circle',
    paint: {
      'circle-color': 'rgba(0,0,0,0)',
      'circle-radius': selonZoom(8, 7, 12, 10, 14, 13, 17, 17),
      'circle-stroke-color': ENCRE,
      'circle-stroke-width': 2.5,
    },
  },
];

/** Département d'un objet de chaque source : sa propriété `dep`, le début de son code commune, ou sa liste `deps`. */
const DEPARTEMENT: Partial<Record<NomSource, 'dep' | 'commune' | 'deps'>> = {
  communes: 'dep', iris: 'commune', accueils: 'commune', assos: 'commune', producteurs: 'commune', relais: 'commune',
  pat: 'deps', qpv: 'deps', cites: 'deps',
};

/** Filtre MapLibre qui ne garde que les départements choisis ; null : aucun choisi, tout est montré. */
export function filtreDepartements(source: NomSource, deps: readonly string[]): FilterSpecification | null {
  const propriete = DEPARTEMENT[source];
  if (!deps.length || !propriete) return null;
  const texte = (p: string): ExpressionSpecification => ['coalesce', ['get', p], ''] as ExpressionSpecification;
  if (propriete === 'deps') return ['any', ...deps.map((d): ExpressionSpecification => ['in', d, texte('deps')])];
  const dep: ExpressionSpecification = propriete === 'dep' ? texte('dep') : ['slice', texte('commune'), 0, 2];
  return ['in', dep, ['literal', [...deps]]];
}

/** Couches MapLibre de chaque couche activable. */
export const GROUPES: Record<Couche, string[]> = {
  ecoles: ['ecoles'],
  accueils: ['accueils'],
  assos: ['assos'],
  producteurs: ['producteurs'],
  relais: ['relais'],
  communes: ['communes', 'communes-trait'],
  pat: ['pat', 'pat-trait', 'pat-nom'],
  qpv: ['qpv', 'qpv-trait', 'qpv-nom'],
  cites: ['cites', 'cites-trait', 'cites-nom'],
  iris: ['iris', 'iris-trait'],
};
