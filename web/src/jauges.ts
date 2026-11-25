/**
 * Formules recalculées en direct : jauge « producteurs » (selon le rayon) et score global (selon les poids).
 * Reprises de src/vi_mapping/calculs/formules.py ; vecteurs de test communs : tests/vecteurs/jauges.json.
 */

import { JAUGES, type ConfigProducteurs, type ParJauge, type Rayon } from './types';

type Nombre = number | null;

export const borne = (x: number): number => Math.max(0, Math.min(100, x));
const dixieme = (x: number): number => Math.round(x * 10) / 10;

export function dansRayon(km: Nombre, minutes: Nombre, r: Rayon): boolean {
  const enKm = km !== null && km <= r.km;
  const enMinutes = minutes !== null && minutes <= r.minutes;
  return r.mode === 'km' ? enKm : r.mode === 'minutes' ? enMinutes : enKm || enMinutes;
}

/** 100 jusqu'à `plein`, puis pente jusqu'à 0 en bord de rayon. */
function pente(x: number, plein: number, bord: number): number {
  if (x <= plein && x <= bord) return 100;
  return bord > plein ? borne((100 * (bord - x)) / (bord - plein)) : 0;
}

export function noteProximite(km: Nombre, minutes: Nombre, r: Rayon, c: ConfigProducteurs): Nombre {
  if (minutes !== null && r.mode !== 'km') return pente(minutes, c.minutes_plein, r.minutes);
  return km === null ? null : pente(km, c.km_plein, r.km);
}

export interface JaugeProducteurs {
  valeur: Nombre;
  plusProche: Nombre; // note du critère
  nombreNote: Nombre;
  nombre: number; // producteurs dans le rayon, plafonné
  minutes: Nombre; // du plus proche dans le rayon
}

/** `prod` : km, minutes, km, minutes… (null : école non localisée). */
export function jaugeProducteurs(prod: Nombre[] | null, r: Rayon, c: ConfigProducteurs): JaugeProducteurs {
  if (prod === null) return { valeur: null, plusProche: null, nombreNote: null, nombre: 0, minutes: null };
  let plusProche = 0;
  let nombre = 0;
  let minutes: Nombre = null;
  for (let k = 0; k < prod.length; k += 2) {
    const km = prod[k];
    const min = prod[k + 1];
    if (!dansRayon(km, min, r)) continue;
    nombre++;
    if (min !== null && (minutes === null || min < minutes)) minutes = min;
    plusProche = Math.max(plusProche, noteProximite(km, min, r, c) ?? 0);
  }
  const nombreNote = borne((100 * nombre) / c.nombre_plein);
  const { plus_proche: a, nombre: b } = c.sous_poids;
  return {
    valeur: dixieme(borne((a * plusProche + b * nombreNote) / (a + b))),
    plusProche,
    nombreNote,
    nombre: Math.min(nombre, c.nombre_plein),
    minutes,
  };
}

/** Moyenne pondérée des jauges connues ; null (« données insuffisantes ») si leur poids est trop faible. */
export function score(valeurs: ParJauge<Nombre>, poids: ParJauge<number>, partMin: number): Nombre {
  let total = 0;
  let connu = 0;
  let somme = 0;
  for (const j of JAUGES) {
    const p = poids[j];
    const v = valeurs[j];
    total += p;
    if (v === null) continue;
    connu += p;
    somme += p * v;
  }
  if (connu === 0 || connu / total < partMin) return null;
  return dixieme(borne(somme / connu));
}
