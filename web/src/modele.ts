/** Valeurs dérivées de toutes les écoles : jauge producteurs, score, écoles visibles et classement. */

import type { Filtres } from './etat';
import { jaugeProducteurs, score } from './jauges';
import { JAUGES, type Meta, type NomJauge, type ParJauge, type Rayon, type TableEcoles } from './types';

type Nombre = number | null;

export class Modele {
  readonly n: number;
  readonly rang = new Map<string, number>(); // UAI → rang dans les colonnes
  readonly parCommune = new Map<string, number[]>(); // code Insee → écoles (Paris : tous les arrondissements)
  producteurs: Nombre[];
  nbProducteurs: Uint8Array;
  scores: Nombre[];
  connues: Uint8Array; // jauges connues, sur 5
  visibles: number[] = []; // écoles filtrées, de la mieux à la moins bien classée

  constructor(
    readonly meta: Meta,
    readonly t: TableEcoles,
  ) {
    this.n = t.uai.length;
    this.producteurs = new Array<Nombre>(this.n).fill(null);
    this.nbProducteurs = new Uint8Array(this.n);
    this.scores = new Array<Nombre>(this.n).fill(null);
    this.connues = new Uint8Array(this.n);
    t.uai.forEach((uai, i) => {
      this.rang.set(uai, i);
      const c = meta.communes[t.commune[i]];
      for (const code of c.mere ? [c.code, c.mere] : [c.code]) {
        const l = this.parCommune.get(code);
        if (l) l.push(i);
        else this.parCommune.set(code, [i]);
      }
    });
  }

  valeur(j: NomJauge, i: number): Nombre {
    return j === 'producteurs' ? this.producteurs[i] : this.t[j][i];
  }

  valeurs(i: number): ParJauge<Nombre> {
    return {
      engagement: this.t.engagement[i],
      periscolaire: this.t.periscolaire[i],
      parents: this.t.parents[i],
      producteurs: this.producteurs[i],
      familles: this.t.familles[i],
    };
  }

  recalculerProducteurs(rayon: Rayon): void {
    for (let i = 0; i < this.n; i++) {
      const j = jaugeProducteurs(this.t.prod[i], rayon, this.meta.producteurs);
      this.producteurs[i] = j.valeur;
      this.nbProducteurs[i] = j.nombre;
    }
    for (let i = 0; i < this.n; i++) {
      this.connues[i] = JAUGES.reduce((s, j) => s + (this.valeur(j, i) === null ? 0 : 1), 0);
    }
  }

  recalculerScores(poids: ParJauge<number>): void {
    for (let i = 0; i < this.n; i++) this.scores[i] = score(this.valeurs(i), poids, this.meta.part_min_score);
  }

  garde(i: number, f: Filtres): boolean {
    const t = this.t;
    const c = this.meta.communes[t.commune[i]];
    if (f.departements.length && !f.departements.includes(c.dep)) return false;
    if (f.commune && c.code !== f.commune && c.mere !== f.commune) return false;
    if (f.secteur !== 'tous' && (t.secteur[i] === 0) !== (f.secteur === 'public')) return false;
    if (f.types.length && !f.types.includes(t.type[i])) return false;
    const eleves = t.eleves[i];
    if (f.elevesMin !== null && (eleves === null || eleves < f.elevesMin)) return false;
    if (f.elevesMax !== null && (eleves === null || eleves > f.elevesMax)) return false;
    if (this.connues[i] < f.connuesMin) return false;
    for (const j of JAUGES) {
      const seuil = f.seuils[j];
      if (seuil <= 0) continue;
      const v = this.valeur(j, i);
      if (v === null ? !f.garderInconnues : v < seuil) return false;
    }
    return true;
  }

  /** Classement : score décroissant, puis école la mieux documentée, puis nom. Sans score : en dernier. */
  filtrer(f: Filtres): void {
    const gardees: number[] = [];
    for (let i = 0; i < this.n; i++) if (this.garde(i, f)) gardees.push(i);
    gardees.sort(
      (a, b) =>
        (this.scores[b] ?? -1) - (this.scores[a] ?? -1) ||
        this.connues[b] - this.connues[a] ||
        this.t.confiance[b] - this.t.confiance[a] ||
        this.t.nom[a].localeCompare(this.t.nom[b], 'fr') ||
        a - b,
    );
    this.visibles = gardees;
  }

  /** École juste avant (-1) ou juste après (1) dans le classement ; null au bout, ou si l'école est filtrée. */
  voisine(i: number, pas: 1 | -1): number | null {
    const rang = this.visibles.indexOf(i);
    return rang < 0 ? null : (this.visibles[rang + pas] ?? null);
  }

  moyenne(valeurs: Iterable<Nombre>): Nombre {
    let n = 0;
    let s = 0;
    for (const v of valeurs) {
      if (v === null) continue;
      n++;
      s += v;
    }
    return n ? s / n : null;
  }
}
