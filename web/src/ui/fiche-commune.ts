/** Fiche d'une collectivité : identité, cantine, dispositifs, élus, signaux du site, écoles. */

import type { Modele } from '../modele';
import {
  CRITERES_COMMUNES, JAUGES, type CritereCommune, type Dispositif, type Fiche, type FicheCommune, type FicheEcole,
  type Meta,
} from '../types';
import { bloc, contact, definition, etiquette, listeRepliee, metre, provenance, tableSources, vide } from './commun';
import { h, lien } from './dom';
import {
  date, LIBELLE_CATEGORIE_ALIMENTATION, LIBELLE_CRITERE_COMMUNE, LIBELLE_CUISINE, LIBELLE_DISPOSITIF, LIBELLE_ECHELON,
  LIBELLE_GESTION, LIBELLE_GESTIONNAIRE, LIBELLE_JAUGE, LIBELLE_PAGE, LIBELLE_THEME, LIBELLE_VISITE, nombre, pluriel,
  pourcent,
} from './format';
import type { ContexteFiche } from './fiche-ecole';

/** Soutiens, lauréats MGP et syndicats : bloc à part, pas dans la liste des dispositifs. */
const SOUTIENS = new Set<Dispositif['type']>(['soutien_territorial', 'laureat_aap_mgp', 'syndicat_restauration']);

/** Thèmes de délégation utiles au projet, les plus proches d'abord. */
const UTILES = ['restauration', 'scolaire', 'enfance_jeunesse', 'agriculture', 'transition_ecologique'];

/** Élus : le maire et les délégations utiles ; `court` : seulement l'école, la cantine et l'enfance. */
export function listeElus(c: FicheCommune, meta: Meta, court = false): HTMLElement {
  const retenus = court ? UTILES.slice(0, 3) : UTILES;
  const rang = (t: string[] | undefined): number => {
    const l = (t ?? []).map((x) => retenus.indexOf(x)).filter((x) => x >= 0);
    return l.length ? Math.min(...l) : 99;
  };
  const maires = (c.elus ?? []).filter((e) => e.fonction.startsWith('Maire'));
  const delegues = (c.elus ?? []).filter((e) => !maires.includes(e) && rang(e.themes) < 99)
    .sort((a, b) => rang(a.themes) - rang(b.themes));
  const adjoints = (c.elus ?? []).filter((e) => !maires.includes(e) && !delegues.includes(e));
  const ligne = (e: (typeof maires)[number]): HTMLElement => h(
    'li', {},
    h('b', {}, e.nom), ` — ${e.fonction}`,
    e.delegation && h('span', { classe: 'sous' }, e.delegation),
    provenance(e.pd ?? e.p, meta),
  );
  const connues = (c.elus ?? []).some((e) => e.delegation);
  return h(
    'div', {},
    h('h4', {}, 'Élus'),
    maires.length || delegues.length ? h('ul', { classe: 'liste' }, [...maires, ...delegues].map(ligne))
      : vide('Aucun élu trouvé.'),
    !connues && vide('Délégations inconnues : site de la mairie pas encore visité, ou sans page d’élus lisible.'),
    !court && adjoints.length > 0 && h(
      'details', { classe: 'replie' },
      h('summary', {}, `${pluriel(adjoints.length, 'autre élu cité', 'autres élus cités')}`),
      h('ul', { classe: 'liste' }, adjoints.map(ligne)),
    ),
  );
}

/** Nom d'un PAT, qui ouvre sa fiche et montre son périmètre sur la carte. */
export const boutonPat = (d: Dispositif, texte: string, ctx: ContexteFiche): HTMLElement => h('button', {
  type: 'button', classe: 'lien fort', title: 'Voir ce PAT sur la carte', onclick: () => ctx.ouvrirPat(d.id),
}, texte);

