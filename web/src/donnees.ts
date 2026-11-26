/** Chargement des fichiers de public/donnees, avec le numéro d'export pour ne pas relire un cache périmé. */

import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson';
import type {
  Acteurs, CollectionPoints, Couverture, Fiche, LigneContact, Meta, NatureFichier, ProprietesPat, ProprietesProducteur,
  ProprietesRelais, TableCommunes, TableEcoles,
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
export const chargerCouverture = (): Promise<Couverture> => lire('couverture.json');

export type CollectionPats = FeatureCollection<Polygon | MultiPolygon, ProprietesPat>;
const lus = new Map<string, Promise<unknown>>();

/** Fichier lu une seule fois. */
function unique<T>(chemin: string): Promise<T> {
  let p = lus.get(chemin) as Promise<T> | undefined;
  if (!p) {
    p = lire<T>(chemin);
    p.catch(() => lus.delete(chemin)); // un échec réseau ne doit pas rester en mémoire
    lus.set(chemin, p);
  }
  return p;
}

export const chargerZone = (nom: string): Promise<FeatureCollection> => unique(`zones/${nom}.geojson`);
/** PAT, pour la couche et les fiches. */
export const chargerPats = (): Promise<CollectionPats> => unique('zones/pat.geojson');
export const chargerFiche = (code: string): Promise<Fiche> => unique(`fiches/${code}.json`);
export const chargerActeurs = (nature: NatureFichier): Promise<Acteurs> => unique(`acteurs/${nature}.json`);

/** Carnet de contacts et son index « nature:id ». */
export interface Carnet {
  lignes: LigneContact[];
  par: Map<string, LigneContact>;
}
let carnet: Promise<Carnet> | null = null;
export function chargerContacts(): Promise<Carnet> {
  if (carnet === null) {
    carnet = unique<LigneContact[]>('contacts.json')
      .then((lignes) => ({ lignes, par: new Map(lignes.map((l) => [`${l.n}:${l.id}`, l])) }));
    carnet.catch(() => {
      carnet = null;
    });
  }
  return carnet;
}
