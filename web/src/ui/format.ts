/** Nombres, dates et libellés en français. */

import type { Coloration, Couche, VariableIris } from '../etat';
import type { NomJauge, ParJauge } from '../types';

const entier = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });

export const nombre = (x: number): string => entier.format(x);
export const dixieme = (x: number): string => decimal.format(x);
export const pourcent = (x: number): string => `${decimal.format(x)} %`;
export const euros = (x: number): string => `${entier.format(x)} €`;
export const km = (x: number): string => `${decimal.format(x)} km`;
export const metres = (m: number): string => (m < 1000 ? `${entier.format(m)} m` : km(m / 1000));
export const minutes = (x: number | null): string => (x === null ? 'durée inconnue' : `${entier.format(x)} min`);

export function date(iso: string): string {
  const [a, m, j] = iso.slice(0, 10).split('-');
  return j ? `${j}/${m}/${a}` : iso;
}

export const pluriel = (n: number, un: string, plusieurs = `${un}s`): string =>
  `${nombre(n)} ${n > 1 ? plusieurs : un}`;

export const LIBELLE_JAUGE: ParJauge<string> = {
  engagement: 'Engagement de la collectivité',
  periscolaire: 'Périscolaire',
  parents: 'Parents',
  producteurs: 'Producteurs',
  familles: 'Familles',
};
export const COURT_JAUGE: ParJauge<string> = {
  engagement: 'Collectivité',
  periscolaire: 'Périscolaire',
  parents: 'Parents',
  producteurs: 'Producteurs',
  familles: 'Familles',
};
export const LIBELLE_COLORATION: Record<Coloration, string> = { score: 'Score global', ...LIBELLE_JAUGE };

export const LIBELLE_CRITERE: Record<string, string> = {
  pat: 'Projet alimentaire territorial (PAT)',
  bio: 'Part de bio déclarée à la cantine',
  web: 'Signaux alimentaires sur le site de la mairie',
  cite_educative: 'Cité éducative',
  soir: 'Accueil du soir à proximité',
  mercredi: 'Accueil le mercredi',
  gestionnaire: 'Gestionnaire identifié',
  rattachee: 'Association rattachée',
  federee: 'Association fédérée',
  active: 'Active en ligne',
  plus_proche: 'Producteur le plus proche',
  nombre: 'Nombre de producteurs dans le rayon',
  nb_eleves: 'Élèves de l’école',
  familles_iris: 'Familles avec enfants du quartier (IRIS)',
  mixite: 'Mixité sociale (IPS, QPV)',
};

export const LIBELLE_COUCHE: Record<Couche, string> = {
  ecoles: 'Écoles',
  accueils: 'Accueils périscolaires',
  assos: 'Associations de parents',
  producteurs: 'Producteurs bio',
  relais: 'Relais locaux',
  communes: 'Communes',
  pat: 'Projets alimentaires territoriaux',
  qpv: 'Quartiers prioritaires (QPV)',
  cites: 'Cités éducatives',
  iris: 'Quartiers IRIS',
};

export const LIBELLE_IRIS: Record<VariableIris, string> = {
  familles: 'Familles avec enfants',
  revenu: 'Revenu médian',
  pauvrete: 'Taux de pauvreté',
};
export const VALEUR_IRIS: Record<VariableIris, (x: number) => string> = {
  familles: nombre,
  revenu: euros,
  pauvrete: pourcent,
};

export const LIBELLE_RELAIS: Record<string, string> = {
  centre_social: 'Centre social',
  distribution_amap: 'Lieu de distribution AMAP',
  epicerie_solidaire: 'Épicerie solidaire',
  ferme_pedagogique: 'Ferme pédagogique',
};

export const LIBELLE_THEME: Record<string, string> = {
  bio: 'bio',
  anti_gaspi: 'anti-gaspi',
  potager: 'potager',
  education_gout: 'éducation au goût',
  alimentation_durable: 'alimentation durable',
  periscolaire_soir: 'périscolaire du soir',
  periscolaire_mercredi: 'mercredi',
};

export const LIBELLE_PAGE: Record<string, string> = {
  actualite: 'actualité', agenda: 'agenda', menu: 'menu', document: 'document', page: 'page',
};

export const LIBELLE_DISPOSITIF: Record<string, string> = {
  pat: 'Projet alimentaire territorial',
  cite_educative: 'Cité éducative',
  qpv: 'Quartier prioritaire',
  laureat_aap: 'Lauréat de l’appel à projets du PNA',
};

export const LIBELLE_BIO: Record<string, string> = {
  bio: 'bio', conversion: 'en conversion', bio_et_conversion: 'bio et conversion', inconnu: 'état inconnu',
};

export const LIBELLE_ADRESSE: Record<string, string> = {
  lieu_activite: 'lieu d’activité', lieu_vente: 'lieu de vente', siege: 'siège (pas forcément la ferme)',
};

export const LIBELLE_METHODE: Record<string, string> = {
  api: 'API', csv: 'fichier ouvert', scraping: 'page web', calcul: 'calcul',
};

export const LIBELLE_VISITE: Record<string, string> = {
  ok: 'site visité',
  vide: 'site visité, sans page exploitable',
  robots_interdit: 'site non visité : robots.txt l’interdit',
  cgu_interdit: 'site non visité : ses conditions d’utilisation l’interdisent',
  tdm_reserve: 'site non visité : droits de fouille réservés',
  anti_robot: 'site non visité : protection anti-robot',
  erreur_http: 'site en erreur lors de la visite',
  injoignable: 'site injoignable lors de la visite',
};

export const LIBELLE_GESTION: Record<string, string> = { regie: 'régie', concedee: 'concédée', mixte: 'mixte' };
export const LIBELLE_GESTIONNAIRE: Record<string, string> = {
  regie: 'régie publique', association: 'association', entreprise: 'entreprise',
};

export const inconnu = 'inconnu';
export const ouiNonInconnu = (x: boolean | undefined): string => (x === undefined ? inconnu : x ? 'oui' : 'non');
export const jaugeOuInsuffisant = (x: number | null): string => (x === null ? 'données insuffisantes' : nombre(x));
export const nomJauge = (j: NomJauge): string => LIBELLE_JAUGE[j];
