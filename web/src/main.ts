import { contactsDe, perimetre, perimetreEcran, type Perimetre } from './carnet';
import { Carte, type Emplacement, type Lien } from './carte/carte';
import { chargerFond } from './carte/fond';
import { classementCommunesCsv, classementCsv, telecharger } from './csv';
import {
  chargerActeurs, chargerCommunes, chargerContacts, chargerCouverture, chargerEcoles, chargerFiche, chargerMeta,
  chargerPats, chargerProducteurs, chargerRelais,
} from './donnees';
import { depuisAdresse, Magasin, versAdresse, type Cible, type Selection, type Sujet } from './etat';
import { dansRayon } from './jauges';
import { Modele } from './modele';
import { ModeleCommunes } from './modele-communes';
import logo from './images/logo-vi.png';
import logoComplet from './images/logo-vraiment-irresistibles.png';
import type { Acteurs, Fiche, NatureFichier } from './types';
import { CarnetContacts } from './ui/carnet';
import { Classement } from './ui/classement';
import { ClassementCommunes } from './ui/classement-communes';
import { vide } from './ui/commun';
import { tableauxCouverture } from './ui/couverture';
import { dialogueSources, ouvrirDialogue } from './ui/dialogue';
import type { ContexteFiche } from './ui/contexte';
import { h, remplacer } from './ui/dom';
import { ficheAbsente, ficheActeur, ficheElu, NATURES_LIEES, territoire, type Dossier } from './ui/fiche-acteur';
import { ficheCommune } from './ui/fiche-commune';
import { ficheEcole } from './ui/fiche-ecole';
import { fichePat } from './ui/fiche-pat';
import { majLegende } from './ui/legende';
import { Parcours } from './ui/parcours';
import { rechercheCommune } from './ui/recherche';
import { panneauReglages } from './ui/reglages';

import './style.css'; // après la feuille de MapLibre, pour la surcharger

const NB_LIENS = 5;
const DELAI_FICHE_MS = 120;

type Vue = 'carte' | 'reglages' | 'liste';

