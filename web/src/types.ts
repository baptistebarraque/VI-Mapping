/** Données écrites par `vi exporter` (src/vi_mapping/export). Un champ absent vaut « inconnu ». */

import type { FeatureCollection, Point } from 'geojson';

export const JAUGES = ['engagement', 'periscolaire', 'parents', 'producteurs', 'familles'] as const;
export type NomJauge = (typeof JAUGES)[number];
export type ParJauge<T> = Record<NomJauge, T>;

/** Critères du score propre des communes (étape 1), dans l'ordre de config/jauges.yaml. */
export const CRITERES_COMMUNES = [
  'pat', 'soutiens', 'cuisine', 'cantine_bio', 'communications', 'producteurs', 'associations', 'ecoles',
] as const;
export type CritereCommune = (typeof CRITERES_COMMUNES)[number];
export type ParCritere<T> = Record<CritereCommune, T>;

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
  poids_communes: ParCritere<number>;
  part_min_jauge: number;
}

export const TYPES_ECOLE = ['Maternelle', 'Élémentaire', 'Primaire'] as const;
export const SECTEURS = ['Publique', 'Privée sous contrat'] as const;
export const EDUCATION_PRIORITAIRE = ['', 'REP', 'REP+'] as const;

/** Colonnes parallèles alignées sur meta.communes : la commune k est faite des k-ièmes valeurs. */
export type TableCommunes = ParCritere<(number | null)[]> & {
  score: (number | null)[];
  confiance: (number | null)[];
  pat_nom: (string | null)[];
  population: (number | null)[];
  eleves: (number | null)[];
  assos: (number | null)[];
};

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

/** Coordonnées publiées par une source, avec leur provenance. */
export interface Contact {
  tel?: string;
  email?: string;
  site?: string;
  formulaire?: string;
  service?: string;
  p: Provenance;
}

export interface FicheEcole {
  contact?: Contact;
  adresse?: string;
  cp?: string;
  classes?: number;
  rentree?: number;
  ips_rentree?: string;
  restauration?: boolean;
  cite?: string;
  cite_id?: string;
  iris?: {
    code: string;
    nom: string;
    familles?: number;
    revenu?: number;
    pauvrete?: number;
    annee?: number;
    annee_revenus?: number;
    pg?: Provenances;
  };
  qpv?: { id: string; nom: string; m: number };
  jauges: ParJauge<DetailJauge>;
  accueils?: { id: string; m: number; motif: string; c: number }[];
  assos?: { id: string; c: number; indices: Record<string, unknown> }[];
  prod?: (number | null)[]; // rang, km, minutes…
  relais?: (number | null)[];
  p: Provenance;
  pg?: Provenances;
}

export interface Elu {
  id: string;
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
  type: 'pat' | 'cite_educative' | 'qpv' | 'laureat_aap' | 'soutien_territorial' | 'laureat_aap_mgp'
    | 'syndicat_restauration';
  nom: string;
  axe?: boolean;
  restauration?: boolean;
  annee?: number;
  niveau?: string;
  echelon?: 'region' | 'departement' | 'interco';
  score?: number;
  editions?: string;
  priorites?: string;
  p: Provenance;
}

export interface CuisineCentrale {
  siret: string;
  nom: string;
  type: 'municipale' | 'caisse_des_ecoles' | 'intercommunale' | 'autre_public' | 'privee' | 'inconnu';
  commune?: string;
  gestion?: 'regie' | 'concedee';
  cantines?: number;
  repas?: number;
  bio?: number;
  egalim?: number;
  p: Provenance;
}

export interface AssoAlimentation {
  id: string;
  nom: string;
  categorie: 'amap_circuits_courts' | 'jardins_agriculture_urbaine' | 'education_alimentaire' | 'solidarite_anti_gaspi';
  site?: string;
  declaration?: string;
  xy?: [number, number];
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
  organismes?: { siren: string; type: TypeOrganisme; nom: string }[]; // de l'intercommunalité à la région
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
    satellites?: number;
    sur_place?: number;
    regie?: number;
    repas?: number;
    centrale?: CuisineCentrale;
  };
  contact?: Contact;
  score?: { valeur: number | null; part: number; criteres: Critere[] };
  alimentation?: { n: number; categories: Partial<Record<AssoAlimentation['categorie'], number>>; assos: AssoAlimentation[] };
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
  restauration?: boolean;
  priorites?: string;
  porteur?: string;
  organisme?: string; // porteur reconnu : Siren…
  commune?: string; // … ou code Insee
  contact?: Contact;
}

// ------------------------------------------------------------------ acteurs : une fiche par instance
/** Natures d'acteurs qui ont une fiche, en plus des communes, des écoles et des PAT. */
export const NATURES = [
  'accueil', 'asso', 'producteur', 'relais', 'alimentation', 'gestionnaire', 'cuisine', 'dispositif', 'organisme',
  'iris', 'elu',
] as const;
export type Nature = (typeof NATURES)[number];
/** Les élus n'ont pas de fichier à eux : ils sont lus dans la fiche de leur commune. */
export type NatureFichier = Exclude<Nature, 'elu'>;
export type TypeOrganisme = 'epci' | 'ept' | 'syndicat_restauration' | 'departement' | 'region';

/** Fiche d'un acteur (acteurs/<nature>.json) : champs communs, puis ceux de sa nature. */
export interface Acteur {
  nom: string;
  type?: string;
  commune?: string;
  communes?: string[];
  adresse?: string;
  xy?: [number, number];
  contact?: Contact;
  p: Provenance;
  pg?: Provenances;
  // accueils et associations
  ecoles?: { uai: string; c: number; m?: number; motif?: string }[];
  soir?: boolean;
  mercredi?: boolean;
  horaires?: string;
  gestionnaire?: string;
  gestionnaire_type?: string;
  siren?: string;
  siege?: string;
  federation?: string;
  objet?: string;
  rna?: string;
  creation?: string;
  declaration?: string;
  activite?: string;
  activite_url?: string;
  // producteurs et relais
  adresse_type?: ProprietesProducteur['adresse_type'];
  activites?: string[];
  productions?: string[];
  bio?: string | number; // producteur : état de certification ; cuisine : % de bio
  vente?: boolean;
  collective?: boolean;
  amap?: boolean;
  eligible?: boolean;
  compte?: boolean;
  numero_bio?: number;
  siret?: string;
  proches?: [uai: string, km: number, minutes: number | null][];
  // gestionnaires, cuisines centrales, dispositifs, organismes
  accueils?: string[];
  organisme?: string;
  gestion?: 'regie' | 'concedee';
  cantines?: number;
  repas?: number;
  egalim?: number;
  annee?: number;
  echelon?: 'region' | 'departement' | 'interco';
  score?: number;
  editions?: string;
  priorites?: string;
  niveau?: string;
  dep?: string;
  dispositifs?: string[];
  // quartiers IRIS
  familles?: number;
  revenu?: number;
  pauvrete?: number;
  annee_revenus?: number;
  qpv?: string[];
  part_qpv?: number;
  uais?: string[];
}
export type Acteurs = Record<string, Acteur>;

/** Ligne du carnet de contacts (contacts.json). */
export interface LigneContact extends Contact {
  n: 'commune' | 'ecole' | 'pat' | NatureFichier;
  id: string;
  nom: string;
  commune?: string;
  communes?: string[];
  dep?: string;
  type?: string;
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
