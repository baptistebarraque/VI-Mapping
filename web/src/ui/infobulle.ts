/** Infobulle au survol et fenêtre au clic des points de la carte. */

import type { Modele } from '../modele';
import { JAUGES, type Meta, type Provenance } from '../types';
import { definition, pastille, provenance } from './commun';
import { h, lien } from './dom';
import {
  COURT_JAUGE, date, LIBELLE_ADRESSE, LIBELLE_BIO, LIBELLE_COUCHE, LIBELLE_RELAIS, nombre,
  ouiNonInconnu, pluriel,
} from './format';

export type TypePoint = 'accueils' | 'assos' | 'producteurs' | 'relais';
type Proprietes = Record<string, unknown>;
const texte = (x: unknown): string | undefined => (x === undefined || x === null || x === '' ? undefined : String(x));

const SINGULIER: Record<TypePoint, string> = {
  accueils: 'Accueil périscolaire', assos: 'Association de parents', producteurs: 'Producteur bio', relais: 'Relais local',
};

/** `autres` : nombre de points superposés à celui-ci. */
export function infobulle(type: TypePoint | 'ecoles', p: Proprietes, modele: Modele, autres = 0): HTMLElement {
  const suite = autres > 0 && h('span', { classe: 'sous' }, `et ${pluriel(autres, 'autre point', 'autres points')} au même endroit`);
  if (type !== 'ecoles') {
    const sous = type === 'relais' ? LIBELLE_RELAIS[String(p.type)] : SINGULIER[type];
    return h('div', {}, h('strong', {}, texte(p.nom)), h('span', { classe: 'sous' }, sous ?? LIBELLE_COUCHE[type]), suite);
  }
  const i = p.i as number;
  const s = modele.scores[i];
  return h(
    'div', {},
    h('strong', {}, modele.t.nom[i]),
    h('span', { classe: 'sous' }, modele.meta.communes[modele.t.commune[i]].nom),
    h('span', { classe: 'sous' }, h('b', {}, s === null ? 'Données insuffisantes' : nombre(s)), s !== null && ' sur 100'),
    h('ul', { classe: 'mini' }, JAUGES.map((j) => {
      const v = modele.valeur(j, i);
      return h('li', {}, h('span', {}, pastille(j), COURT_JAUGE[j]), v === null ? h('span', { classe: 'sous' }, 'insuffisant') : h('b', {}, nombre(v)));
    })),
    suite,
  );
}

/** Plusieurs points au même endroit : une école s'ouvre d'un clic, les autres se déplient. */
export function popupGroupe(
  points: { type: TypePoint | 'ecoles'; p: Proprietes }[], modele: Modele, ouvrirEcole: (i: number) => void,
): HTMLElement {
  return h('div', {}, h('p', { classe: 'surtitre' }, `${points.length} points au même endroit`), h(
    'ul', { classe: 'liste' }, points.map(({ type, p }) => {
      if (type !== 'ecoles') {
        return h('li', {}, h('details', {}, h('summary', {}, texte(p.nom)), popupPoint(type, p, modele.meta, false)));
      }
      const i = p.i as number;
      const s = modele.scores[i];
      return h('li', { classe: 'proche' },
        h('button', { type: 'button', classe: 'lien fort', onclick: () => ouvrirEcole(i) }, modele.t.nom[i]),
        h('span', { classe: 'trajet' }, s === null ? '–' : nombre(s)));
    }),
  ));
}

export function popupPoint(type: TypePoint, p: Proprietes, meta: Meta, avecNom = true): HTMLElement {
  const prov = p as unknown as Provenance;
  const commune = meta.communes.find((c) => c.code === p.commune)?.nom;
  const liees = Number(p.ecoles ?? 0);
  const details: Record<TypePoint, () => HTMLElement> = {
    accueils: () => definition(
      ['Adresse', texte(p.adresse) ?? commune ?? 'inconnue'],
      ['Accueil du soir', ouiNonInconnu(p.soir as boolean | undefined)],
      ['Mercredi', ouiNonInconnu(p.mercredi as boolean | undefined)],
      p.horaires ? ['Horaires', texte(p.horaires)] : null,
      ['Gestionnaire', texte(p.gestionnaire) ?? 'inconnu'],
      ['Écoles rattachées', liees ? pluriel(liees, 'école') : 'aucune'],
    ),
    assos: () => definition(
      ['Siège', texte(p.siege) ?? commune ?? 'inconnu'],
      ['Fédération', texte(p.federation) ?? 'inconnue'],
      p.creation ? ['Création', date(String(p.creation))] : null,
      p.activite ? ['Dernière activité en ligne', date(String(p.activite))] : null,
      ['Écoles rattachées', liees ? pluriel(liees, 'école') : 'aucune'],
    ),
    producteurs: () => definition(
      ['Activités', texte(p.activites) ?? 'inconnues'],
      ['État', LIBELLE_BIO[String(p.bio)]],
      ['Vente directe', ouiNonInconnu(p.vente as boolean | undefined)],
      ['Membre d’une AMAP', ouiNonInconnu(p.amap as boolean | undefined)],
      ['Adresse', `${texte(p.adresse) ?? commune ?? 'inconnue'} — ${LIBELLE_ADRESSE[String(p.adresse_type)]}`],
      ['Jauge producteurs', p.compte ? 'compté' : p.eligible
        ? 'non compté : seul le siège est connu' : 'non compté : hors critères (légumes ou fruits, vente directe)'],
    ),
    relais: () => definition(
      ['Type', LIBELLE_RELAIS[String(p.type)]],
      ['Adresse', texte(p.adresse) ?? commune ?? 'inconnue'],
    ),
  };
  return h(
    'div', {},
    h('p', { classe: 'surtitre' }, SINGULIER[type]),
    avecNom && h('strong', {}, texte(p.nom)),
    details[type](),
    p.site ? h('p', {}, lien(String(p.site), 'Site web')) : null,
    provenance(prov, meta),
  );
}
