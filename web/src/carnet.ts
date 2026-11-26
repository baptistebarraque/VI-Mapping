/** Carnet de contacts : lignes utiles pour un territoire, texte à coller dans un e-mail, export CSV tracé. */

import type { Carnet } from './donnees';
import { parametreCible, type Cible, type Filtres } from './etat';
import { enregistrerCsv, type Cellule } from './csv';
import type { Modele } from './modele';
import type { LigneContact, Meta } from './types';
import { LIBELLE_NATURE, pluriel } from './ui/format';

export type NatureContact = LigneContact['n'];
/** Ordre d'affichage : qui décide, puis qui agit. */
export const NATURES_CONTACT: readonly NatureContact[] = [
  'commune', 'organisme', 'pat', 'ecole', 'accueil', 'asso', 'producteur', 'relais', 'alimentation',
];

export interface Perimetre {
  titre: string;
  codes: Set<string>; // communes, arrondissements et communes mères compris
  ecoles: number[];
}

/** Périmètre de communes ; un arrondissement apporte sa commune mère, et une commune mère ses arrondissements. */
export function perimetre(titre: string, codes: Iterable<string>, modele: Modele, ecoles?: number[]): Perimetre {
  const demandes = new Set(codes);
  const tous = new Set(demandes);
  for (const c of modele.meta.communes) {
    if (c.mere && (demandes.has(c.code) || demandes.has(c.mere))) {
      tous.add(c.code);
      tous.add(c.mere);
    }
  }
  // Les écoles d'une commune mère (Paris) sont déjà celles de ses arrondissements.
  const meres = new Set(modele.meta.communes.map((c) => c.mere));
  return {
    titre, codes: tous,
    ecoles: ecoles ?? [...tous].flatMap((c) => (meres.has(c) ? [] : modele.parCommune.get(c) ?? [])),
  };
}

const RAYON_TERRE_KM = 6371;
export function distanceKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const r = Math.PI / 180;
  const a = Math.sin(((lat2 - lat1) * r) / 2) ** 2
    + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2;
  return 2 * RAYON_TERRE_KM * Math.asin(Math.sqrt(a));
}

/** Contacts d'un périmètre. Un producteur compte s'il est à moins du rayon (à vol d'oiseau) d'une de ses écoles. */
export function contactsDe(
  carnet: Carnet, p: Perimetre, modele: Modele, positions: Map<string, [number, number]>, rayonKm: number,
): LigneContact[] {
  const { t, meta } = modele;
  const ecoles = new Set(p.ecoles.map((i) => t.uai[i]));
  const departements = new Set(meta.communes.filter((c) => p.codes.has(c.code)).map((c) => c.dep));
  const garder = (l: LigneContact): boolean => {
    switch (l.n) {
      case 'ecole': return ecoles.has(l.id);
      case 'organisme':
        return l.type === 'region' || (l.type === 'departement' ? departements.has(l.dep ?? '') : (l.communes ?? []).some((c) => p.codes.has(c)));
      case 'pat': return (l.communes ?? []).some((c) => p.codes.has(c));
      case 'producteur': {
        const xy = positions.get(l.id);
        return xy !== undefined && p.ecoles.some((i) => distanceKm(t.lon[i], t.lat[i], ...xy) <= rayonKm);
      }
      default: return l.commune !== undefined && p.codes.has(l.commune);
    }
  };
  return carnet.lignes.filter(garder)
    .sort((a, b) => NATURES_CONTACT.indexOf(a.n) - NATURES_CONTACT.indexOf(b.n) || a.nom.localeCompare(b.nom, 'fr'));
}

/** Périmètre de l'écran : communes retenues (sinon filtrées) à l'étape 1, écoles affichées à l'étape 2. */
export function perimetreEcran(
  etape: 'communes' | 'ecoles', filtres: Filtres, communesVisibles: string[], modele: Modele,
): Perimetre {
  if (etape === 'ecoles') {
    const codes = modele.visibles.map((i) => modele.meta.communes[modele.t.commune[i]].code);
    return perimetre(pluriel(modele.visibles.length, 'école affichée', 'écoles affichées'), codes, modele, modele.visibles);
  }
  const n = filtres.retenues.length;
  if (n) return perimetre(pluriel(n, 'commune retenue', 'communes retenues'), filtres.retenues, modele);
  return perimetre(pluriel(communesVisibles.length, 'commune affichée', 'communes affichées'), communesVisibles, modele);
}

export const cibleDe = (l: LigneContact): Cible => l.n === 'commune' ? { type: 'commune', code: l.id }
  : l.n === 'ecole' ? { type: 'ecole', uai: l.id } : l.n === 'pat' ? { type: 'pat', id: l.id }
    : { type: 'acteur', nature: l.n, id: l.id };

/** Adresses distinctes, dans l'ordre. */
export const adresses = (lignes: LigneContact[]): string[] =>
  [...new Set(lignes.flatMap((l) => (l.email ? [l.email] : [])))];

/** Adresse de la page qui rouvre la fiche : le CSV reste relié à ses sources et à la carte. */
export function lienProfond(c: Cible, page: string): string {
  const p = new URLSearchParams([parametreCible(c)]);
  return `${page.split('#')[0]}#${p.toString()}`;
}

const ENTETE = [
  'nature', 'nom', 'service', 'commune', 'code_insee', 'departement', 'email', 'telephone', 'site', 'formulaire',
  'source', 'url_source', 'collecte_le', 'confiance', 'fiche',
];

export function contactsCsv(lignes: LigneContact[], meta: Meta, page: string): string {
  return enregistrerCsv(ENTETE, lignes.map((l): Cellule[] => {
    const c = meta.communes.find((x) => x.code === l.commune);
    return [
      LIBELLE_NATURE[l.n][0], l.nom, l.service, c?.nom, l.commune, c?.dep ?? l.dep, l.email, l.tel, l.site, l.formulaire,
      meta.sources[l.p.s]?.libelle ?? l.p.s, l.p.u, l.p.d, l.p.c, lienProfond(cibleDe(l), page),
    ];
  }));
}
