/** Fiche d'un acteur : contact, description, instances liées (communes, écoles, collectivités), provenance. */

import type { Carnet } from '../donnees';
import type { Cible } from '../etat';
import type { Acteur, Acteurs, Elu, Fiche, Nature, NatureFichier } from '../types';
import { bloc, definition, etiquette, listeRepliee, provenance, tableSources, vide, volet, type Paire } from './commun';
import { blocContact, type Relais } from './contact';
import { bouton, boutonActeur, boutonCommune, boutonEcole, type ContexteFiche } from './contexte';
import { h, lien, type Enfant } from './dom';
import {
  date, euros, km, LIBELLE_ADRESSE, LIBELLE_BIO, LIBELLE_CATEGORIE_ALIMENTATION, LIBELLE_CUISINE, LIBELLE_DISPOSITIF,
  LIBELLE_ECHELON, LIBELLE_GESTION, LIBELLE_GESTIONNAIRE, LIBELLE_NATURE, LIBELLE_ORGANISME, LIBELLE_RELAIS, metres,
  minutes, MOTIF_RATTACHEMENT, nombre, ouiNonInconnu, pluriel, pourcent,
} from './format';

/** Autres fichiers dont la fiche a besoin pour nommer ses liens. */
export const NATURES_LIEES: Record<NatureFichier, NatureFichier[]> = {
  accueil: ['gestionnaire'], asso: [], producteur: [], relais: [], alimentation: [], gestionnaire: ['accueil'],
  cuisine: ['organisme'], dispositif: ['organisme'], organisme: ['dispositif'], iris: ['dispositif'],
};

export interface Dossier {
  nature: NatureFichier;
  id: string;
  a: Acteur;
  liees: Partial<Record<NatureFichier, Acteurs>>;
  carnet: Carnet;
}

const RELAIS_MAX = 4;
const COMMUNES_VISIBLES = 8;

export function surtitre(nature: Nature, a: Acteur): string {
  if (nature === 'relais') return LIBELLE_RELAIS[a.type ?? ''] ?? LIBELLE_NATURE.relais[0];
  if (nature === 'dispositif') return LIBELLE_DISPOSITIF[a.type ?? ''] ?? LIBELLE_NATURE.dispositif[0];
  if (nature === 'organisme') return LIBELLE_ORGANISME[a.type as keyof typeof LIBELLE_ORGANISME] ?? LIBELLE_NATURE.organisme[0];
  return LIBELLE_NATURE[nature][0];
}

// ------------------------------------------------------------------ contacts de secours
function relaisDuCarnet(carnet: Carnet, cible: Cible, motif: string): Relais[] {
  const cle = cible.type === 'ecole' ? `ecole:${cible.uai}` : cible.type === 'commune' ? `commune:${cible.code}`
    : cible.type === 'acteur' ? `${cible.nature}:${cible.id}` : `pat:${cible.id}`;
  const l = carnet.par.get(cle);
  return l ? [{ cible, nom: l.nom, motif, contact: l }] : [];
}

export const mairie = (carnet: Carnet, code: string | undefined, motif = 'mairie'): Relais[] =>
  (code ? relaisDuCarnet(carnet, { type: 'commune', code }, motif) : []);
export const collectivite = (carnet: Carnet, siren: string | undefined, motif: string): Relais[] =>
  (siren ? relaisDuCarnet(carnet, { type: 'acteur', nature: 'organisme', id: siren }, motif) : []);

/** Qui contacter quand l'acteur ne publie pas d'e-mail, du plus proche de lui au plus éloigné. */
export function relaisDe(d: Dossier): Relais[] {
  const { a, carnet, nature } = d;
  const ecoles = (motif: string): Relais[] => (a.ecoles ?? []).slice(0, 2)
    .flatMap((e) => relaisDuCarnet(carnet, { type: 'ecole', uai: e.uai }, motif));
  const l = ((): Relais[] => {
    switch (nature) {
      case 'accueil': {
        const regie = a.gestionnaire_type === 'regie' ? d.liees.gestionnaire?.[a.siren ?? '']?.commune : undefined;
        return [...mairie(carnet, regie, 'gestionnaire'), ...mairie(carnet, a.commune), ...ecoles('école rattachée')];
      }
      case 'asso': return [...ecoles('école rattachée'), ...mairie(carnet, a.commune)];
      case 'gestionnaire': return a.commune ? mairie(carnet, a.commune, 'gestionnaire')
        : (a.communes ?? []).flatMap((c) => mairie(carnet, c, 'commune d’un accueil'));
      case 'cuisine': return [
        ...collectivite(carnet, a.organisme, 'gestionnaire'), ...mairie(carnet, a.commune),
        ...(a.communes ?? []).flatMap((c) => mairie(carnet, c, 'commune livrée')),
      ];
      case 'dispositif': return [
        ...collectivite(carnet, a.organisme, 'porteur'), ...mairie(carnet, a.commune, 'porteur'),
        ...(a.type === 'soutien_territorial' ? [] : (a.communes ?? []).flatMap((c) => mairie(carnet, c, 'commune du périmètre'))),
      ];
      case 'iris': return mairie(carnet, a.commune);
      case 'relais': case 'alimentation': return mairie(carnet, a.commune);
      default: return [];
    }
  })();
  const vus = new Set<string>();
  return l.filter((r) => {
    const cle = JSON.stringify(r.cible);
    return !vus.has(cle) && vus.add(cle);
  }).slice(0, RELAIS_MAX);
}

