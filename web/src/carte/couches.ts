/** Sources et couches de la carte, du dessous (zones) au dessus (écoles). */

import type { ExpressionSpecification, LayerSpecification } from '@maplibre/maplibre-gl-style-spec';

import {
  ALIMENTATION, BORNES_IRIS, bornesDe, ENCRE, ENCRE_2, INCONNU, OPACITE_IRIS, RAMPE_ECOLES, RAMPE_IRIS, SURFACE,
  VIE_SCOLAIRE, ZONE_CITE, ZONE_PAT,
} from '../couleurs';
import type { Coloration, Couche, VariableIris } from '../etat';
import { POLICE } from './fond';

export const SOURCES = [
  'iris', 'communes', 'pat', 'cites', 'qpv', 'relais', 'producteurs', 'accueils', 'assos', 'ecoles', 'liens', 'selection',
] as const;
export type NomSource = (typeof SOURCES)[number];
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
  {
    id: 'pat-choisi', source: 'pat', type: 'fill', filter: ['==', ['get', 'id'], ''],
    paint: { 'fill-color': ZONE_PAT, 'fill-opacity': 0.18 },
  },
  {
    id: 'pat-choisi-trait', source: 'pat', type: 'line', filter: ['==', ['get', 'id'], ''],
    paint: { 'line-color': ZONE_PAT, 'line-width': 3.5 },
  },
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
    id: 'selection', source: 'selection', type: 'circle',
    paint: {
      'circle-color': 'rgba(0,0,0,0)',
      'circle-radius': selonZoom(8, 7, 12, 10, 14, 13, 17, 17),
      'circle-stroke-color': ENCRE,
      'circle-stroke-width': 2.5,
    },
  },
];

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
