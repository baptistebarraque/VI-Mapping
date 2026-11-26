/** État de l'interface : réglages, filtres, couches, sélection. Conservé dans l'adresse de la page. */

import {
  CRITERES_COMMUNES, JAUGES, NATURES, type Meta, type Mode, type Nature, type NomJauge, type ParCritere, type ParJauge,
  type Rayon,
} from './types';

export const COUCHES = [
  'ecoles', 'accueils', 'assos', 'producteurs', 'relais', 'communes', 'pat', 'qpv', 'cites', 'iris',
] as const;
export type Couche = (typeof COUCHES)[number];
export type Secteur = 'tous' | 'public' | 'prive';
export type VariableIris = 'familles' | 'revenu' | 'pauvrete';
export type Coloration = 'score' | NomJauge;
/** Étape 1 : classer les communes ; étape 2 : classer les écoles (des communes retenues). */
export type Etape = 'communes' | 'ecoles';

export interface Filtres {
  departements: string[]; // vide : tous
  commune: string | null;
  secteur: Secteur;
  types: number[]; // vide : tous
  elevesMin: number | null;
  elevesMax: number | null;
  seuils: ParJauge<number>;
  garderInconnues: boolean; // jauge inconnue : garder l'école malgré un seuil
  connuesMin: number; // nombre minimal de jauges connues, sur 5
  premiers: number | null; // ne garder que le début du classement ; null : tout
  retenues: string[]; // communes retenues à l'étape 1 (codes Insee) ; vide : toutes
  criteresMin: number; // communes : nombre minimal de critères connus, sur 8
}

export const PREMIERS_DEFAUT = 50;
export const PREMIERS_MAX = 9999;

/** Instance ouverte : sa fiche à droite, sa position ou son contour sur la carte. */
export type Cible =
  | { type: 'ecole'; uai: string }
  | { type: 'commune'; code: string }
  | { type: 'pat'; id: string }
  | { type: 'acteur'; nature: Nature; id: string };
export type Selection = Cible | null;

export interface Etat {
  etape: Etape;
  poids: ParJauge<number>;
  poidsCommunes: ParCritere<number>;
  rayon: Rayon;
  filtres: Filtres;
  couches: Record<Couche, boolean>;
  coloration: Coloration;
  iris: VariableIris;
  selection: Selection;
}

export type Sujet = keyof Etat;

const parJauge = <T>(f: (j: NomJauge) => T): ParJauge<T> =>
  Object.fromEntries(JAUGES.map((j) => [j, f(j)])) as ParJauge<T>;

export function filtresVides(): Filtres {
  return {
    departements: [], commune: null, secteur: 'tous', types: [], elevesMin: null, elevesMax: null,
    seuils: parJauge(() => 0), garderInconnues: false, connuesMin: 0, premiers: null, retenues: [], criteresMin: 0,
  };
}

export function etatInitial(meta: Meta): Etat {
  return {
    etape: 'communes',
    poids: { ...meta.poids },
    poidsCommunes: { ...meta.poids_communes },
    rayon: { ...meta.rayon },
    filtres: filtresVides(),
    couches: {
      ecoles: true, accueils: false, assos: false, producteurs: false, relais: false,
      communes: true, pat: false, qpv: false, cites: false, iris: false,
    },
    coloration: 'score',
    iris: 'familles',
    selection: null,
  };
}

/** Magasin minimal : les abonnés sont prévenus une fois par image, avec les sujets modifiés. */
export class Magasin {
  private abonnes: ((sujets: Set<Sujet>) => void)[] = [];
  private enAttente = new Set<Sujet>();

  constructor(readonly etat: Etat) {}

  modifier<S extends Sujet>(sujet: S, valeur: Etat[S]): void {
    this.etat[sujet] = valeur;
    if (this.enAttente.size === 0) requestAnimationFrame(() => this.prevenir());
    this.enAttente.add(sujet);
  }

  filtrer(partiel: Partial<Filtres>): void {
    this.modifier('filtres', { ...this.etat.filtres, ...partiel });
  }

  /** Reprend un état entier (adresse collée, bouton « précédent » du navigateur). */
  reprendre(e: Etat): void {
    for (const sujet of Object.keys(e) as Sujet[]) this.modifier(sujet, e[sujet]);
  }

  abonner(f: (sujets: Set<Sujet>) => void): void {
    this.abonnes.push(f);
  }

  private prevenir(): void {
    const sujets = this.enAttente;
    this.enAttente = new Set();
    for (const f of this.abonnes) f(sujets);
  }
}

// ------------------------------------------------------------------ état dans l'adresse (#…)
const liste = (x: readonly (string | number)[]): string => x.join('-');
const nombres = (s: string | null): number[] => (s ? s.split('-').map(Number).filter(Number.isFinite) : []);