export function listeDispositifs(c: FicheCommune, ctx: ContexteFiche, ecole?: FicheEcole): HTMLElement {
  const { meta } = ctx.modele;
  // Pour une école : PAT et appels à projets de la commune ; QPV et cité éducative sont les siens propres.
  const liste = (c.dispositifs ?? []).filter((d) => !SOUTIENS.has(d.type))
    .filter((d) => !ecole || d.type === 'pat' || d.type === 'laureat_aap');
  const laureats = new Set(liste.filter((d) => d.type === 'laureat_aap').map((d) => d.id.split(':')[1]));
  const lignes = liste.filter((d) => d.type !== 'laureat_aap').map((d) => h(
    'li', {},
    d.type === 'pat' ? boutonPat(d, d.nom, ctx) : h('b', {}, d.nom), ' ', etiquette(LIBELLE_DISPOSITIF[d.type]),
    h('span', { classe: 'sous' }, [
      d.type === 'pat' && (d.axe ? 'axe éducation alimentaire' : 'sans axe éducation alimentaire'),
      d.type === 'pat' && d.restauration !== undefined
        && (d.restauration ? 'axe restauration collective' : 'sans axe restauration collective'),
      d.type === 'pat' && laureats.has(d.id.split(':')[1]) && 'lauréat de l’appel à projets du PNA',
      d.niveau, d.annee,
    ].filter(Boolean).join(' · ')),
    d.priorites && h('span', { classe: 'sous' }, d.priorites),
    provenance(d.p, meta),
  ));
  return h('div', {}, h('h4', {}, 'Dispositifs'),
    lignes.length ? listeRepliee(lignes, 6) : vide('Aucun dispositif ne couvre la commune.'));
}

