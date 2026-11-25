/** Chargement des fichiers de public/donnees, avec le numéro d'export pour ne pas relire un cache périmé. */

import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson';
import type {
  CollectionPoints, Couverture, Fiche, Meta, ProprietesPat, ProprietesProducteur, ProprietesRelais, TableCommunes,
  TableEcoles,
} from './types';

const RACINE = `${import.meta.env.BASE_URL}donnees/`;
let version = '';

async function lire<T>(chemin: string, options?: RequestInit): Promise<T> {
  const r = await fetch(adresse(chemin), options);
  if (!r.ok) throw new Error(`${chemin} : HTTP ${r.status}`);
  return (await r.json()) as T;
}

export const adresse = (chemin: string): string =>
  new URL(`${RACINE}${chemin}${version && `?v=${encodeURIComponent(version)}`}`, document.baseURI).href;

export async function chargerMeta(): Promise<Meta> {
  const meta = await lire<Meta>('meta.json', { cache: 'no-cache' });
  version = meta.genere_le;
  return meta;
}

export const chargerEcoles = (): Promise<TableEcoles> => lire('ecoles.json');
export const chargerCommunes = (): Promise<TableCommunes> => lire('communes.json');
export const chargerProducteurs = (): Promise<CollectionPoints<ProprietesProducteur>> =>
  lire('points/producteurs.geojson');
export const chargerRelais = (): Promise<CollectionPoints<ProprietesRelais>> => lire('points/relais.geojson');
export const chargerZone = (nom: string): Promise<FeatureCollection> => lire(`zones/${nom}.geojson`);
export const chargerCouverture = (): Promise<Couverture> => lire('couverture.json');

export type CollectionPats = FeatureCollection<Polygon | MultiPolygon, ProprietesPat>;
let pats: Promise<CollectionPats> | null = null;

/** PAT, pour la couche et les fiches : lus une seule fois. */
export function chargerPats(): Promise<CollectionPats> {
  if (pats === null) {
    pats = lire<CollectionPats>('zones/pat.geojson');
    pats.catch(() => {
      pats = null;
    });
  }
  return pats;
}

const fiches = new Map<string, Promise<Fiche>>();

export function chargerFiche(code: string): Promise<Fiche> {
  let p = fiches.get(code);
  if (!p) {
    p = lire<Fiche>(`fiches/${code}.json`);
    p.catch(() => fiches.delete(code)); // un échec réseau ne doit pas rester en mémoire
    fiches.set(code, p);
  }
  return p;
}