/** Seulement ce qui diffère des réglages par défaut : adresse courte et partageable. */
export function versAdresse(e: Etat, meta: Meta): string {
  const defaut = etatInitial(meta);
  const p = new URLSearchParams();
  const poser = (cle: string, valeur: string, ref: string): void => {
    if (valeur !== ref) p.set(cle, valeur);
  };
  const poids = (x: Etat): string => liste(JAUGES.map((j) => x.poids[j]));
  const poidsCommunes = (x: Etat): string => liste(CRITERES_COMMUNES.map((c) => x.poidsCommunes[c]));
  const rayon = (x: Etat): string => liste([x.rayon.km, x.rayon.minutes, x.rayon.mode]);
  const seuils = (x: Etat): string => liste(JAUGES.map((j) => x.filtres.seuils[j]));
  const couches = (x: Etat): string => liste(COUCHES.filter((c) => x.couches[c]));
  poser('etape', e.etape, defaut.etape);
  poser('poids', poids(e), poids(defaut));
  poser('pc', poidsCommunes(e), poidsCommunes(defaut));
  poser('retenues', liste(e.filtres.retenues), '');
  poser('criteres', String(e.filtres.criteresMin), '0');
  poser('rayon', rayon(e), rayon(defaut));
  poser('dep', liste(e.filtres.departements), '');
  poser('commune', e.filtres.commune ?? '', '');
  poser('secteur', e.filtres.secteur, 'tous');
  poser('types', liste(e.filtres.types), '');
  poser('eleves', `${e.filtres.elevesMin ?? ''}_${e.filtres.elevesMax ?? ''}`, '_');
  poser('seuils', seuils(e), seuils(defaut));
  poser('inconnues', e.filtres.garderInconnues ? '1' : '', '');
  poser('connues', String(e.filtres.connuesMin), '0');
  poser('premiers', String(e.filtres.premiers ?? ''), '');
  poser('couches', couches(e), couches(defaut));
  poser('couleur', e.coloration, defaut.coloration);
  poser('iris', e.iris, defaut.iris);
  if (e.selection) p.set(...parametreCible(e.selection));
  return p.toString();
}

/** Paramètre d'adresse qui rouvre une fiche : aussi utilisé comme lien profond dans les exports. */
export function parametreCible(c: Cible): [string, string] {
  switch (c.type) {
    case 'ecole': return ['ecole', c.uai];
    case 'commune': return ['fiche', c.code];
    case 'pat': return ['pat', c.id.replace('pat:', '')];
    case 'acteur': return ['acteur', `${c.nature}:${c.id}`];
  }
}

function cibleDepuis(p: URLSearchParams, meta: Meta): Selection {
  const ecole = p.get('ecole');
  const fiche = p.get('fiche');
  const pat = p.get('pat');
  const [nature, ...id] = (p.get('acteur') ?? '').split(':');
  if (ecole) return { type: 'ecole', uai: ecole };
  if (fiche) return meta.communes.some((c) => c.code === fiche) ? { type: 'commune', code: fiche } : null;
  if (pat) return /^(\d+|referentiel:\w+)$/.test(pat) ? { type: 'pat', id: pat.includes(':') ? pat : `pat:${pat}` } : null;
  if (NATURES.includes(nature as Nature) && id.join(':')) return { type: 'acteur', nature: nature as Nature, id: id.join(':') };
  return null;
}

export function depuisAdresse(hash: string, meta: Meta): Etat {
  const e = etatInitial(meta);
  const p = new URLSearchParams(hash.replace(/^#/, ''));
  const dans = (x: number, min: number, max: number): boolean => x >= min && x <= max;
  if (p.get('etape') === 'ecoles') e.etape = 'ecoles';
  const poids = nombres(p.get('poids'));
  if (poids.length === JAUGES.length && poids.every((x) => dans(x, 0, 100))) {
    e.poids = parJauge((j) => poids[JAUGES.indexOf(j)]);
  }
  const pc = nombres(p.get('pc'));
  if (pc.length === CRITERES_COMMUNES.length && pc.every((x) => dans(x, 0, 100))) {
    e.poidsCommunes = Object.fromEntries(CRITERES_COMMUNES.map((c, k) => [c, pc[k]])) as ParCritere<number>;
  }
  const [km, minutes, mode] = (p.get('rayon') ?? '').split('-');
  if (['ou', 'km', 'minutes'].includes(mode) && dans(Number(km), 1, meta.km_max) && dans(Number(minutes), 1, 120)) {
    e.rayon = { km: Number(km), minutes: Number(minutes), mode: mode as Mode };
  }
  const f = e.filtres;
  f.departements = (p.get('dep') ?? '').split('-').filter((d) => d in meta.departements);
  const commune = p.get('commune');
  f.commune = meta.communes.some((c) => c.code === commune) ? commune : null;
  const secteur = p.get('secteur');
  if (secteur === 'public' || secteur === 'prive') f.secteur = secteur;
  f.types = nombres(p.get('types')).filter((t) => dans(t, 0, 2));
  const [min, max] = (p.get('eleves') ?? '_').split('_').map((x) => (x && Number.isFinite(+x) ? +x : null));
  f.elevesMin = min ?? null;
  f.elevesMax = max ?? null;
  const seuils = nombres(p.get('seuils'));
  if (seuils.length === JAUGES.length) f.seuils = parJauge((j) => Math.min(100, Math.max(0, seuils[JAUGES.indexOf(j)])));
  f.garderInconnues = p.get('inconnues') === '1';
  const connues = Number(p.get('connues') ?? 0);
  f.connuesMin = dans(connues, 0, 5) ? connues : 0;
  const codes = new Set(meta.communes.map((c) => c.code));
  f.retenues = (p.get('retenues') ?? '').split('-').filter((c) => codes.has(c));
  const criteres = Number(p.get('criteres') ?? 0);
  f.criteresMin = Number.isInteger(criteres) && dans(criteres, 0, CRITERES_COMMUNES.length) ? criteres : 0;
  const premiers = Number(p.get('premiers'));
  f.premiers = Number.isInteger(premiers) && dans(premiers, 1, PREMIERS_MAX) ? premiers : null;
  if (p.has('couches')) {
    const actives = new Set((p.get('couches') ?? '').split('-'));
    for (const c of COUCHES) e.couches[c] = actives.has(c);
  }
  const couleur = p.get('couleur');
  if (couleur === 'score' || JAUGES.includes(couleur as NomJauge)) e.coloration = couleur as Coloration;
  const iris = p.get('iris');
  if (iris === 'familles' || iris === 'revenu' || iris === 'pauvrete') e.iris = iris;
  e.selection = cibleDepuis(p, meta);
  return e;
}
