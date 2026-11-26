/** Fiche d'une école : identité, jauges, acteurs liés, producteurs et relais dans le rayon, sources. */

import { dansRayon, jaugeProducteurs } from '../jauges';
import type { Cible } from '../etat';
import {
  EDUCATION_PRIORITAIRE, JAUGES, SECTEURS, TYPES_ECOLE, type Critere, type Fiche, type FicheEcole, type NomJauge,
} from '../types';
import {
  anneau, bloc, definition, etiquette, listeRepliee, metre, provenance, tableSources, vide, volet,
} from './commun';
import { blocContact } from './contact';
import { boutonActeur, boutonCommune, montrerBloc, type ContexteFiche } from './contexte';
import { h, lien, type Enfant } from './dom';
import {
  date, dixieme, euros, km, LIBELLE_ADRESSE, LIBELLE_CRITERE, LIBELLE_GESTIONNAIRE, LIBELLE_JAUGE, LIBELLE_NATURE,
  LIBELLE_RELAIS, LIBELLE_THEME, metres, minutes, MOTIF_RATTACHEMENT, nombre, ouiNonInconnu, pluriel, pourcent,
} from './format';
import { listeDispositifs, listeElus } from './fiche-commune';
import { blocRelance } from './relance';

interface Proche {
  rang: number;
  km: number;
  minutes: number | null;
}

function proches(liste: (number | null)[] | undefined): Proche[] {
  const l: Proche[] = [];
  for (let k = 0; liste && k < liste.length; k += 3) {
    l.push({ rang: liste[k] as number, km: liste[k + 1] as number, minutes: liste[k + 2] });
  }
  return l;
}

export function ficheEcole(i: number, fiche: Fiche, ctx: ContexteFiche): HTMLElement {
  const { modele } = ctx;
  const { t, meta } = modele;
  const f = fiche.ecoles?.[t.uai[i]];
  const commune = meta.communes[t.commune[i]];
  if (!f) return vide('Fiche absente de cet export.');
  const rang = modele.visibles.indexOf(i);
  const s = modele.scores[i];
  const connues = modele.connues[i];
  return h(
    'article', { classe: 'fiche' },
    h('p', { classe: 'surtitre' }, `École ${TYPES_ECOLE[t.type[i]].toLowerCase()} · ${SECTEURS[t.secteur[i]].toLowerCase()}`),
    h('h2', {}, t.nom[i]),
    h('p', { classe: 'lieu' }, boutonCommune(ctx, commune.code), ` (${commune.dep})`, f.adresse && ` · ${f.adresse}`),
    blocContact(f.contact, ctx, {
      relais: fiche.commune.contact && [{
        cible: { type: 'commune', code: commune.code }, nom: `Mairie de ${commune.nom}`, motif: 'mairie', contact: fiche.commune.contact,
      }],
    }),
    h('div', { classe: 'heros' },
      anneau(s),
      h('div', {},
        h('b', {}, s === null ? 'Données insuffisantes' : 'Score global sur 100'),
        h('span', { classe: 'sous' },
          rang >= 0 && s !== null && `${nombre(rang + 1)}${rang === 0 ? 're' : 'e'} sur ${pluriel(modele.visibles.length, 'école filtrée', 'écoles filtrées')}`),
        h('span', { classe: 'sous' }, `${connues} jauges sur 5 · ${pourcent(100 * t.confiance[i])} des critères renseignés`))),
    blocRelance(t.uai[i], s),
    h('div', { classe: 'jauges' }, JAUGES.map((j) => jauge(j, i, f, fiche, ctx))),
    identite(i, f, ctx),
    blocAccueils(f, fiche, ctx),
    blocAssos(f, fiche, ctx),
    volet(ELUS, null, listeElus(fiche.commune, ctx, true), listeDispositifs(fiche.commune, ctx, f)),
    blocProducteurs(f, ctx),
    blocRelais(f, ctx),
    h('p', { classe: 'pied' }, h('button', { type: 'button', onclick: () => ctx.ouvrirCarnet([commune.code], commune.nom) }, 'Contacts de la commune')),
    tableSources(meta, f, (f.accueils ?? []).map((a) => fiche.accueils?.[a.id]),
      (f.assos ?? []).map((a) => fiche.assos?.[a.id]), fiche.commune.p, fiche.commune.pg, fiche.commune.dispositifs,
      fiche.commune.elus?.[0]),
  );
}

const ELUS = 'Élus et dispositifs';
const IDENTITE = 'Identité';
const PRODUCTEURS = 'Producteurs bio dans le rayon';

