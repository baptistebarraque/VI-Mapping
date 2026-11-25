/** Données écrites par `vi exporter` (src/vi_mapping/export). Un champ absent vaut « inconnu ». */

import type { FeatureCollection, Point } from 'geojson';

export const JAUGES = ['engagement', 'periscolaire', 'parents', 'producteurs', 'familles'] as const;
export type NomJauge = (typeof JAUGES)[number];
export type ParJauge<T> = Record<NomJauge, T>;

export type Mode = 'ou' | 'km' | 'minutes';
export interface Rayon {
  km: number;
  minutes: number;
  mode: Mode;
}

/** s : source, u : url, d : date de collecte, c : confiance (0 à 1). La méthode est celle de la source. */
export interface Provenance {
  s: string;
  u: string;
  d: string;
  c: number;
}
export type Provenances = Record<string, Provenance>;

export interface Commune {
  code: string;
  nom: string;
  dep: string;
  mere?: string;
  ecoles: number;
  bbox: [number, number, number, number];
}

export interface Source {
  libelle: string;
  producteur: string;
  url: string;
  licence: string;
  methode: 'api' | 'csv' | 'scraping' | 'calcul';
  frequence: string;
  verrouillee?: boolean;
  collecte?: string;
  constat?: string;
  remplacement?: string[];
}

export interface ConfigProducteurs {
  sous_poids: { plus_proche: number; nombre: number };
  minutes_plein: number;
  km_plein: number;
  nombre_plein: number;
}

export interface Meta {
  genere_le: string;
  config: string;
  departements: Record<string, string>;
  bbox: [number, number, number, number];
  poids: ParJauge<number>;
  rayon: Rayon;
  km_max: number;
  part_min_score: number;
  producteurs: ConfigProducteurs;
  sous_poids: ParJauge<Record<string, number>>;
  seuils: {
    web_mois: number;
    parents_mois: number;
    accueil_m: number;
    asso_confiance: number;
    bio_pct_plein: number;
  };
  communes: Commune[];
  sources: Record<string, Source>;
}

export const TYPES_ECOLE = ['Maternelle', 'Élémentaire', 'Primaire'] as const;
export const SECTEURS = ['Publique', 'Privée sous contrat'] as const;
export const EDUCATION_PRIORITAIRE = ['', 'REP', 'REP+'] as const;

/** Colonnes parallèles : l'école i est faite des i-èmes valeurs. */
export interface TableEcoles {
  uai: string[];
  nom: string[];
  commune: number[]; // rang dans meta.communes
  type: number[];
  secteur: number[];
  eleves: (number | null)[];
  ips: (number | null)[];
  rep: number[];
  cite: number[];
  lon: number[];
  lat: number[];
  engagement: (number | null)[];
  periscolaire: (number | null)[];
  parents: (number | null)[];
  producteurs: (number | null)[];
  familles: (number | null)[];
  score: (number | null)[];
  confiance: number[];
  prod: ((number | null)[] | null)[]; // km, minutes, km, minutes… (inconnu : null)
}

export interface Critere {
  code: string;
  valeur?: number;
  detail?: unknown;
}
export interface DetailJauge {
  part: number;
  criteres: Critere[];
}

export interface FicheAccueil {
  nom: string;
  adresse?: string;
  soir?: boolean;
  mercredi?: boolean;
  horaires?: string;
  gestionnaire?: string;
  gestionnaire_type?: string;
  siren?: string;
  xy?: [number, number];
  p: Provenance;
}

export interface FicheAsso {
  nom: string;
  siege?: string;
  federation?: string;
  site?: string;
  rna?: string;
  siren?: string;
  creation?: string;
  activite?: string;
  activite_url?: string;
  xy?: [number, number];
  p: Provenance;
  pg?: Provenances;
}

export interface FicheEcole {
  adresse?: string;
  cp?: string;
  classes?: number;
  rentree?: number;
  ips_rentree?: string;
  restauration?: boolean;
  cite?: string;
  iris?: {
    nom: string;
    familles?: number;
    revenu?: number;
    pauvrete?: number;
    annee?: number;
    annee_revenus?: number;
    pg?: Provenances;
  };
  qpv?: { nom: string; m: number };
  jauges: ParJauge<DetailJauge>;
  accueils?: { id: string; m: number; motif: string; c: number }[];
  assos?: { id: string; c: number; indices: Record<string, unknown> }[];
  prod?: (number | null)[]; // rang, km, minutes…
  relais?: (number | null)[];
  p: Provenance;
  pg?: Provenances;
}

export interface Elu {
  nom: string;
  fonction: string;
  delegation?: string;
  themes?: string[];
  debut?: string;
  p: Provenance;
  pd?: Provenance;
}

export interface Dispositif {
  id: string;
  type: 'pat' | 'cite_educative' | 'qpv' | 'laureat_aap';
  nom: string;
  axe?: boolean;
  annee?: number;
  niveau?: string;
  p: Provenance;
}

export interface Signal {
  theme: string;
  titre?: string;
  date?: string;
  type: string;
  p: Provenance;
}

export interface FicheCommune {
  code: string;
  nom: string;
  type: 'commune' | 'arrondissement';
  dep: string;
  siren?: string;
  mere?: { code: string; nom: string };
  epci?: string;
  ept?: string;
  population?: number;
  population_annee?: number;
  densite?: number;
  site?: string;
  cantine?: {
    gestion?: 'regie' | 'concedee' | 'mixte';
    nb?: number;
    declarations?: number;
    bio?: number;
    egalim?: number;
    annee?: number;
  };
  nb: { accueils: number; assos: number; relais: number; producteurs: number; elus: number };
  gestionnaires?: { siren: string; nom: string; type: string; n: number }[];
  dispositifs?: Dispositif[];
  elus?: Elu[];
  signaux?: Signal[];
  nb_signaux: number;
  visite?: { statut: string; date: string };
  p: Provenance;
  pg?: Provenances;
}

export interface Fiche {
  commune: FicheCommune;
  ecoles?: Record<string, FicheEcole>;
  accueils?: Record<string, FicheAccueil>;
  assos?: Record<string, FicheAsso>;
}

export interface ProprietesProducteur extends Provenance {
  id: string;
  nom: string;
  activites?: string;
  bio: string;
  legumes: boolean;
  fruits: boolean;
  vente?: boolean;
  amap?: boolean;
  eligible: boolean;
  compte: boolean;
  adresse?: string;
  adresse_type: 'lieu_activite' | 'lieu_vente' | 'siege';
  commune?: string;
}

export interface ProprietesRelais extends Provenance {
  id: string;
  type: 'centre_social' | 'distribution_amap' | 'epicerie_solidaire' | 'ferme_pedagogique';
  nom: string;
  adresse?: string;
  site?: string;
  commune?: string;
}

export interface ProprietesPat extends Provenance {
  id: string;
  nom: string;
  axe?: boolean;
  annee?: number;
  niveau?: string;
  laureat?: boolean;
  communes?: string[]; // codes Insee ; Paris : la commune entière. Absent des exports antérieurs
}

export type CollectionPoints<P> = FeatureCollection<Point, P>;

export interface TableCouverte {
  nom: string;
  libelle: string;
  lignes: number[]; // par zone
  champs: { libelle: string; nature: 'rempli' | 'part'; cause?: string; taux: (number | null)[] }[];
}

/** Rapport de couverture ; zones : région puis départements. */
export interface Couverture {
  genere_le: string;
  zones: string[];
  tables: TableCouverte[];
}
