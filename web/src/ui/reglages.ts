/** Panneau de gauche : filtres, poids du score, rayon des producteurs, couches. */

import {
  filtresVides, type Coloration, type Couche, type Etape, type Etat, type Magasin, type Secteur, type VariableIris,
} from '../etat';
import {
  CRITERES_COMMUNES, JAUGES, TYPES_ECOLE, type CritereCommune, type Meta, type Mode, type NomJauge, type ProprietesPat,
} from '../types';
import { ENCRE_2, INCONNU, RAMPE_ECOLES, RAMPE_IRIS, SURFACE, ZONE_CITE, ZONE_PAT } from '../couleurs';
import { ACTEUR_CRITERE, pastille } from './commun';
import { h, identifiant, remplacer, type Enfant } from './dom';
import {
  COURT_CRITERE_COMMUNE, COURT_JAUGE, LIBELLE_COLORATION, LIBELLE_COUCHE, LIBELLE_CRITERE_COMMUNE, LIBELLE_IRIS, pluriel,
} from './format';
import { rond, symbole, zone } from './symboles';

interface Curseur {
  el: HTMLElement;
  maj: (valeur: number) => void;
}

function curseur(
  libelle: Enfant,
  o: { min: number; max: number; pas: number; valeur: number; format: (x: number) => string; change: (x: number) => void },
): Curseur {
  const id = identifiant('curseur');
  const sortie = h('output', { for: id }, o.format(o.valeur));
  const input = h('input', {
    id, type: 'range', min: o.min, max: o.max, step: o.pas, value: o.valeur,
    oninput: () => {
      sortie.textContent = o.format(input.valueAsNumber);
      o.change(input.valueAsNumber);
    },
  });
  return {
    el: h('div', { classe: 'curseur' }, h('label', { for: id }, libelle), sortie, input),
    maj: (v) => {
      input.value = String(v);
      sortie.textContent = o.format(v);
    },
  };
}

function segments<T extends string>(
  libelle: string, choix: [T, string][], lire: () => T, change: (x: T) => void,
): { el: HTMLElement; maj: () => void } {
  const boutons = choix.map(([valeur, texte]) => {
    const b = h('button', {
      type: 'button', 'data-valeur': valeur,
      onclick: () => {
        change(valeur);
        maj();
      },
    }, texte);
    return b;
  });
  const maj = (): void => {
    for (const b of boutons) b.setAttribute('aria-pressed', String(b.dataset.valeur === lire()));
  };
  maj();
  return { el: h('div', { classe: 'segments', role: 'group', 'aria-label': libelle }, boutons), maj };
}

function puces(
  libelle: string, choix: [string, string, string][], actives: () => string[], basculer: (x: string) => void,
): { el: HTMLElement; maj: () => void } {
  const boutons = choix.map(([valeur, texte, titre]) => h('button', {
    type: 'button', classe: 'puce', 'data-valeur': valeur, title: titre,
    onclick: () => {
      basculer(valeur);
      maj();
    },
  }, texte));
  const maj = (): void => {
    const l = actives();
    for (const b of boutons) b.setAttribute('aria-pressed', String(l.includes(b.dataset.valeur ?? '')));
  };
  maj();
  return { el: h('div', { classe: 'puces', role: 'group', 'aria-label': libelle }, boutons), maj };
}

const section = (titre: string, ouverte: boolean, ...contenu: Enfant[]): HTMLElement =>
  h('details', { classe: 'section', open: ouverte }, h('summary', {}, h('h2', {}, titre)), ...contenu);

const note = (...texte: Enfant[]): HTMLElement => h('p', { classe: 'note' }, ...texte);

export interface Reglages {
  el: HTMLElement;
  maj: () => void;
}

export interface Deplacements {
  commune: (code: string) => void;
  departement: (code: string) => void;
  pat: (id: string) => void;
}

