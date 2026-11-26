/** Communes (étape 1) : critère producteurs selon le rayon, score selon les poids, communes visibles et classement. */

import type { Filtres } from './etat';
import { producteursCommune, scoreCommune } from './jauges';
import type { Modele } from './modele';
import { CRITERES_COMMUNES, type CritereCommune, type Meta, type ParCritere, type TableCommunes } from './types';

type Nombre = number | null;

export class ModeleCommunes {
  readonly n: number;
  readonly rang = new Map<string, number>(); // code Insee → rang dans les colonnes (celui de meta.communes)
  producteurs: Nombre[];
  scores: Nombre[];
  connus: Uint8Array; // critères connus, sur 8
  visibles: number[] = []; // communes filtrées, de la mieux à la moins bien classée

  constructor(
    readonly meta: Meta,
    readonly t: TableCommunes,
    readonly ecoles: Modele,
  ) {
    this.n = meta.communes.length;
    meta.communes.forEach((c, k) => this.rang.set(c.code, k));
    this.producteurs = new Array<Nombre>(this.n).fill(null);
    this.scores = new Array<Nombre>(this.n).fill(null);
    this.connus = new Uint8Array(this.n);
  }

  valeur(c: CritereCommune, k: number): Nombre {
    return c === 'producteurs' ? this.producteurs[k] : this.t[c][k];
  }

  valeurs(k: number): ParCritere<Nombre> {
    return Object.fromEntries(CRITERES_COMMUNES.map((c) => [c, this.valeur(c, k)])) as ParCritere<Nombre>;
  }

  /** À refaire après la jauge Producteurs des écoles (le rayon a changé). */
  recalculerProducteurs(): void {
    this.meta.communes.forEach((c, k) => {
      const ecoles = this.ecoles.parCommune.get(c.code) ?? [];
      this.producteurs[k] = producteursCommune(ecoles.map((i) => this.ecoles.producteurs[i]));
      this.connus[k] = CRITERES_COMMUNES.reduce((s, x) => s + (this.valeur(x, k) === null ? 0 : 1), 0);
    });
  }

  recalculerScores(poids: ParCritere<number>): void {
    for (let k = 0; k < this.n; k++) this.scores[k] = scoreCommune(this.valeurs(k), poids, this.meta.part_min_jauge);
  }

  /** Communes qui ont des écoles (Paris : ses arrondissements), selon les départements et les critères connus. */
  garde(k: number, f: Filtres): boolean {
    const c = this.meta.communes[k];
    if (!c.ecoles) return false;
    if (f.departements.length && !f.departements.includes(c.dep)) return false;
    return this.connus[k] >= f.criteresMin;
  }

  /** Score décroissant, puis commune la mieux documentée, puis nom. Sans score : en dernier. */
  filtrer(f: Filtres): void {
    const gardees: number[] = [];
    for (let k = 0; k < this.n; k++) if (this.garde(k, f)) gardees.push(k);
    gardees.sort(
      (a, b) =>
        (this.scores[b] ?? -1) - (this.scores[a] ?? -1) ||
        this.connus[b] - this.connus[a] ||
        this.meta.communes[a].nom.localeCompare(this.meta.communes[b].nom, 'fr') ||
        a - b,
    );
    this.visibles = gardees;
  }

  /** Les n premières communes du classement : à retenir pour l'étape « écoles ». */
  premieres(n: number): string[] {
    return this.visibles.slice(0, n).map((k) => this.meta.communes[k].code);
  }
}