// ------------------------------------------------------------------ jauges
/** Un critère mène à ce qui l'explique : la fiche d'une instance, ou un bloc de cette fiche-ci. */
function destination(c: Critere, f: FicheEcole, fiche: Fiche): Cible | string {
  const commune: Cible = { type: 'commune', code: fiche.commune.code };
  switch (c.code) {
    case 'pat': {
      const d = fiche.commune.dispositifs?.find((x) => x.type === 'pat' && x.nom === c.detail);
      return d ? { type: 'pat', id: d.id } : ELUS;
    }
    case 'bio': case 'web': return commune;
    case 'cite_educative': return f.cite_id ? { type: 'acteur', nature: 'dispositif', id: f.cite_id } : IDENTITE;
    case 'soir': case 'mercredi': case 'gestionnaire': return LIBELLE_NATURE.accueil[1];
    case 'rattachee': case 'federee': case 'active': return LIBELLE_NATURE.asso[1];
    case 'plus_proche': case 'nombre': return PRODUCTEURS;
    case 'familles_iris': return f.iris ? { type: 'acteur', nature: 'iris', id: f.iris.code } : IDENTITE;
    case 'mixite': return f.qpv ? { type: 'acteur', nature: 'dispositif', id: f.qpv.id } : IDENTITE;
    default: return IDENTITE;
  }
}

function jauge(j: NomJauge, i: number, f: FicheEcole, fiche: Fiche, ctx: ContexteFiche): HTMLElement {
  const { modele, etat } = ctx;
  const v = modele.valeur(j, i);
  const total = JAUGES.reduce((x, k) => x + etat.poids[k], 0);
  const part = total ? Math.round((100 * etat.poids[j]) / total) : 0;
  const suivre = (c: Critere, depuis: Element): void => {
    const d = destination(c, f, fiche);
    if (typeof d === 'string') montrerBloc(depuis, d);
    else ctx.ouvrir(d);
  };
  const criteres = j === 'producteurs' ? criteresProducteurs(i, ctx) : f.jauges[j].criteres;
  return h(
    'details', { classe: 'jauge' },
    h('summary', {},
      h('span', { classe: 'nom' }, LIBELLE_JAUGE[j]),
      h('span', { classe: v === null ? 'valeur insuffisant' : 'valeur' }, v === null ? 'données insuffisantes' : nombre(v)),
      metre(v, LIBELLE_JAUGE[j], j)),
    h('ul', { classe: 'criteres' }, criteres.map((c) => h(
      'li', {}, h(
        'button', { type: 'button', onclick: (e: MouseEvent) => suivre(c, e.currentTarget as Element) },
        h('span', { classe: 'nom' }, LIBELLE_CRITERE[c.code] ?? c.code),
        h('span', { classe: 'valeur' }, c.valeur === undefined ? 'inconnu' : nombre(c.valeur)),
        h('span', { classe: 'sous' }, expliquer(c, ctx)),
      ),
    ))),
    h('p', { classe: 'note' }, `Pèse ${part} % du score.`),
  );
}

function criteresProducteurs(i: number, ctx: ContexteFiche): Critere[] {
  const { modele, etat } = ctx;
  const j = jaugeProducteurs(modele.t.prod[i], etat.rayon, modele.meta.producteurs);
  return [
    { code: 'plus_proche', valeur: j.plusProche ?? undefined, detail: j.minutes },
    { code: 'nombre', valeur: j.nombreNote ?? undefined, detail: j.nombre },
  ];
}

const themes = (l: unknown): string => (Array.isArray(l) ? l.map((x) => LIBELLE_THEME[String(x)] ?? x).join(', ') : '');