// ------------------------------------------------------------------ description
function description(d: Dossier, ctx: ContexteFiche): Paire[] {
  const { a, nature, liees } = d;
  const { meta } = ctx.modele;
  const commune: Paire = a.commune ? ['Commune', boutonCommune(ctx, a.commune)] : null;
  const porteur: Paire = (a.organisme ?? a.commune) !== undefined && ['Porteur', a.organisme
    ? boutonActeur(ctx, 'organisme', a.organisme, liees.organisme?.[a.organisme]?.nom ?? a.organisme, false)
    : boutonCommune(ctx, a.commune)];
  const activite: Paire = ['Dernière activité en ligne',
    a.activite ? lien(a.activite_url, date(a.activite)) ?? date(a.activite) : 'inconnue'];
  switch (nature) {
    case 'accueil': return [
      commune, a.adresse && ['Adresse', a.adresse],
      ['Accueil du soir', ouiNonInconnu(a.soir)], ['Mercredi', ouiNonInconnu(a.mercredi)],
      a.horaires && ['Horaires', a.horaires],
      ['Gestionnaire', a.gestionnaire ? [
        boutonActeur(ctx, 'gestionnaire', a.siren !== undefined && liees.gestionnaire?.[a.siren] ? a.siren : undefined, a.gestionnaire, false),
        a.gestionnaire_type && ` (${LIBELLE_GESTIONNAIRE[a.gestionnaire_type]})`] : 'inconnu'],
    ];
    case 'asso': return [
      commune, a.siege && ['Siège', a.siege], ['Fédération', a.federation ?? 'inconnue'], a.objet && ['Objet', a.objet],
      a.creation && ['Création', date(a.creation)], activite, a.rna && ['RNA', a.rna], a.siren && ['Siren', a.siren],
    ];
    case 'producteur': return [
      commune, ['Adresse', `${a.adresse ?? 'inconnue'} — ${LIBELLE_ADRESSE[a.adresse_type ?? '']}`],
      ['Activités', a.activites?.join(', ') ?? 'inconnues'], a.productions && ['Productions', a.productions.join(', ')],
      ['État', LIBELLE_BIO[String(a.bio)]], ['Vente directe', ouiNonInconnu(a.vente)],
      ['Vente à la restauration collective', ouiNonInconnu(a.collective)], ['Membre d’une AMAP', ouiNonInconnu(a.amap)],
      ['Jauge producteurs', a.compte ? 'compté' : a.eligible ? 'non compté : seul le siège est connu'
        : 'non compté : hors critères (légumes ou fruits, vente directe)'],
      a.numero_bio && ['Numéro bio', a.numero_bio], a.siret && ['Siret', a.siret],
    ];
    case 'relais': return [['Type', LIBELLE_RELAIS[a.type ?? '']], commune, a.adresse && ['Adresse', a.adresse]];
    case 'alimentation': return [
      ['Catégorie', LIBELLE_CATEGORIE_ALIMENTATION[a.type ?? '']], commune, a.objet && ['Objet', a.objet],
      a.creation && ['Création', date(a.creation)], a.declaration && ['Dernière déclaration', date(a.declaration)],
      a.rna && ['RNA', a.rna],
    ];
    case 'gestionnaire': return [
      ['Type', LIBELLE_GESTIONNAIRE[a.type ?? '']], commune, ['Siren', lien(a.p.u, a.siren) ?? a.siren],
    ];
    case 'cuisine': return [
      ['Gestionnaire', LIBELLE_CUISINE[a.type ?? '']], commune,
      a.organisme && ['Collectivité', boutonActeur(ctx, 'organisme', a.organisme, liees.organisme?.[a.organisme]?.nom ?? a.organisme, false)],
      a.gestion && ['Gestion', LIBELLE_GESTION[a.gestion]],
      a.cantines && ['Cantines scolaires livrées', nombre(a.cantines)], a.repas && ['Repas par jour', nombre(a.repas)],
      typeof a.bio === 'number' && ['Bio', `${pourcent(a.bio)}${a.annee ? ` (${a.annee})` : ''}`],
      a.egalim !== undefined && ['EGalim', pourcent(a.egalim)], ['Siret', a.siret],
    ];
    case 'dispositif': return [
      porteur, a.echelon && ['Échelon', LIBELLE_ECHELON[a.echelon]],
      a.score !== undefined && ['Soutien', `${a.score} sur 2`], a.editions && ['Éditions', a.editions],
      (a.niveau || a.annee) && ['Reconnaissance', [a.niveau, a.annee].filter(Boolean).join(', ')],
      a.priorites && ['Contenu', a.priorites],
    ];
    case 'organisme': return [
      ['Type', LIBELLE_ORGANISME[a.type as keyof typeof LIBELLE_ORGANISME]],
      a.dep && ['Département', meta.departements[a.dep] ?? a.dep], ['Siren', a.siren],
    ];
    case 'iris': return [
      commune, ['Familles avec enfants', a.familles === undefined ? 'inconnu' : `${nombre(a.familles)}${a.annee ? ` (${a.annee})` : ''}`],
      ['Revenu médian', a.revenu === undefined ? 'inconnu' : `${euros(a.revenu)}${a.annee_revenus ? ` (${a.annee_revenus})` : ''}`],
      ['Taux de pauvreté', a.pauvrete === undefined ? 'inconnu' : pourcent(a.pauvrete)],
      a.qpv && ['Quartiers prioritaires', h('ul', {}, a.qpv.map((id) => h('li', {},
        boutonActeur(ctx, 'dispositif', id, liees.dispositif?.[id]?.nom ?? id, false))))],
      ['Code IRIS', d.id],
    ];
  }
}

