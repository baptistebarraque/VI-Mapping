/** État dans l'adresse de la page, export CSV, affichage des taux. */

import { describe, expect, test } from 'vitest';

import { cellule, classementCsv } from '../src/csv';
import { depuisAdresse, etatInitial, filtresVides, versAdresse, type Etat } from '../src/etat';
import { Modele } from '../src/modele';
import { pourcent } from '../src/ui/couverture';
import { meta, table } from './exemple';

describe('adresse', () => {
  test('vide pour les réglages par défaut', () => {
    expect(versAdresse(etatInitial(meta), meta)).toBe('');
    expect(depuisAdresse('', meta)).toEqual(etatInitial(meta));
  });

  test('aller-retour', () => {
    const e: Etat = {
      etape: 'ecoles',
      poids: { engagement: 0, periscolaire: 10, parents: 20, producteurs: 30, familles: 40 },
      poidsCommunes: {
        pat: 30, soutiens: 0, cuisine: 20, cantine_bio: 10, producteurs: 20, associations: 10, communications: 5,
        ecoles: 5,
      },
      rayon: { km: 8, minutes: 20, mode: 'minutes' },
      filtres: {
        ...filtresVides(), departements: ['75', '93'], commune: '93048', secteur: 'prive', types: [0, 2],
        elevesMin: 50, elevesMax: null, seuils: { ...filtresVides().seuils, parents: 30 }, garderInconnues: true,
        connuesMin: 3, premiers: 50, retenues: ['75112', '93048'], criteresMin: 5,
      },
      couches: { ...etatInitial(meta).couches, qpv: true, communes: false },
      coloration: 'familles',
      iris: 'revenu',
      selection: { type: 'ecole', uai: '0930003C' },
    };
    expect(depuisAdresse(`#${versAdresse(e, meta)}`, meta)).toEqual(e);
  });

  test.each([
    { type: 'commune', code: '93048' }, { type: 'pat', id: 'pat:1441' },
  ] as const)('sélection : %o', (selection) => {
    const e: Etat = { ...etatInitial(meta), selection };
    expect(depuisAdresse(`#${versAdresse(e, meta)}`, meta)).toEqual(e);
  });

  test.each([
    '#poids=1-2', '#poids=-5-1-1-1-1', '#poids=500-0-0-0-0', '#rayon=999-45-ou', '#rayon=8-20-autre', '#dep=99',
    '#commune=00000', '#secteur=x', '#types=7', '#eleves=abc', '#seuils=1', '#connues=12', '#premiers=0', '#pat=x', '#premiers=2.5', '#couleur=x', '#iris=x',
  ])('valeur invalide ignorée : %s', (hash) => {
    expect(depuisAdresse(hash, meta)).toEqual(etatInitial(meta));
  });
});

describe('export CSV', () => {
  test('cellules', () => {
    expect(cellule(12.5)).toBe('12,5');
    expect(cellule(null)).toBe('');
    expect(cellule('a;b')).toBe('"a;b"');
    expect(cellule('dit "oui"')).toBe('"dit ""oui"""');
  });

  test.each(['=1+1', '+1', '-1', '@x'])('une formule est neutralisée : %s', (x) => {
    expect(cellule(x)).toBe(`'${x}`);
  });

  test('une ligne par école affichée, dans l’ordre du classement', () => {
    const m = new Modele(meta, table);
    const e = etatInitial(meta);
    m.recalculerProducteurs(e.rayon);
    m.recalculerScores(e.poids);
    m.filtrer({ ...filtresVides(), commune: '93048' });
    const csv = classementCsv(m);
    expect(csv.startsWith('\uFEFFrang;uai;ecole;')).toBe(true); // BOM : accents lus par un tableur
    const lignes = csv.trim().split('\r\n');
    expect(lignes).toHaveLength(4);
    expect(lignes[1]).toContain('0930004D');
    expect(lignes.find((l) => l.includes('0930003C'))).toContain(`"'=Cité; ""C"""`);
    expect(lignes.at(-1)).toContain('0930002B;École B;Montreuil;93048;93;Maternelle;Publique;;;REP;;;;;;;0;');
  });
});

test.each([[null, '–'], [0, '0 %'], [0.004, '< 1 %'], [0.5, '50 %'], [0.999, '> 99 %'], [1, '100 %']] as const)(
  'taux %s',
  (taux, attendu) => {
    expect(pourcent(taux)).toBe(attendu);
  },
);