export function panneauReglages(meta: Meta, m: Magasin, pats: ProprietesPat[], aller: Deplacements): Reglages {
  const e = (): Etat => m.etat;
  const majs: (() => void)[] = [];
  const suivre = <X extends { maj: () => void }>(x: X): X => {
    majs.push(x.maj);
    return x;
  };
  const suivi = (c: Curseur, lire: () => number): HTMLElement => {
    majs.push(() => c.maj(lire()));
    return c.el;
  };

  // ------------------------------------------------------------ filtres
  const departements = suivre(puces(
    'Départements', Object.entries(meta.departements).map(([code, nom]) => [code, code, nom]),
    () => e().filtres.departements,
    (d) => {
      const l = e().filtres.departements;
      const choisis = l.includes(d) ? l.filter((x) => x !== d) : [...l, d].sort();
      m.filtrer({ departements: choisis });
      if (choisis.length === 1) aller.departement(choisis[0]);
    },
  ));

  const parNom = new Map(meta.communes.map((c) => [`${c.nom} (${c.dep})`, c.code]));
  const idListe = identifiant('communes');
  const commune = h('input', {
    type: 'search', list: idListe, placeholder: 'Toutes', autocomplete: 'off', id: identifiant('commune'),
    onchange: () => {
      const code = parNom.get(commune.value) ?? null;
      if (code === null && commune.value.trim() !== '') {
        commune.setCustomValidity('Choisissez une commune de la liste.');
        commune.reportValidity();
        return;
      }
      commune.setCustomValidity('');
      m.filtrer({ commune: code });
      if (code) aller.commune(code);
    },
    oninput: () => commune.setCustomValidity(''),
  });
  majs.push(() => {
    const c = meta.communes.find((x) => x.code === e().filtres.commune);
    commune.value = c ? `${c.nom} (${c.dep})` : '';
  });
  const listeCommunes = h('datalist', { id: idListe }, [...parNom.keys()].map((n) => h('option', { value: n })));

  const secteur = suivre(segments<Secteur>(
    'Secteur', [['tous', 'Toutes'], ['public', 'Publiques'], ['prive', 'Privées']],
    () => e().filtres.secteur, (s) => m.filtrer({ secteur: s }),
  ));
  const types = suivre(puces(
    'Type d’école', TYPES_ECOLE.map((t, k) => [String(k), t, t]), () => e().filtres.types.map(String),
    (x) => {
      const l = e().filtres.types;
      m.filtrer({ types: l.includes(+x) ? l.filter((y) => y !== +x) : [...l, +x].sort() });
    },
  ));
  const taille = (cle: 'elevesMin' | 'elevesMax', texte: string): HTMLElement => {
    const id = identifiant('taille');
    const input = h('input', {
      id, type: 'number', min: 0, max: 2000, step: 10, inputmode: 'numeric', placeholder: cle === 'elevesMin' ? '0' : 'max',
      oninput: () => m.filtrer({ [cle]: input.value === '' ? null : Math.max(0, input.valueAsNumber) }),
    });
    majs.push(() => {
      input.value = String(e().filtres[cle] ?? '');
    });
    return h('label', { for: id }, texte, input);
  };
  const connues = curseur('Jauges connues, au moins', {
    min: 0, max: 5, pas: 1, valeur: e().filtres.connuesMin, format: (x) => `${x} sur 5`,
    change: (x) => m.filtrer({ connuesMin: x }),
  });
  const seuils = JAUGES.map((j) => suivi(curseur([pastille(j), COURT_JAUGE[j]], {
    min: 0, max: 100, pas: 5, valeur: e().filtres.seuils[j], format: (x) => (x === 0 ? 'aucun' : `≥ ${x}`),
    change: (x) => m.filtrer({ seuils: { ...e().filtres.seuils, [j]: x } }),
  }), () => e().filtres.seuils[j]));
  const garder = h('input', {
    type: 'checkbox', onchange: () => m.filtrer({ garderInconnues: garder.checked }),
  });
  majs.push(() => {
    garder.checked = e().filtres.garderInconnues;
  });

  const avance = h(
    'details', { classe: 'replie avance' },
    h('summary', {}, 'Plus de filtres'),
    h('div', { classe: 'champ taille' }, h('span', { classe: 'libelle' }, 'Élèves'),
      taille('elevesMin', 'de'), taille('elevesMax', 'à')),
    suivi(connues, () => e().filtres.connuesMin),
    h('fieldset', {}, h('legend', {}, 'Seuil minimal par jauge'), seuils,
      h('label', { classe: 'case' }, garder, ' Garder les écoles dont la jauge est inconnue')),
  );
  majs.push(() => { // un filtre actif ne reste jamais caché
    const f = e().filtres;
    if (f.elevesMin !== null || f.elevesMax !== null || f.connuesMin > 0 || JAUGES.some((j) => f.seuils[j] > 0)) avance.open = true;
  });

  // ------------------------------------------------------------ étape : communes, puis écoles
  const etape = suivre(segments<Etape>(
    'Étape', [['communes', '1. Communes'], ['ecoles', '2. Écoles']], () => e().etape, (x) => m.modifier('etape', x),
  ));
  const criteres = curseur('Critères connus, au moins', {
    min: 0, max: CRITERES_COMMUNES.length, pas: 1, valeur: e().filtres.criteresMin,
    format: (x) => `${x} sur ${CRITERES_COMMUNES.length}`, change: (x) => m.filtrer({ criteresMin: x }),
  });
  const retenues = h('p', { classe: 'note' });
  const effacerRetenues = h('button', {
    type: 'button', classe: 'discret', onclick: () => m.filtrer({ retenues: [] }),
  }, 'Toutes les communes');
  const majRetenues = (): void => {
    const n = e().filtres.retenues.length;
    retenues.textContent = n
      ? `Écoles de ${pluriel(n, 'commune retenue', 'communes retenues')} à l’étape 1.`
      : 'Écoles de toutes les communes (aucune retenue à l’étape 1).';
    effacerRetenues.hidden = n === 0;
  };
  majs.push(majRetenues);
  const pourCommunes = h('div', { classe: 'pour-communes' }, suivi(criteres, () => e().filtres.criteresMin));
  const pourEcoles = h(
    'div', { classe: 'pour-ecoles' },
    h('div', { classe: 'champ' }, retenues, effacerRetenues),
    h('div', { classe: 'champ' }, h('label', { classe: 'libelle', for: commune.id }, 'Commune'), commune, listeCommunes),
    h('div', { classe: 'champ' }, h('span', { classe: 'libelle' }, 'Secteur'), secteur.el),
    h('div', { classe: 'champ' }, h('span', { classe: 'libelle' }, 'Type'), types.el),
    avance,
  );

  const filtres = section(
    'Filtres', true,
    h('div', { classe: 'champ' }, h('span', { classe: 'libelle' }, 'Départements'), departements.el),
    pourCommunes, pourEcoles,
    h('button', {
      type: 'button', classe: 'discret',
      onclick: () => {
        // Les communes retenues à l'étape 1 ne sont pas des filtres : elles restent.
        m.modifier('filtres', { ...filtresVides(), retenues: e().filtres.retenues });
        maj();
      },
    }, 'Effacer les filtres'),
  );

  // ------------------------------------------------------------ poids des critères communaux
  const partsCommunes = new Map<CritereCommune, HTMLElement>();
  const majPartsCommunes = (): void => {
    const total = CRITERES_COMMUNES.reduce((s, c) => s + e().poidsCommunes[c], 0);
    for (const [c, el] of partsCommunes) {
      el.textContent = total ? `${Math.round((100 * e().poidsCommunes[c]) / total)} %` : '–';
    }
  };
  const poidsCommunes = CRITERES_COMMUNES.map((c) => {
    const part = h('span', { classe: 'part' });
    partsCommunes.set(c, part);
    const x = curseur([pastille(ACTEUR_CRITERE[c]), COURT_CRITERE_COMMUNE[c]], {
      min: 0, max: 100, pas: 5, valeur: e().poidsCommunes[c], format: String,
      change: (v) => {
        m.modifier('poidsCommunes', { ...e().poidsCommunes, [c]: v });
        majPartsCommunes();
      },
    });
    x.el.querySelector('input')?.before(part);
    x.el.classList.add('avec-part');
    x.el.title = LIBELLE_CRITERE_COMMUNE[c];
    return suivi(x, () => e().poidsCommunes[c]);
  });
  majs.push(majPartsCommunes);
  const sectionPoidsCommunes = section(
    'Poids du score', false, poidsCommunes,
    note('Score de la commune = moyenne pondérée de ses critères connus. Un critère inconnu sort de la moyenne. '
      + 'Le critère « producteurs » suit le rayon choisi plus bas.'),
    h('button', {
      type: 'button', classe: 'discret',
      onclick: () => {
        m.modifier('poidsCommunes', { ...meta.poids_communes });
        maj();
      },
    }, 'Poids par défaut'),
  );

  // ------------------------------------------------------------ poids
  const parts = new Map<NomJauge, HTMLElement>();
  const majParts = (): void => {
    const total = JAUGES.reduce((s, j) => s + e().poids[j], 0);
    for (const [j, el] of parts) el.textContent = total ? `${Math.round((100 * e().poids[j]) / total)} %` : '–';
  };
  const poids = JAUGES.map((j) => {
    const part = h('span', { classe: 'part' });
    parts.set(j, part);
    const c = curseur([pastille(j), COURT_JAUGE[j]], {
      min: 0, max: 100, pas: 5, valeur: e().poids[j], format: String,
      change: (x) => {
        m.modifier('poids', { ...e().poids, [j]: x });
        majParts();
      },
    });
    c.el.querySelector('input')?.before(part);
    c.el.classList.add('avec-part');
    return suivi(c, () => e().poids[j]);
  });
  majs.push(majParts);
  const sectionPoids = section(
    'Poids du score', false, poids,
    note('Score = moyenne pondérée des jauges connues. Une jauge inconnue ne compte pas 0 : elle sort de la moyenne.'),
    h('button', {
      type: 'button', classe: 'discret',
      onclick: () => {
        m.modifier('poids', { ...meta.poids });
        maj();
      },
    }, 'Poids par défaut'),
  );

  // ------------------------------------------------------------ rayon
  const rayonKm = curseur('Distance par la route', {
    min: 5, max: meta.km_max, pas: 1, valeur: e().rayon.km, format: (x) => `${x} km`,
    change: (x) => m.modifier('rayon', { ...e().rayon, km: x }),
  });
  const rayonMin = curseur('Temps de trajet', {
    min: 5, max: 60, pas: 1, valeur: e().rayon.minutes, format: (x) => `${x} min`,
    change: (x) => m.modifier('rayon', { ...e().rayon, minutes: x }),
  });
  const mode = suivre(segments<Mode>(
    'Dans le rayon si', [['ou', 'km ou min'], ['km', 'km'], ['minutes', 'minutes']],
    () => e().rayon.mode, (x) => m.modifier('rayon', { ...e().rayon, mode: x }),
  ));
  const sectionRayon = section(
    'Rayon des producteurs', false,
    h('div', { classe: 'champ' }, h('span', { classe: 'libelle' }, 'Dans le rayon selon'), mode.el),
    suivi(rayonKm, () => e().rayon.km), suivi(rayonMin, () => e().rayon.minutes),
    note(`Trajets en voiture sans trafic (OSRM), plutôt optimistes en zone dense. Paires calculées jusqu’à ${meta.km_max} km à vol d’oiseau.`),
    h('button', {
      type: 'button', classe: 'discret',
      onclick: () => {
        m.modifier('rayon', { ...meta.rayon });
        maj();
      },
    }, 'Rayon par défaut'),
  );

  // ------------------------------------------------------------ couches
  const signes: Record<Couche, () => Node> = {
    ecoles: () => rond(RAMPE_ECOLES[2]),
    accueils: () => symbole('accueils'),
    assos: () => symbole('assos'),
    producteurs: () => symbole('producteurs'),
    relais: () => symbole('relais'),
    communes: () => zone(INCONNU, 'none'),
    pat: () => zone(ZONE_PAT, `${ZONE_PAT}22`),
    cites: () => zone(ZONE_CITE, `${ZONE_CITE}22`),
    qpv: () => zone(ENCRE_2, 'none', true),
    iris: () => zone(SURFACE, RAMPE_IRIS[2]),
  };
  const bascule = (c: Couche): HTMLElement => {
    const input = h('input', {
      type: 'checkbox',
      onchange: () => m.modifier('couches', { ...e().couches, [c]: input.checked }),
    });
    majs.push(() => {
      input.checked = e().couches[c];
    });
    return h('label', { classe: 'case' }, input, signes[c](), h('span', {}, LIBELLE_COUCHE[c]));
  };
  const choix = <T extends string>(
    libelle: string, options: [T, string][], lire: () => T, change: (x: T) => void,
  ): HTMLElement => {
    const id = identifiant('choix');
    const select = h(
      'select', { id, onchange: () => change(select.value as T) },
      options.map(([v, t]) => h('option', { value: v }, t)),
    );
    majs.push(() => {
      select.value = lire();
    });
    return h('div', { classe: 'champ' }, h('label', { classe: 'libelle', for: id }, libelle), select);
  };
  const idPat = identifiant('pat');
  const pat = h(
    'select', { id: idPat, onchange: () => pat.value && aller.pat(pat.value) },
    h('option', { value: '' }, 'Choisir…'),
    [...pats].sort((a, b) => a.nom.localeCompare(b.nom, 'fr', { ignorePunctuation: true }))
      .map((p) => h('option', { value: p.id }, p.nom)),
  );
  const majPat = (): void => {
    const s = e().selection;
    pat.value = s?.type === 'pat' ? s.id : '';
  };
  majs.push(majPat);
  m.abonner((sujets) => {
    if (sujets.has('selection')) majPat();
  });
  const couches = section(
    'Couches de la carte', false,
    choix<Coloration>(
      'Couleur des écoles', Object.entries(LIBELLE_COLORATION) as [Coloration, string][],
      () => e().coloration, (x) => m.modifier('coloration', x),
    ),
    h('fieldset', {}, h('legend', {}, 'Points'),
      (['ecoles', 'accueils', 'assos', 'producteurs', 'relais'] as const).map(bascule)),
    h('fieldset', {}, h('legend', {}, 'Zones'), (['communes', 'pat', 'cites', 'qpv', 'iris'] as const).map(bascule)),
    h('div', { classe: 'champ' }, h('label', { classe: 'libelle', for: idPat }, 'Voir un PAT'), pat),
    choix<VariableIris>(
      'Variable des IRIS', Object.entries(LIBELLE_IRIS) as [VariableIris, string][],
      () => e().iris,
      (x) => {
        m.modifier('iris', x);
        if (!e().couches.iris) {
          m.modifier('couches', { ...e().couches, iris: true });
          maj();
        }
      },
    ),
  );

  const majEtape = (): void => {
    const communes = e().etape === 'communes';
    pourCommunes.hidden = !communes;
    sectionPoidsCommunes.hidden = !communes;
    pourEcoles.hidden = communes;
    sectionPoids.hidden = communes;
  };
  majs.push(majEtape);
  m.abonner((sujets) => {
    if (sujets.has('etape')) majEtape();
    if (sujets.has('filtres')) majRetenues();
  });

  const el = h('div', { classe: 'reglages' });
  remplacer(el, h('div', { classe: 'etape' }, etape.el), filtres, sectionPoidsCommunes, sectionPoids, sectionRayon,
    couches);
  const maj = (): void => majs.forEach((f) => f());
  maj();
  return { el, maj };
}