// ------------------------------------------------------------------ instances liées
export function voletCommunes(codes: string[], ctx: ContexteFiche, titre = 'Communes'): HTMLElement | null {
  const { modele } = ctx;
  const couvertes = new Set(codes);
  const communes = modele.meta.communes.filter((c) => couvertes.has(c.code)).sort((a, b) => a.nom.localeCompare(b.nom, 'fr'));
  if (!communes.length) return null;
  return volet(titre, communes.length, listeRepliee(communes.map((c) => h(
    'li', { classe: 'proche' }, bouton(ctx, { type: 'commune', code: c.code }, c.nom, true),
    h('span', { classe: 'trajet' }, pluriel(modele.parCommune.get(c.code)?.length ?? 0, 'école')))), COMMUNES_VISIBLES));
}

function voletsLies(d: Dossier, ctx: ContexteFiche): Enfant[] {
  const { a, nature, liees } = d;
  const ecole = (uai: string, precision: Enfant): HTMLElement => h('li', { classe: 'proche' },
    boutonEcole(ctx, uai), h('span', { classe: 'trajet' }, precision));
  const titreEcoles: Partial<Record<NatureFichier, string>> = {
    accueil: 'Écoles rattachées', asso: 'Écoles rattachées', dispositif: a.type === 'qpv' ? 'Écoles à moins de 2 km' : 'Écoles membres',
  };
  return [
    a.ecoles && volet(titreEcoles[nature] ?? 'Écoles', a.ecoles.length, listeRepliee(a.ecoles.map((e) => ecole(e.uai,
      e.m !== undefined ? [e.m === 0 && nature === 'dispositif' ? 'dedans' : metres(e.m),
        e.motif && h('span', { classe: 'sous' }, MOTIF_RATTACHEMENT[e.motif])]
        : nature === 'asso' && ['rattachement', h('span', { classe: 'sous' }, pourcent(100 * e.c))])), 8)),
    a.proches && volet('Écoles les plus proches', a.proches.length, listeRepliee(a.proches.map(([uai, x, m]) => ecole(uai,
      [km(x), h('span', { classe: 'sous' }, minutes(m))])), 8)),
    a.uais && volet('Écoles du quartier', a.uais.length, listeRepliee(a.uais.map((u) => ecole(u, null)), 8)),
    a.accueils && volet('Accueils gérés', a.accueils.length, listeRepliee(a.accueils.map((id) => h('li', {},
      boutonActeur(ctx, 'accueil', id, liees.accueil?.[id]?.nom ?? id), ' ',
      liees.accueil?.[id]?.commune && h('span', { classe: 'sous' }, boutonCommune(ctx, liees.accueil[id].commune)))), 8)),
    a.dispositifs && volet('Politiques alimentaires portées', a.dispositifs.length, h('ul', { classe: 'liste' }, a.dispositifs.map((id) => {
      const x = liees.dispositif?.[id];
      return h('li', {}, id.startsWith('pat:') || id.startsWith('referentiel:')
        ? bouton(ctx, { type: 'pat', id }, x?.nom ?? LIBELLE_NATURE.pat[0], true)
        : boutonActeur(ctx, 'dispositif', id, x?.nom ?? id),
      x?.priorites && h('span', { classe: 'sous' }, x.priorites));
    }))),
    a.communes && nature !== 'iris' && voletCommunes(a.communes, ctx, {
      cuisine: 'Communes livrées', gestionnaire: 'Communes de ses accueils', organisme: 'Communes membres',
    }[nature as string] ?? 'Communes du périmètre'),
  ];
}