async function demarrer(app: HTMLElement): Promise<void> {
  const meta = await chargerMeta();
  const [table, tableCommunes, producteurs, relais, pats, fond] = await Promise.all([
    chargerEcoles(), chargerCommunes(), chargerProducteurs(), chargerRelais(), chargerPats(), chargerFond(),
  ]);
  const modele = new Modele(meta, table);
  const communes = new ModeleCommunes(meta, tableCommunes, modele);
  const magasin = new Magasin(depuisAdresse(location.hash, meta));
  const { etat } = magasin;
  modele.recalculerProducteurs(etat.rayon);
  modele.recalculerScores(etat.poids);
  modele.filtrer(etat.filtres);
  communes.recalculerProducteurs();
  communes.recalculerScores(etat.poidsCommunes);
  communes.filtrer(etat.filtres);

  // ---------------------------------------------------------------- mise en page
  const zoneCarte = h('div', { classe: 'fond-carte' });
  const legende = h('details', { classe: 'legende', open: !matchMedia('(max-width: 900px)').matches });
  // Une flèche remplace la fiche sans l'empiler dans l'historique : « précédent » ramène à l'écran d'avant.
  const parcours = new Parcours({
    ecole: { nom: 'École', visibles: () => modele.visibles, choisir: (i) => choisir({ type: 'ecole', uai: table.uai[i] }, true, true) },
    commune: {
      nom: 'Commune', visibles: () => communes.visibles,
      choisir: (k) => choisir({ type: 'commune', code: meta.communes[k].code }, true, true),
    },
  });
  const corpsFiche = h('div', { classe: 'corps-fiche' });
  const retour = h('button', { type: 'button', classe: 'discret', title: 'Fiche précédente', onclick: () => history.back() }, '← Retour');
  const panneauFiche = h(
    'div', { classe: 'panneau-fiche', tabindex: -1, hidden: true, role: 'region', 'aria-label': 'Fiche' },
    h('div', { classe: 'barre collee' },
      h('button', { type: 'button', classe: 'discret', onclick: () => choisir(null) }, '× Fermer'),
      retour, parcours.el),
    corpsFiche,
  );
  const classement = new Classement(
    modele,
    (i) => choisir({ type: 'ecole', uai: table.uai[i] }, true),
    () => telecharger(classementCsv(modele), `classement-ecoles-${meta.genere_le.slice(0, 10)}.csv`),
    { lire: () => etat.filtres.premiers, changer: (premiers) => magasin.filtrer({ premiers }) },
    () => etat.filtres.retenues.length,
    () => contactsEcran(),
  );
  const classementCommunes = new ClassementCommunes(
    communes,
    (code) => choisir({ type: 'commune', code }, true),
    { lire: () => etat.filtres.retenues, changer: (retenues) => magasin.filtrer({ retenues }) },
    () => {
      magasin.modifier('etape', 'ecoles');
      carte.allerCommunes(etat.filtres.retenues);
    },
    () => telecharger(classementCommunesCsv(communes, etat.filtres.retenues),
      `classement-communes-${meta.genere_le.slice(0, 10)}.csv`),
    () => contactsEcran(),
  );
  const droite = h('aside', { classe: 'droite', 'aria-label': 'Classement et fiches' },
    classementCommunes.el, classement.el, panneauFiche);
  /** Sans fiche ouverte : le classement de l'étape en cours. */
  const montrerClassement = (): void => {
    classementCommunes.el.hidden = etat.etape !== 'communes';
    classement.el.hidden = etat.etape !== 'ecoles';
  };
  const reglages = panneauReglages(meta, magasin, pats.features.map((f) => f.properties), {
    commune: (code) => {
      carte.allerCommune(code);
      choisir({ type: 'commune', code });
    },
    departements: (codes) => carte.allerDepartements(codes),
    pat: (id) => choisir({ type: 'pat', id }, true),
  });
  const dialogue = dialogueSources(meta, async () => tableauxCouverture(await chargerCouverture()));
  const carnet = new CarnetContacts(meta, (c) => choisir(c, true));
  const positions = new Map(producteurs.features.map((f) => [f.properties.id, f.geometry.coordinates as [number, number]]));
  const ouvrirCarnet = (p: Perimetre): void => carnet.ouvrir(p, chargerContacts()
    .then((c) => contactsDe(c, p, modele, positions, etat.rayon.km)));
  const contactsEcran = (): void => ouvrirCarnet(perimetreEcran(
    etat.etape, etat.filtres, communes.visibles.map((k) => meta.communes[k].code), modele));
  const onglets = (['carte', 'reglages', 'liste'] as const).map((v) => h(
    'button', { type: 'button', 'data-vue': v, onclick: () => voir(v) },
    { carte: 'Carte', reglages: 'Réglages', liste: 'Classement' }[v],
  ));
  remplacer(
    app,
    h('header', { classe: 'entete' },
      h('h1', {}, h('img', { src: logo, alt: 'V.i', width: 150, height: 44 }),
        h('span', {}, 'Communautés scolaires d’Île-de-France')),
      rechercheCommune(communes, (code) => choisir({ type: 'commune', code }, true)),
      h('button', { type: 'button', classe: 'discret', onclick: () => ouvrirDialogue(dialogue) }, 'Méthode et sources')),
    h('aside', { classe: 'gauche', 'aria-label': 'Réglages' }, reglages.el),
    h('main', { classe: 'centre', 'aria-label': 'Carte' }, zoneCarte, legende),
    droite,
    h('nav', { classe: 'onglets', 'aria-label': 'Vues' }, onglets),
    dialogue, carnet.el,
  );

  function voir(v: Vue): void {
    app.dataset.vue = v;
    for (const b of onglets) b.setAttribute('aria-pressed', String(b.dataset.vue === v));
  }
  voir('carte');

  // Une zone peut dépasser l'écran : on la cadre. Un point cliqué y est déjà.
  const carte = new Carte(zoneCarte, fond, modele, etat, producteurs, relais, (c) => choisir(c, c.type === 'pat'));

  if (import.meta.env.DEV) Object.assign(window, { carte, modele, communes, magasin });

  // ---------------------------------------------------------------- sélection
  const ctx: ContexteFiche = {
    modele, communes, etat, producteurs, relais,
    ouvrir: (c) => choisir(c, true),
    ouvrirCarnet: (codes, titre) => ouvrirCarnet(perimetre(titre, codes, modele)),
  };

  function choisir(s: Selection, deplacer = false, remplace = false): void {
    const avant = etat.selection;
    if (JSON.stringify(avant) === JSON.stringify(s)) return;
    magasin.modifier('selection', s);
    // L'état dit si l'entrée d'avant est une fiche : « Fiche précédente » y ramène.
    if (!remplace) history.pushState({ depuisFiche: avant !== null && s !== null }, '', adresse());
    aDeplacer = deplacer;
    if (deplacer && s) montrerSurCarte(s);
  }

  /** Cadre l'instance ; celle d'un acteur n'est connue qu'une fois sa fiche lue (voir montrerSelection). */
  function montrerSurCarte(s: Cible): void {
    if (s.type === 'commune') carte.allerCommune(s.code);
    else if (s.type === 'pat') carte.allerZone('pat', s.id).catch(console.error);
    else if (s.type === 'ecole' && modele.rang.has(s.uai)) carte.allerEcole(modele.rang.get(s.uai) as number);
  }
  let aDeplacer = false;

  const ecoleChoisie = (): number | null =>
    etat.selection?.type === 'ecole' ? (modele.rang.get(etat.selection.uai) ?? null) : null;
  /** Fiche ouverte qui a un classement (école ou commune) et son rang dans les colonnes. */
  const aParcourir = (): { type: 'ecole' | 'commune'; k: number } | null => {
    const s = etat.selection;
    const k = s?.type === 'ecole' ? modele.rang.get(s.uai) : s?.type === 'commune' ? communes.rang.get(s.code) : undefined;
    return s && k !== undefined ? { type: s.type as 'ecole' | 'commune', k } : null;
  };

  let dessin: (() => HTMLElement) | null = null;
  let fiche: Fiche | null = null;
  let derniere: string | null = null;

  /** Lit la fiche d'un acteur et ce qu'il faut pour nommer ses liens. */
  async function chargerDossier(nature: NatureFichier, id: string): Promise<Dossier | null> {
    const liees: Partial<Record<NatureFichier, Acteurs>> = {};
    const [acteurs, contacts] = await Promise.all([
      chargerActeurs(nature), chargerContacts(),
      ...NATURES_LIEES[nature].map(async (n) => {
        liees[n] = await chargerActeurs(n);
      }),
    ]);
    const a = acteurs[id];
    return a ? { nature, id, a, liees, carnet: contacts } : null;
  }

  /** Point, zone ou communes d'un acteur ; traits vers les écoles rattachées. */
  function emplacement({ nature, id, a }: Dossier): Emplacement {
    const symbole = { accueil: 'accueils', asso: 'assos', producteur: a.compte ? 'producteurs' : 'producteurs_autres', relais: 'relais' } as const;
    if (a.xy) {
      const vers = (a.ecoles ?? []).slice(0, 2 * NB_LIENS).flatMap((e): Lien[] => {
        const i = modele.rang.get(e.uai);
        return i === undefined ? [] : [{ vers: [table.lon[i], table.lat[i]], famille: 'scolaire' }];
      });
      return { xy: a.xy, symbole: nature in symbole ? symbole[nature as keyof typeof symbole] : undefined, liens: vers };
    }
    if (nature === 'iris') return { zone: { source: 'iris', id } };
    if (a.type === 'qpv') return { zone: { source: 'qpv', id } };
    if (a.type === 'cite_educative') return { zone: { source: 'cites', id } };
    return { communes: territoire(a, ctx, nature) };
  }

  /** Prépare la fiche choisie : ce qui la dessine, et où la montrer sur la carte. */
  async function preparer(s: Cible): Promise<{ dessin: () => HTMLElement; ou?: Emplacement; fiche?: Fiche } | null> {
    if (s.type === 'pat') {
      const [pats, contacts] = await Promise.all([chargerPats(), chargerContacts()]);
      const p = pats.features.find((f) => f.properties.id === s.id)?.properties;
      return p ? { dessin: () => fichePat(p, contacts, ctx) } : null;
    }
    if (s.type === 'acteur' && s.nature !== 'elu') {
      const d = await chargerDossier(s.nature, s.id);
      return d && { dessin: () => ficheActeur(d, ctx), ou: emplacement(d) };
    }
    if (s.type === 'acteur') {
      const [code, ...id] = s.id.split(':');
      const f = await chargerFiche(code);
      const e = f.commune.elus?.find((x) => x.id === id.join(':'));
      return e ? { dessin: () => ficheElu(e, f, ctx), ou: { communes: [code] } } : null;
    }
    const i = s.type === 'ecole' ? modele.rang.get(s.uai) : undefined;
    const f = await chargerFiche(i === undefined ? (s as { code: string }).code : meta.communes[table.commune[i]].code);
    return { fiche: f, dessin: () => (i === undefined ? ficheCommune(f.commune.code, f, ctx) : ficheEcole(i, f, ctx)) };
  }

  async function montrerSelection(): Promise<void> {
    const s = etat.selection;
    const cle = JSON.stringify(s);
    derniere = cle;
    const i = ecoleChoisie();
    const deplacer = aDeplacer;
    aDeplacer = false;
    classement.marquer(i);
    classementCommunes.marquer(s?.type === 'commune' ? s.code : null);
    parcours.maj(aParcourir());
    retour.hidden = !(history.state as { depuisFiche?: boolean } | null)?.depuisFiche;
    void carte.choisir(i !== null ? { xy: [table.lon[i], table.lat[i]] } : s?.type === 'commune' ? { communes: [s.code] }
      : s?.type === 'pat' ? { zone: { source: 'pat', id: s.id } } : {});
    dessin = null;
    fiche = null;
    if (s === null) {
      panneauFiche.hidden = true;
      montrerClassement();
      return;
    }
    panneauFiche.hidden = false;
    classement.el.hidden = true;
    classementCommunes.el.hidden = true;
    voir('liste');
    remplacer(corpsFiche, vide('Chargement de la fiche…'));
    try {
      const p = await preparer(s);
      if (derniere !== cle) return; // une autre fiche a été demandée entre-temps
      if (!p) {
        remplacer(corpsFiche, ficheAbsente());
        return;
      }
      ({ dessin } = p);
      fiche = p.fiche ?? null;
      if (p.ou) {
        void carte.choisir(p.ou);
        if (deplacer) carte.allerEmplacement(p.ou);
      }
    } catch (e) {
      console.error(e);
      if (derniere === cle) remplacer(corpsFiche, vide('Fiche indisponible : vérifiez la connexion puis réessayez.'));
      return;
    }
    dessinerFiche();
    droite.scrollTop = 0;
    // Pas depuis une flèche : on doit pouvoir la réactiver aussitôt au clavier.
    if (!parcours.el.contains(document.activeElement)) panneauFiche.focus({ preventScroll: true });
  }

  /** (Re)dessine la fiche ouverte ; à la mise à jour, garde les volets ouverts et le défilement. */
  function dessinerFiche(): void {
    if (!dessin) return;
    const cleVolet = (d: HTMLDetailsElement): string => d.querySelector('summary')?.firstChild?.textContent ?? '';
    const ouverts = new Set(
      [...corpsFiche.querySelectorAll('details')].filter((d) => d.open).map(cleVolet),
    );
    const defilement = droite.scrollTop;
    remplacer(corpsFiche, dessin());
    for (const d of corpsFiche.querySelectorAll('details')) if (ouverts.has(cleVolet(d))) d.open = true;
    droite.scrollTop = defilement;
    const i = ecoleChoisie();
    if (i !== null && fiche) void carte.choisir({ xy: [table.lon[i], table.lat[i]], liens: liens(i, fiche) });
  }

  /** Traits de la carte : accueils et associations rattachés, cinq producteurs comptés les plus proches. */
  function liens(i: number, f: Fiche): Lien[] {
    const e = f.ecoles?.[table.uai[i]];
    if (!e) return [];
    const xy = (l: ({ xy?: [number, number] } | undefined)[]): Lien[] =>
      l.flatMap((x) => (x?.xy ? [{ vers: x.xy, famille: 'scolaire' as const }] : [])).slice(0, NB_LIENS);
    const prod: Lien[] = [];
    for (let k = 0; e.prod && k < e.prod.length && prod.length < NB_LIENS; k += 3) {
      const g = producteurs.features[e.prod[k] as number];
      if (!g?.properties.compte || !dansRayon(e.prod[k + 1], e.prod[k + 2], etat.rayon)) continue;
      prod.push({ vers: g.geometry.coordinates as [number, number], famille: 'alimentation' });
    }
    return [
      ...xy((e.accueils ?? []).map((a) => f.accueils?.[a.id])), ...xy((e.assos ?? []).map((a) => f.assos?.[a.id])), ...prod,
    ];
  }

  // ---------------------------------------------------------------- réactions
  const adresse = (): string => {
    const p = versAdresse(etat, meta);
    return p ? `#${p}` : location.pathname + location.search;
  };
  let minuterie = 0;
  magasin.abonner((sujets) => {
    const touche = (...l: Sujet[]): boolean => l.some((s) => sujets.has(s));
    if (touche('rayon')) {
      modele.recalculerProducteurs(etat.rayon);
      communes.recalculerProducteurs();
    }
    if (touche('rayon', 'poids')) modele.recalculerScores(etat.poids);
    if (touche('rayon', 'poidsCommunes')) communes.recalculerScores(etat.poidsCommunes);
    if (touche('rayon', 'poids', 'filtres')) {
      modele.filtrer(etat.filtres);
      classement.maj();
      void carte.majEcoles();
    }
    if (touche('rayon', 'poidsCommunes', 'filtres')) {
      communes.filtrer(etat.filtres);
      classementCommunes.maj();
    }
    if (touche('rayon', 'poids', 'poidsCommunes', 'filtres')) parcours.maj(aParcourir());
    if (touche('filtres')) void carte.majDepartements();
    if (touche('rayon', 'poidsCommunes', 'filtres')) {
      void carte.colorerCommunes(communes.scores);
    }
    if (touche('etape')) {
      if (!etat.selection) montrerClassement();
      majLegende(legende, etat);
    }
    if (touche('coloration', 'iris')) void carte.majColoration();
    if (touche('couches', 'etape')) void carte.majCouches();
    if (touche('coloration', 'iris', 'couches')) majLegende(legende, etat);
    if (touche('selection')) void montrerSelection();
    else if (touche('rayon', 'poids', 'poidsCommunes', 'filtres')) {
      window.clearTimeout(minuterie);
      minuterie = window.setTimeout(dessinerFiche, DELAI_FICHE_MS);
    }
    history.replaceState(history.state, '', adresse());
  });
  window.addEventListener('popstate', () => {
    magasin.reprendre(depuisAdresse(location.hash, meta));
    aDeplacer = true;
    if (etat.selection) montrerSurCarte(etat.selection);
    reglages.maj();
  });
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !dialogue.open && !carnet.el.open && etat.selection) choisir(null);
  });

  classement.maj();
  classementCommunes.maj();
  montrerClassement();
  void carte.colorerCommunes(communes.scores);
  majLegende(legende, etat);
  if (etat.selection) {
    const s = etat.selection;
    if (s.type === 'ecole' && !modele.rang.has(s.uai)) etat.selection = null;
    else montrerSurCarte(s);
    aDeplacer = true;
    void montrerSelection();
  } else if (etat.filtres.commune) carte.allerCommune(etat.filtres.commune);
  else if (etat.filtres.departements.length) carte.allerDepartements(etat.filtres.departements);
  history.replaceState(history.state, '', adresse());
}

const app = document.getElementById('app') as HTMLElement;
remplacer(app, h('div', { classe: 'attente' },
  h('img', { src: logoComplet, alt: 'Vraiment irrésistibles', width: 350, height: 134 }),
  h('p', {}, 'Chargement des écoles…')));
demarrer(app).catch((e: unknown) => {
  console.error(e);
  remplacer(
    app,
    h('div', { classe: 'attente' },
      h('img', { src: logoComplet, alt: 'Vraiment irrésistibles', width: 350, height: 134 }),
      h('p', {}, 'Les données de la carte n’ont pas pu être chargées.'),
      h('p', { classe: 'note' }, 'Lancez « vi exporter » pour les produire, puis rechargez la page.'),
      h('p', { classe: 'note' }, String(e))),
  );
});