export function ficheCommune(code: string, fiche: Fiche, ctx: ContexteFiche): HTMLElement {
  const { modele } = ctx;
  const { meta } = modele;
  const c = fiche.commune;
  const ecoles = modele.parCommune.get(code) ?? [];
  return h(
    'article', { classe: 'fiche' },
    h('p', { classe: 'surtitre' }, c.type === 'arrondissement' ? 'Arrondissement' : 'Commune'),
    h('h2', {}, c.nom),
    h('p', { classe: 'lieu' }, [meta.departements[c.dep], c.ept ?? c.epci].filter(Boolean).join(' · '),
      c.mere && [' · ', h('button', { type: 'button', classe: 'lien', onclick: () => c.mere && ctx.ouvrirCommune(c.mere.code) }, c.mere.nom)]),
    resumeCommune(code, c, ctx),
    resumeEcoles(ecoles, modele, 'Aucune école du périmètre dans cette commune.'),
    bloc(
      'Collectivité',
      definition(
        ['Code Insee', c.code],
        c.siren ? ['Siren', c.siren] : null,
        c.epci ? ['Intercommunalité', [c.epci, c.ept].filter(Boolean).join(', ')] : null,
        ['Population', c.population === undefined ? 'inconnue'
          : `${nombre(c.population)} habitants${c.population_annee ? ` (${c.population_annee})` : ''}`],
        c.densite === undefined ? null : ['Densité', `${nombre(c.densite)} hab./km²`],
        ['Site de la mairie', lien(c.site, (c.site ?? '').replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')) ?? 'inconnu'],
        c.contact ? ['Contact mairie', contact(c.contact)] : null,
        ['Acteurs recensés', [
          pluriel(c.nb.accueils, 'accueil'), pluriel(c.nb.assos, 'association de parents', 'associations de parents'),
          pluriel(c.nb.relais, 'relais local', 'relais locaux'), pluriel(c.nb.producteurs, 'producteur pris en compte', 'producteurs pris en compte'),
        ].join(' · ')],
      ),
      provenance(c.p, meta),
    ),
    blocCantine(c, meta),
    blocSoutiens(c, meta),
    blocAlimentation(c, meta),
    bloc('Dispositifs et élus', listeDispositifs(c, ctx), listeElus(c, meta)),
    blocSignaux(c, meta),
    c.gestionnaires?.length ? bloc('Gestionnaires périscolaires', h('ul', { classe: 'liste' }, c.gestionnaires.map((g) => h(
      'li', {}, h('b', {}, g.nom), h('span', { classe: 'sous' },
        `${LIBELLE_GESTIONNAIRE[g.type] ?? g.type} · Siren ${g.siren} · ${pluriel(g.n, 'accueil')}`),
    )))) : null,
    blocEcoles(ecoles, ctx),
    tableSources(meta, c),
  );
}

export function resumeEcoles(toutes: number[], modele: Modele, sinon: string): HTMLElement {
  const moyenne = modele.moyenne(toutes.map((i) => modele.scores[i]));
  if (!toutes.length) return vide(sinon);
  return h(
    'div', {},
    h('div', { classe: 'heros' },
      h('span', { classe: 'chiffre' }, moyenne === null ? '–' : nombre(moyenne)),
      h('div', {}, h('b', {}, 'Score moyen des écoles sur 100'),
        h('span', { classe: 'sous' }, pluriel(toutes.length, 'école'), ', toutes confondues'))),
    h('div', { classe: 'jauges' }, JAUGES.map((j) => {
      const valeurs = toutes.map((i) => modele.valeur(j, i));
      const v = modele.moyenne(valeurs);
      const n = valeurs.filter((x) => x !== null).length;
      return h('div', { classe: 'jauge simple' },
        h('span', { classe: 'nom' }, LIBELLE_JAUGE[j], h('span', { classe: 'sous' }, ` ${n}/${toutes.length} écoles`)),
        h('span', { classe: v === null ? 'valeur insuffisant' : 'valeur' }, v === null ? 'données insuffisantes' : nombre(v)),
        metre(v, LIBELLE_JAUGE[j]));
    })),
  );
}

function blocCantine(c: FicheCommune, meta: Meta): HTMLElement {
  const k = c.cantine;
  return bloc(
    'Cantine scolaire',
    k ? definition(
      ['Gestion', k.gestion ? LIBELLE_GESTION[k.gestion] : 'inconnue'],
      ['Bio', k.bio === undefined ? 'non déclaré' : `${pourcent(k.bio)} des achats${k.annee ? ` (${k.annee})` : ''}`],
      ['EGalim', k.egalim === undefined ? 'non déclaré' : `${pourcent(k.egalim)} durables et de qualité, bio compris`],
      ['Restaurants', `${pluriel(k.nb ?? 0, 'inscrit')} sur « ma cantine », ${pluriel(k.declarations ?? 0, 'déclaration')}`],
      k.satellites !== undefined || k.sur_place !== undefined ? ['Production', [
        k.satellites ? `${pluriel(k.satellites, 'satellite')} (repas livrés)` : null,
        k.sur_place ? `${pluriel(k.sur_place, 'cuisine sur place', 'cuisines sur place')}` : null,
        k.regie !== undefined ? `${pourcent(100 * k.regie)} en régie` : null,
        k.repas ? `${nombre(k.repas)} repas par jour` : null,
      ].filter(Boolean).join(' · ') || 'inconnue'] : null,
      k.centrale ? ['Cuisine centrale', h('span', {}, h('b', {}, k.centrale.nom), h('span', { classe: 'sous' }, [
        LIBELLE_CUISINE[k.centrale.type] ?? k.centrale.type,
        k.centrale.commune && `à ${k.centrale.commune}`,
        k.centrale.gestion && LIBELLE_GESTION[k.centrale.gestion],
        k.centrale.cantines && `livre ${pluriel(k.centrale.cantines, 'cantine')} scolaire${k.centrale.cantines > 1 ? 's' : ''} en Île-de-France`,
        k.centrale.bio !== undefined && `${pourcent(k.centrale.bio)} de bio`,
      ].filter(Boolean).join(' · ')), provenance(k.centrale.p, meta))] : null,
    ) : vide('Aucun restaurant scolaire public inscrit sur « ma cantine ».'),
    provenance(c.pg?.cantine, meta),
  );
}

/** Score propre de la commune (étape 1), recalculé selon les poids et le rayon choisis. */
function resumeCommune(code: string, c: FicheCommune, ctx: ContexteFiche): HTMLElement | null {
  const m = ctx.communes;
  const k = m.rang.get(code);
  if (k === undefined) return null;
  const s = m.scores[k];
  const details = new Map((c.score?.criteres ?? []).map((x) => [x.code, x.detail]));
  const texte = (x: CritereCommune): string | null => {
    const d = details.get(x) as unknown;
    if (x === 'producteurs') return m.valeur(x, k) === null ? null : `moyenne des écoles, rayon de ${ctx.etat.rayon.km} km`;
    if (d === undefined || d === null) return null;
    if (x === 'cuisine') return LIBELLE_CUISINE[d as string] ?? String(d);
    if (x === 'cantine_bio') return `${pourcent(d as number)} de bio`;
    if (x === 'associations') return pluriel(d as number, 'association');
    if (x === 'ecoles') return pluriel(d as number, 'élève');
    if (x === 'communications') return (d as string[]).map((t) => LIBELLE_THEME[t] ?? t).join(', ') || 'aucun thème récent';
    if (x === 'soutiens') {
      const v = d as { departement?: number; aap_mgp?: boolean };
      return [v.departement !== undefined && v.departement !== null && `département ${v.departement}/2`,
        v.aap_mgp && 'lauréat AAP MGP'].filter(Boolean).join(' · ') || null;
    }
    return String(d);
  };
  return h(
    'div', {},
    h('div', { classe: 'heros' },
      h('span', { classe: 'chiffre' }, s === null ? '–' : nombre(s)),
      h('div', {}, h('b', {}, 'Score de la commune sur 100'),
        h('span', { classe: 'sous' }, `${m.connus[k]}/${CRITERES_COMMUNES.length} critères connus · étape 1`))),
    h('div', { classe: 'jauges' }, CRITERES_COMMUNES.map((x) => {
      const v = m.valeur(x, k);
      return h('div', { classe: 'jauge simple' },
        h('span', { classe: 'nom' }, LIBELLE_CRITERE_COMMUNE[x], texte(x) && h('span', { classe: 'sous' }, ` ${texte(x)}`)),
        h('span', { classe: v === null ? 'valeur insuffisant' : 'valeur' }, v === null ? 'inconnu' : nombre(v)),
        metre(v, LIBELLE_CRITERE_COMMUNE[x]));
    })),
  );
}

function blocSoutiens(c: FicheCommune, meta: Meta): HTMLElement {
  const liste = (c.dispositifs ?? []).filter((d) => SOUTIENS.has(d.type));
  const lignes = liste.map((d) => h(
    'li', {},
    h('b', {}, d.type === 'soutien_territorial' && d.echelon ? `${LIBELLE_ECHELON[d.echelon]} : ${meta.departements[d.nom] ?? d.nom}` : d.nom),
    ' ', etiquette(d.type === 'soutien_territorial' ? (d.score === undefined ? 'contexte' : `${d.score}/2`) : LIBELLE_DISPOSITIF[d.type]),
    (d.priorites || d.editions) && h('span', { classe: 'sous' }, d.editions ? `Éditions : ${d.editions}` : d.priorites),
    provenance(d.p, meta),
  ));
  return bloc('Soutiens territoriaux',
    lignes.length ? h('ul', { classe: 'liste' }, lignes) : vide('Aucun soutien recensé.'));
}

function blocAlimentation(c: FicheCommune, meta: Meta): HTMLElement {
  const a = c.alimentation;
  if (!a) return bloc('Associations d’alimentation durable', vide('Aucune association recensée au RNA.'));
  const categories = Object.entries(a.categories).map(([k, n]) => `${LIBELLE_CATEGORIE_ALIMENTATION[k] ?? k} : ${n}`);
  return bloc(
    'Associations d’alimentation durable',
    h('p', { classe: 'note' }, `${pluriel(a.n, 'association')} (siège dans la commune) · `, categories.join(' · ')),
    listeRepliee(a.assos.map((x) => h(
      'li', {}, x.site ? lien(x.site, x.nom) : h('b', {}, x.nom), ' ',
      etiquette(LIBELLE_CATEGORIE_ALIMENTATION[x.categorie] ?? x.categorie),
      x.declaration && h('span', { classe: 'sous' }, `Dernière déclaration : ${date(x.declaration)}`),
      provenance(x.p, meta),
    )), 6),
    h('p', { classe: 'note' }, 'Classement automatique par mots-clés du titre et de l’objet : à vérifier avant tout contact.'),
  );
}

function blocSignaux(c: FicheCommune, meta: Meta): HTMLElement {
  const signaux = (c.signaux ?? []).map((s) => h(
    'li', {},
    lien(s.p.u, s.titre ?? 'Page du site') ?? s.titre, ' ', etiquette(LIBELLE_THEME[s.theme] ?? s.theme),
    h('span', { classe: 'sous' }, `${LIBELLE_PAGE[s.type] ?? s.type} · ${s.date ? date(s.date) : 'sans date'}`),
    provenance(s.p, meta),
  ));
  const etat = c.visite ? `${LIBELLE_VISITE[c.visite.statut] ?? c.visite.statut} le ${date(c.visite.date)}`
    : c.site ? 'site pas encore visité' : 'aucun site connu';
  return bloc(
    'Signaux du site de la mairie',
    h('p', { classe: 'note' }, etat.charAt(0).toUpperCase() + etat.slice(1),
      c.nb_signaux > signaux.length && ` · ${c.nb_signaux} signaux, les plus récents affichés`),
    signaux.length ? listeRepliee(signaux, 5) : vide('Aucun signal.'),
  );
}

export function blocEcoles(liste: number[], ctx: ContexteFiche): HTMLElement | null {
  const { modele } = ctx;
  const ecoles = [...liste].sort(
    (a, b) => (modele.scores[b] ?? -1) - (modele.scores[a] ?? -1) || modele.t.nom[a].localeCompare(modele.t.nom[b], 'fr'),
  );
  if (!ecoles.length) return null;
  return bloc('Écoles', listeRepliee(ecoles.map((i) => {
    const s = modele.scores[i];
    return h('li', { classe: 'proche' },
      h('button', { type: 'button', classe: 'lien fort', onclick: () => ctx.ouvrirEcole(i) }, modele.t.nom[i]),
      h('span', { classe: 'trajet' }, s === null ? '–' : nombre(s)));
  }), 12));
}