/** Communes d'un acteur, pour le carnet et la carte. */
export function territoire(a: Acteur, ctx: Pick<ContexteFiche, 'modele'>, nature: Nature): string[] {
  if (nature === 'organisme' && a.type === 'departement') {
    return ctx.modele.meta.communes.filter((c) => c.dep === a.dep).map((c) => c.code);
  }
  return a.communes ?? (a.commune ? [a.commune] : []);
}

export function ficheActeur(d: Dossier, ctx: ContexteFiche): HTMLElement {
  const { a, nature } = d;
  const { meta } = ctx.modele;
  const zone = territoire(a, ctx, nature);
  const alerte = nature === 'alimentation' && 'Classement automatique par mots-clés : à vérifier avant tout contact.';
  return h(
    'article', { classe: 'fiche' },
    h('p', { classe: 'surtitre' }, surtitre(nature, a)),
    h('h2', {}, a.nom),
    h('p', { classe: 'lieu' }, boutonCommune(ctx, a.commune) ?? (a.dep ? meta.departements[a.dep] : null)),
    blocContact(a.contact, ctx, { relais: relaisDe(d) }),
    alerte && h('p', { classe: 'note' }, alerte),
    bloc('Identité', definition(...description(d, ctx)), provenance(a.p, meta)),
    ...voletsLies(d, ctx),
    zone.length > 0 && h('p', { classe: 'pied' }, h('button', {
      type: 'button', onclick: () => ctx.ouvrirCarnet(zone, a.nom),
    }, zone.length > 1 ? 'Contacts de ce territoire' : 'Contacts de la commune')),
    tableSources(meta, a),
  );
}

// ------------------------------------------------------------------ élus
/** Un élu n'a pas d'adresse publiée : on écrit à sa mairie, à son attention. */
export function ficheElu(e: Elu, fiche: Fiche, ctx: ContexteFiche): HTMLElement {
  const { meta } = ctx.modele;
  const c = fiche.commune;
  return h(
    'article', { classe: 'fiche' },
    h('p', { classe: 'surtitre' }, e.fonction),
    h('h2', {}, e.nom),
    h('p', { classe: 'lieu' }, boutonCommune(ctx, c.code)),
    blocContact(undefined, ctx, {
      sujet: `À l’attention de ${e.nom}, ${e.fonction}`,
      absence: 'Aucun contact personnel : le répertoire des élus n’en publie pas.',
      relais: c.contact ? [{ cible: { type: 'commune', code: c.code }, nom: `Mairie de ${c.nom}`, motif: 'à son attention', contact: c.contact }] : [],
    }),
    bloc('Mandat', definition(
      ['Fonction', e.fonction], ['Délégation', e.delegation ?? 'inconnue'],
      e.themes?.length ? ['Thèmes', e.themes.map((t) => etiquette(t.replaceAll('_', ' ')))] : null,
      e.debut ? ['Début du mandat', date(e.debut)] : null,
    ), provenance(e.p, meta), e.pd && provenance(e.pd, meta, 'Délégation : ')),
    tableSources(meta, e, c.contact),
  );
}

export const ficheAbsente = (): HTMLElement => vide('Cette fiche est absente de cet export.');