function expliquer(c: Critere, ctx: ContexteFiche): string {
  const { meta } = ctx.modele;
  const d = c.detail as never;
  const o = (d ?? {}) as Record<string, unknown>;
  const connu = c.valeur !== undefined;
  switch (c.code) {
    case 'pat': return d ? String(d) : 'aucun PAT ne couvre la commune';
    case 'bio': return d ? `${pourcent(Number(o.pct))} des achats en ${String(o.annee)}` : 'aucune déclaration';
    case 'web': {
      if (!d) return 'site de la mairie pas encore visité';
      const recents = themes(o.recents);
      const sansDate = themes(o.sans_date);
      return [
        recents && `moins de ${meta.seuils.web_mois} mois : ${recents}`, sansDate && `pages sans date : ${sansDate}`,
      ].filter(Boolean).join(' ; ') || 'aucun thème alimentaire trouvé';
    }
    case 'cite_educative': return d ? String(d) : 'non';
    case 'soir': return ({
      oui: 'annoncé par l’accueil', accueil_sans_horaire: 'accueil trouvé, horaires inconnus',
      oui_commune: 'annoncé sur le site de la mairie', non: 'pas d’accueil du soir',
    } as Record<string, string>)[String(d)] ?? `aucun accueil trouvé à moins de ${meta.seuils.accueil_m} m`;
    case 'mercredi': return ({
      oui: 'ouvert le mercredi', centre_de_loisirs: 'centre de loisirs : mercredi probable',
      oui_commune: 'annoncé sur le site de la mairie', non: 'fermé le mercredi',
    } as Record<string, string>)[String(d)] ?? 'ouverture inconnue';
    case 'gestionnaire':
      return !connu ? 'aucun accueil trouvé' : c.valeur ? 'identifié' : 'accueil trouvé, gestionnaire inconnu';
    case 'rattachee':
      return d ? `${pluriel(Number(d), 'association')}, meilleure confiance ${dixieme((c.valeur ?? 0) / 100)}`
        : 'aucune association trouvée';
    case 'federee': return Array.isArray(d) ? (d as string[]).join(', ') : 'aucune fédération connue';
    case 'active':
      return !connu ? 'dernière activité inconnue'
        : c.valeur ? `activité de moins de ${meta.seuils.parents_mois} mois` : 'pas d’activité récente';
    case 'plus_proche': return d === null || d === undefined ? 'aucun dans le rayon' : minutes(Number(d));
    case 'nombre': {
      const n = Number(d);
      return n >= meta.producteurs.nombre_plein ? `${n} ou plus` : pluriel(n, 'producteur');
    }
    case 'nb_eleves': return connu ? pluriel(Number(d), 'élève') : 'effectif inconnu';
    case 'familles_iris': return connu ? pluriel(Number(d), 'famille') : 'inconnu';
    case 'mixite': {
      if (!connu) return 'IPS non publié';
      const origine = String(o.ips_origine ?? '');
      return [
        `IPS ${dixieme(Number(o.ips))}${origine && origine !== 'ecole' ? ` (école voisine : ${origine})` : ''}`,
        o.qpv_m === null || o.qpv_m === undefined ? 'pas de QPV à moins de 2 km'
          : Number(o.qpv_m) === 0 ? 'dans un QPV' : `QPV à ${metres(Number(o.qpv_m))}`,
      ].join(', ');
    }
    default: return '';
  }
}

// ------------------------------------------------------------------ identité
function identite(i: number, f: FicheEcole, ctx: ContexteFiche): HTMLElement {
  const { t, meta } = ctx.modele;
  const eleves = t.eleves[i];
  const ips = t.ips[i];
  return bloc(
    IDENTITE,
    definition(
      ['UAI', t.uai[i]],
      ['Effectif', eleves === null ? 'inconnu'
        : `${pluriel(eleves, 'élève')}${f.classes ? `, ${pluriel(f.classes, 'classe')}` : ''}${f.rentree ? ` (rentrée ${f.rentree})` : ''}`],
      ['IPS', ips === null ? 'non publié' : `${dixieme(ips)}${f.ips_rentree ? ` (${f.ips_rentree})` : ''}`],
      ['Éducation prioritaire', EDUCATION_PRIORITAIRE[t.rep[i]] || 'non'],
      ['Cité éducative', f.cite ? boutonActeur(ctx, 'dispositif', f.cite_id, f.cite, false) : 'non'],
      ['Restauration', ouiNonInconnu(f.restauration)],
      f.qpv ? ['Quartier prioritaire', [boutonActeur(ctx, 'dispositif', f.qpv.id, f.qpv.nom, false), f.qpv.m === 0 ? ' (dedans)' : `, à ${metres(f.qpv.m)}`]] : null,
      f.iris && ['Quartier (IRIS)', h('span', {}, boutonActeur(ctx, 'iris', f.iris.code, f.iris.nom, false), h('span', { classe: 'sous' }, [
        f.iris.familles !== undefined && pluriel(f.iris.familles, 'famille avec enfants', 'familles avec enfants'),
        f.iris.revenu !== undefined && `revenu médian ${euros(f.iris.revenu)}`,
        f.iris.pauvrete !== undefined && `pauvreté ${pourcent(f.iris.pauvrete)}`,
      ].filter(Boolean).join(' · ')))],
    ),
    provenance(f.p, meta),
  );
}

// ------------------------------------------------------------------ acteurs liés
function blocAccueils(f: FicheEcole, fiche: Fiche, ctx: ContexteFiche): HTMLElement {
  const { meta } = ctx.modele;
  const lignes = (f.accueils ?? []).flatMap((l) => {
    const a = fiche.accueils?.[l.id];
    if (!a) return [];
    return [h(
      'li', {},
      boutonActeur(ctx, 'accueil', l.id, a.nom), ' ', etiquette(`${metres(l.m)} · ${MOTIF_RATTACHEMENT[l.motif] ?? l.motif}`),
      h('span', { classe: 'sous' }, `Soir : ${ouiNonInconnu(a.soir)} · mercredi : ${ouiNonInconnu(a.mercredi)}`,
        a.horaires && ` · ${a.horaires}`),
      h('span', { classe: 'sous' }, 'Gestionnaire : ', boutonActeur(ctx, 'gestionnaire', a.siren, a.gestionnaire ?? 'inconnu', false),
        a.gestionnaire_type && ` (${LIBELLE_GESTIONNAIRE[a.gestionnaire_type]})`),
      a.adresse && h('span', { classe: 'sous' }, a.adresse),
      provenance(a.p, meta),
    )];
  });
  return volet(
    LIBELLE_NATURE.accueil[1], lignes.length,
    lignes.length ? listeRepliee(lignes, 4)
      : vide('Aucun accueil trouvé à proximité. Les sources ouvertes ne sont pas exhaustives : l’école peut en avoir un.'),
  );
}

