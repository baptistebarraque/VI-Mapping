import { Carte, type Lien } from './carte/carte';
import { chargerFond } from './carte/fond';
import { classementCsv, telecharger } from './csv';
import { chargerCouverture, chargerEcoles, chargerFiche, chargerMeta, chargerProducteurs, chargerRelais } from './donnees';
import { depuisAdresse, Magasin, versAdresse, type Selection, type Sujet } from './etat';
import { dansRayon } from './jauges';
import { Modele } from './modele';
import type { Fiche } from './types';
import { Classement } from './ui/classement';
import { vide } from './ui/commun';
import { tableauxCouverture } from './ui/couverture';
import { dialogueSources, ouvrirDialogue } from './ui/dialogue';
import { h, remplacer } from './ui/dom';
import { ficheCommune } from './ui/fiche-commune';
import { ficheEcole, type ContexteFiche } from './ui/fiche-ecole';
import { date, pluriel } from './ui/format';
import { majLegende } from './ui/legende';
import { Parcours } from './ui/parcours';
import { panneauReglages } from './ui/reglages';

import './style.css'; // après la feuille de MapLibre, pour la surcharger

const NB_LIENS = 5;
const DELAI_FICHE_MS = 120;

type Vue = 'carte' | 'reglages' | 'liste';

