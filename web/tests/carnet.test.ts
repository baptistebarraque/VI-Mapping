/** Carnet de contacts : périmètre, sélection des lignes, adresses, export CSV et lien vers la fiche. */

import { describe, expect, test } from 'vitest';

import {
  adresses, cibleDe, contactsCsv, contactsDe, distanceKm, lienProfond, perimetre, perimetreEcran,
} from '../src/carnet';
import type { Carnet } from '../src/donnees';
import { depuisAdresse, filtresVides } from '../src/etat';
import { Modele } from '../src/modele';
import type { LigneContact } from '../src/types';
import { meta, table } from './exemple';

const p = { s: 'annuaire', u: 'https://exemple.fr/fiche', d: '2026-11-25', c: 0.9 };
const ligne = (x: Partial<LigneContact> & Pick<LigneContact, 'n' | 'id'>): LigneContact => ({ nom: x.id, p, ...x });
const lignes: LigneContact[] = [
  ligne({ n: 'producteur', id: 'loin' }), ligne({ n: 'producteur', id: 'pres', email: 'ferme@x.fr' }),
  ligne({ n: 'ecole', id: '0930002B', commune: '93048', email: 'b@ac.fr' }),
  ligne({ n: 'ecole', id: '0750001A', commune: '75112', email: 'a@ac.fr' }),
  ligne({ n: 'commune', id: '93048', commune: '93048', email: 'mairie@montreuil.fr' }),
  ligne({ n: 'commune', id: '75056', commune: '75056', tel: '39 75' }),
  ligne({ n: 'organisme', id: 'ept', type: 'ept', communes: ['93048'], email: 'mairie@montreuil.fr' }),
  ligne({ n: 'organisme', id: 'dep75', type: 'departement', dep: '75' }),
  ligne({ n: 'organisme', id: 'region', type: 'region' }),
  ligne({ n: 'pat', id: 'pat:1', communes: ['75056'] }),
];
const carnet: Carnet = { lignes, par: new Map(lignes.map((l) => [`${l.n}:${l.id}`, l])) };
const positions = new Map<string, [number, number]>([['pres', [2.45, 48.9]], ['loin', [3.5, 48.9]]]);
const modele = new Modele(meta, table);
const ids = (codes: string[]): string[] => contactsDe(carnet, perimetre('', codes, modele), modele, positions, 20).map((l) => l.id);

describe('périmètre', () => {
  test('un arrondissement apporte sa mairie centrale, pas les écoles des autres', () => {
    const x = perimetre('', ['75112'], modele);
    expect([...x.codes].sort()).toEqual(['75056', '75112']);
    expect(x.ecoles).toEqual([0]);
  });

  test('Paris entier ne compte pas ses écoles deux fois', () => {
    expect(perimetre('', ['75056'], modele).ecoles).toEqual([0]);
  });

  test('écran : communes retenues, sinon affichées ; à l’étape 2, les écoles affichées', () => {
    const f = filtresVides();
    expect([...perimetreEcran('communes', f, ['93048'], modele).codes]).toEqual(['93048']);
    expect([...perimetreEcran('communes', { ...f, retenues: ['75112'] }, ['93048'], modele).codes]).toContain('75112');
    modele.visibles = [2];
    const e = perimetreEcran('ecoles', f, [], modele);
    expect(e.ecoles).toEqual([2]);
    expect([...e.codes]).toEqual(['93048']);
  });
});

describe('contacts d’un territoire', () => {
  test('mairie, collectivités, écoles et producteurs proches, dans cet ordre', () => {
    expect(ids(['93048'])).toEqual(['93048', 'ept', 'region', '0930002B', 'pres']);
  });

  test('département et PAT de la commune mère', () => {
    expect(ids(['75112'])).toEqual(['75056', 'dep75', 'region', 'pat:1', '0750001A', 'pres']);
  });

  test('distance à vol d’oiseau', () => {
    expect(distanceKm(2.35, 48.85, 2.35, 48.95)).toBeCloseTo(11.12, 1);
  });

  test('adresses sans double', () => {
    expect(adresses(lignes)).toEqual(['ferme@x.fr', 'b@ac.fr', 'a@ac.fr', 'mairie@montreuil.fr']);
  });
});

describe('traçabilité', () => {
  test('chaque ligne du CSV porte sa source, sa date et le lien vers sa fiche', () => {
    const [entete, l] = contactsCsv([lignes[4]], meta, 'https://carte.fr/#dep=93').replace('﻿', '').trim().split(/\r?\n/)
      .map((x) => x.split(';'));
    const champ = (nom: string): string => l[entete.indexOf(nom)];
    expect(champ('email')).toBe('mairie@montreuil.fr');
    expect(champ('commune')).toBe('Montreuil');
    expect(champ('url_source')).toBe('https://exemple.fr/fiche');
    expect(champ('collecte_le')).toBe('2026-11-25');
    expect(champ('confiance')).toBe('0,9');
    expect(champ('fiche')).toContain('https://carte.fr/#');
  });

  test('un nom qui commence par = ne devient pas une formule', () => {
    expect(contactsCsv([ligne({ n: 'ecole', id: '0930003C', nom: '=1+1' })], meta, '/')).not.toMatch(/(^|;)=1/m);
  });

  test.each(lignes)('le lien rouvre la fiche : $n $id', (l) => {
    const c = cibleDe(l);
    expect(depuisAdresse(new URL(lienProfond(c, 'https://carte.fr/')).hash, meta).selection).toEqual(c);
  });
});