function blocAssos(f: FicheEcole, fiche: Fiche, ctx: ContexteFiche): HTMLElement {
  const { meta } = ctx.modele;
  const lignes = (f.assos ?? []).flatMap((l) => {
    const a = fiche.assos?.[l.id];
    if (!a) return [];
    return [h(
      'li', {},
      boutonActeur(ctx, 'asso', l.id, a.nom), ' ', etiquette(`rattachement ${pourcent(100 * l.c)}`),
      h('span', { classe: 'sous' }, [
        a.federation ?? 'sans fédération connue', a.creation && `créée le ${date(a.creation)}`,
        a.rna && `RNA ${a.rna}`,
      ].filter(Boolean).join(' · ')),
      a.siege && h('span', { classe: 'sous' }, `Siège : ${a.siege}`),
      h('span', { classe: 'sous' },
        a.activite ? ['Dernière activité en ligne : ', lien(a.activite_url, date(a.activite)) ?? date(a.activite)]
          : 'Dernière activité en ligne inconnue',
        a.site && [' · ', lien(a.site, 'site web')]),
      provenance(a.p, meta),
    )];
  });
  return volet(
    LIBELLE_NATURE.asso[1], lignes.length,
    lignes.length ? listeRepliee(lignes, 4)
      : vide('Aucune association rattachée. Beaucoup de conseils locaux ne sont pas déclarés en propre.'),
  );
}

// ------------------------------------------------------------------ producteurs et relais dans le rayon
function trajet(p: Proche): HTMLElement {
  return h('span', { classe: 'trajet' }, km(p.km), h('span', { classe: 'sous' }, minutes(p.minutes)));
}

function blocProducteurs(f: FicheEcole, ctx: ContexteFiche): HTMLElement {
  const { rayon } = ctx.etat;
  const dedans = proches(f.prod).filter((p) => dansRayon(p.km, p.minutes, rayon));
  const lignes = dedans.flatMap((p) => {
    const g = ctx.producteurs.features[p.rang];
    if (!g) return [];
    const x = g.properties;
    return [h(
      'li', { classe: 'proche' },
      h('span', {},
        boutonActeur(ctx, 'producteur', x.id, x.nom),
        h('span', { classe: 'sous' }, x.activites),
        !x.compte && h('span', { classe: 'sous' }, `Adresse : ${LIBELLE_ADRESSE[x.adresse_type]} — non compté dans la jauge`)),
      trajet(p),
    )];
  });
  const comptes = dedans.filter((p) => ctx.producteurs.features[p.rang]?.properties.compte).length;
  return volet(
    PRODUCTEURS, lignes.length,
    lignes.length
      ? [h('p', { classe: 'note' }, `${pluriel(comptes, 'producteur compté', 'producteurs comptés')}, du plus proche au plus loin. Trajets par la route.`),
        listeRepliee(lignes, 6)]
      : vide('Aucun producteur pris en compte dans ce rayon.'),
  );
}

function blocRelais(f: FicheEcole, ctx: ContexteFiche): HTMLElement {
  const { rayon } = ctx.etat;
  const parType = new Map<string, HTMLElement[]>();
  for (const p of proches(f.relais)) {
    const g = ctx.relais.features[p.rang];
    if (!g || !dansRayon(p.km, p.minutes, rayon)) continue;
    const x = g.properties;
    const l = parType.get(x.type) ?? [];
    l.push(h(
      'li', { classe: 'proche' },
      h('span', {},
        boutonActeur(ctx, 'relais', x.id, x.nom),
        x.adresse && h('span', { classe: 'sous' }, x.adresse)),
      trajet(p),
    ));
    parType.set(x.type, l);
  }
  const contenu: Enfant[] = [...parType].map(([type, l]) => [
    h('h4', {}, LIBELLE_RELAIS[type]), listeRepliee(l, 3),
  ]);
  return volet(
    'Relais locaux dans le rayon', [...parType.values()].reduce((x, l) => x + l.length, 0),
    contenu.length ? [h('p', { classe: 'note' }, 'Les dix plus proches de chaque type.'), contenu]
      : vide('Aucun relais dans ce rayon.'),
  );
}