async function demarrer(app: HTMLElement): Promise<void> {
  const meta = await chargerMeta();
  const [table, producteurs, relais, fond] = await Promise.all([
    chargerEcoles(), chargerProducteurs(), chargerRelais(), chargerFond(),
  ]);
  const modele = new Modele(meta, table);
  const magasin = new Magasin(depuisAdresse(location.hash, meta));
  const { etat } = magasin;
  modele.recalculerProducteurs(etat.rayon);
  modele.recalculerScores(etat.poids);
  modele.filtrer(etat.filtres);

  // ---------------------------------------------------------------- mise en page
  const zoneCarte = h('div', { classe: 'fond-carte' });
  const legende = h('details', { classe: 'legende', open: !matchMedia('(max-width: 900px)').matches });
  // Une flèche remplace la fiche sans l'empiler dans l'historique : « précédent » ramène à l'écran d'avant.
  const parcours = new Parcours(modele, (i) => choisir({ type: 'ecole', uai: table.uai[i] }, true, true));
  const corpsFiche = h('div', { classe: 'corps-fiche' });
  const panneauFiche = h(
    'div', { classe: 'panneau-fiche', tabindex: -1, hidden: true, role: 'region', 'aria-label': 'Fiche' },
    h('div', { classe: 'barre collee' },
      h('button', { type: 'button', classe: 'discret', onclick: () => choisir(null) }, '← Classement'),
      parcours.el),
    corpsFiche,
  );
  const classement = new Classement(
    modele,
    (i) => choisir({ type: 'ecole', uai: table.uai[i] }, true),
    () => telecharger(classementCsv(modele), `classement-ecoles-${meta.genere_le.slice(0, 10)}.csv`),
    { lire: () => etat.filtres.premiers, changer: (premiers) => magasin.filtrer({ premiers }) },
  );
  const droite = h('aside', { classe: 'droite', 'aria-label': 'Classement et fiches' }, classement.el, panneauFiche);
  const reglages = panneauReglages(meta, magasin, {
    commune: (code) => {
      carte.allerCommune(code);
      choisir({ type: 'commune', code });
    },
    departement: (code) => carte.allerDepartement(code),
  });
  const dialogue = dialogueSources(meta, async () => tableauxCouverture(await chargerCouverture()));
  const onglets = (['carte', 'reglages', 'liste'] as const).map((v) => h(
    'button', { type: 'button', 'data-vue': v, onclick: () => voir(v) },
    { carte: 'Carte', reglages: 'Réglages', liste: 'Classement' }[v],
  ));
  remplacer(
    app,
    h('header', { classe: 'entete' },
      h('h1', {}, 'V.i ', h('span', {}, 'Communautés scolaires d’Île-de-France')),
      h('p', {}, `${pluriel(modele.n, 'école')} du 1er degré · données du ${date(meta.genere_le)}`),
      h('button', { type: 'button', onclick: () => ouvrirDialogue(dialogue) }, 'Méthode et sources')),
    h('aside', { classe: 'gauche', 'aria-label': 'Réglages' }, reglages.el),
    h('main', { classe: 'centre', 'aria-label': 'Carte' }, zoneCarte, legende),
    droite,
    h('nav', { classe: 'onglets', 'aria-label': 'Vues' }, onglets),
    dialogue,
  );

  function voir(v: Vue): void {
    app.dataset.vue = v;
    for (const b of onglets) b.setAttribute('aria-pressed', String(b.dataset.vue === v));
  }
  voir('carte');

  const carte = new Carte(zoneCarte, fond, modele, etat, producteurs, relais, {
    ecole: (i) => choisir({ type: 'ecole', uai: table.uai[i] }),
    commune: (code) => choisir({ type: 'commune', code }),
  });

  if (import.meta.env.DEV) Object.assign(window, { carte, modele, magasin });

  // ---------------------------------------------------------------- sélection
  const ctx: ContexteFiche = {
    modele, etat, producteurs, relais,
    ouvrirCommune: (code) => choisir({ type: 'commune', code }, true),
    ouvrirEcole: (i) => choisir({ type: 'ecole', uai: table.uai[i] }, true),
    voir: (xy) => {
      if (app.dataset.vue !== 'carte') voir('carte');
      carte.allerPoint(xy);
    },
  };

  function choisir(s: Selection, deplacer = false, remplace = false): void {
    const avant = JSON.stringify(etat.selection);
    if (avant === JSON.stringify(s)) return;
    magasin.modifier('selection', s);
    if (!remplace) history.pushState(null, '', adresse());
    if (!deplacer || !s) return;
    if (s.type === 'commune') carte.allerCommune(s.code);
    else carte.allerEcole(modele.rang.get(s.uai) ?? 0);
  }

  const ecoleChoisie = (): number | null =>
    etat.selection?.type === 'ecole' ? (modele.rang.get(etat.selection.uai) ?? null) : null;

  let fiche: Fiche | null = null;
  let derniere: string | null = null;

  async function montrerSelection(): Promise<void> {
    const s = etat.selection;
    const cle = JSON.stringify(s);
    derniere = cle;
    const i = s?.type === 'ecole' ? modele.rang.get(s.uai) : undefined;
    const code = s?.type === 'commune' ? s.code : i === undefined ? undefined : meta.communes[table.commune[i]].code;
    classement.marquer(i ?? null);
    parcours.maj(i ?? null);
    if (s === null || code === undefined) {
      fiche = null;
      panneauFiche.hidden = true;
      classement.el.hidden = false;
      void carte.choisirEcole(null);
      void carte.choisirCommune(null);
      return;
    }
    panneauFiche.hidden = false;
    classement.el.hidden = true;
    voir('liste');
    void carte.choisirEcole(i ?? null);
    void carte.choisirCommune(s.type === 'commune' ? code : null);
    remplacer(corpsFiche, vide('Chargement de la fiche…'));
    try {
      fiche = await chargerFiche(code);
    } catch (e) {
      console.error(e);
      if (derniere === cle) remplacer(corpsFiche, vide('Fiche indisponible : vérifiez la connexion puis réessayez.'));
      return;
    }
    if (derniere !== cle) return; // une autre fiche a été demandée entre-temps
    dessinerFiche();
    droite.scrollTop = 0;
    // Pas depuis une flèche : on doit pouvoir la réactiver aussitôt au clavier.
    if (!parcours.el.contains(document.activeElement)) panneauFiche.focus({ preventScroll: true });
  }

  /** (Re)dessine la fiche ouverte ; à la mise à jour, garde les volets ouverts et le défilement. */
  function dessinerFiche(): void {
    const s = etat.selection;
    if (!s || !fiche) return;
    const cleVolet = (d: HTMLDetailsElement): string => d.querySelector('summary')?.firstChild?.textContent ?? '';
    const ouverts = new Set(
      [...corpsFiche.querySelectorAll('details')].filter((d) => d.open).map(cleVolet),
    );
    const defilement = droite.scrollTop;
    const i = s.type === 'ecole' ? modele.rang.get(s.uai) : undefined;
    remplacer(corpsFiche, i === undefined ? ficheCommune(fiche.commune.code, fiche, ctx) : ficheEcole(i, fiche, ctx));
    for (const d of corpsFiche.querySelectorAll('details')) if (ouverts.has(cleVolet(d))) d.open = true;
    droite.scrollTop = defilement;
    if (i !== undefined) void carte.choisirEcole(i, liens(i, fiche));
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
    if (touche('rayon')) modele.recalculerProducteurs(etat.rayon);
    if (touche('rayon', 'poids')) modele.recalculerScores(etat.poids);
    if (touche('rayon', 'poids', 'filtres')) {
      modele.filtrer(etat.filtres);
      classement.maj();
      parcours.maj(ecoleChoisie());
      void carte.majEcoles();
    }
    if (touche('coloration', 'iris')) void carte.majColoration();
    if (touche('couches')) void carte.majCouches();
    if (touche('coloration', 'iris', 'couches')) majLegende(legende, etat);
    if (touche('selection')) void montrerSelection();
    else if (touche('rayon', 'poids', 'filtres')) {
      window.clearTimeout(minuterie);
      minuterie = window.setTimeout(dessinerFiche, DELAI_FICHE_MS);
    }
    history.replaceState(null, '', adresse());
  });
  window.addEventListener('popstate', () => {
    magasin.reprendre(depuisAdresse(location.hash, meta));
    reglages.maj();
  });
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !dialogue.open && etat.selection) choisir(null);
  });

  classement.maj();
  majLegende(legende, etat);
  if (etat.selection) {
    const s = etat.selection;
    if (s.type === 'commune') carte.allerCommune(s.code);
    else if (modele.rang.has(s.uai)) carte.allerEcole(modele.rang.get(s.uai) as number);
    else etat.selection = null;
    void montrerSelection();
  } else if (etat.filtres.commune) carte.allerCommune(etat.filtres.commune);
  else if (etat.filtres.departements.length === 1) carte.allerDepartement(etat.filtres.departements[0]);
  history.replaceState(null, '', adresse());
}

const app = document.getElementById('app') as HTMLElement;
remplacer(app, h('p', { classe: 'attente' }, 'Chargement des écoles…'));
demarrer(app).catch((e: unknown) => {
  console.error(e);
  remplacer(
    app,
    h('div', { classe: 'attente' },
      h('p', {}, 'Les données de la carte n’ont pas pu être chargées.'),
      h('p', { classe: 'note' }, 'Lancez « vi exporter » pour les produire, puis rechargez la page.'),
      h('p', { classe: 'note' }, String(e))),
  );
});
