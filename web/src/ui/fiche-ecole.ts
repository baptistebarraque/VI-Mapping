/** Fiche d'une école : identité, jauges, acteurs liés, producteurs et relais dans le rayon, sources. */

import type { Etat } from '../etat';
import { dansRayon, jaugeProducteurs } from '../jauges';
import type { Modele } from '../modele';
import {
  EDUCATION_PRIORITAIRE, JAUGES, SECTEURS, TYPES_ECOLE,
  type CollectionPoints, type Critere, type Dispositif, type Fiche, type FicheEcole, type NomJauge, type ProprietesProducteur,
  type ProprietesRelais,
} from '../types';
import { bloc, definition, etiquette, listeRepliee, metre, provenance, tableSources, vide } from './commun';
import { h, lien, type Enfant } from './dom';
import {
  date, dixieme, euros, km, LIBELLE_ADRESSE, LIBELLE_CRITERE, LIBELLE_GESTIONNAIRE, LIBELLE_JAUGE, LIBELLE_RELAIS,
  LIBELLE_THEME, metres, minutes, nombre, ouiNonInconnu, pluriel, pourcent,
} from './format';
import { boutonPat, listeDispositifs, listeElus } from './fiche-commune';
import { blocRelance } from './relance';

export interface ContexteFiche {
  modele: Modele;
  etat: Etat;
  producteurs: CollectionPoints<ProprietesProducteur>;
  relais: CollectionPoints<ProprietesRelais>;
  ouvrirCommune: (code: string) => void;
  ouvrirEcole: (i: number) => void;
  ouvrirPat: (id: string) => void;
  voir: (xy: [number, number]) => void;
}

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
    h('p', { classe: 'lieu' },
      h('button', { type: 'button', classe: 'lien', onclick: () => ctx.ouvrirCommune(commune.code) }, commune.nom),
      ` (${commune.dep})`, f.adresse && ` · ${f.adresse}`),
    h('div', { classe: 'heros' },
      h('span', { classe: 'chiffre' }, s === null ? '–' : nombre(s)),
      h('div', {},
        h('b', {}, s === null ? 'Données insuffisantes' : 'Score global sur 100'),
        h('span', { classe: 'sous' },
          rang >= 0 && s !== null && `${nombre(rang + 1)}${rang === 0 ? 're' : 'e'} sur ${pluriel(modele.visibles.length, 'école filtrée', 'écoles filtrées')} · `,
          `${connues} jauges connues sur 5`),
        h('span', { classe: 'sous' }, `${pourcent(100 * t.confiance[i])} des critères renseignés`))),
    blocRelance(t.uai[i], s),
    h('div', { classe: 'jauges' }, JAUGES.map((j) => jauge(j, i, f, fiche, ctx))),
    identite(i, f, ctx),
    blocAccueils(f, fiche, ctx),
    blocAssos(f, fiche, ctx),
    bloc('Élus et dispositifs', listeElus(fiche.commune, meta, true), listeDispositifs(fiche.commune, ctx, f)),
    blocProducteurs(f, ctx),
    blocRelais(f, ctx),
    tableSources(meta, f, (f.accueils ?? []).map((a) => fiche.accueils?.[a.id]),
      (f.assos ?? []).map((a) => fiche.assos?.[a.id]), fiche.commune.p, fiche.commune.pg, fiche.commune.dispositifs,
      fiche.commune.elus?.[0]),
  );
}

// ------------------------------------------------------------------ jauges
function jauge(j: NomJauge, i: number, f: FicheEcole, fiche: Fiche, ctx: ContexteFiche): HTMLElement {
  const { modele, etat } = ctx;
  const v = modele.valeur(j, i);
  const total = JAUGES.reduce((x, k) => x + etat.poids[k], 0);
  const part = total ? Math.round((100 * etat.poids[j]) / total) : 0;
  const pat = (c: Critere): Dispositif | undefined => c.code !== 'pat' ? undefined
    : fiche.commune.dispositifs?.find((d) => d.type === 'pat' && d.nom === c.detail);
  const explication = (c: Critere): Enfant => {
    const d = pat(c);
    return d ? boutonPat(d, d.nom, ctx) : expliquer(c, ctx);
  };
  const criteres = j === 'producteurs' ? criteresProducteurs(i, ctx) : f.jauges[j].criteres;
  return h(
    'details', { classe: 'jauge' },
    h('summary', {},
      h('span', { classe: 'nom' }, LIBELLE_JAUGE[j]),
      h('span', { classe: v === null ? 'valeur insuffisant' : 'valeur' }, v === null ? 'données insuffisantes' : nombre(v)),
      metre(v, LIBELLE_JAUGE[j])),
    h('ul', { classe: 'criteres' }, criteres.map((c) => h(
      'li', {},
      h('span', { classe: 'nom' }, LIBELLE_CRITERE[c.code] ?? c.code),
      h('span', { classe: 'valeur' }, c.valeur === undefined ? 'inconnu' : nombre(c.valeur)),
      h('span', { classe: 'sous' }, explication(c)),
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
    'Identité',
    definition(
      ['UAI', t.uai[i]],
      ['Effectif', eleves === null ? 'inconnu'
        : `${pluriel(eleves, 'élève')}${f.classes ? `, ${pluriel(f.classes, 'classe')}` : ''}${f.rentree ? ` (rentrée ${f.rentree})` : ''}`],
      ['IPS', ips === null ? 'non publié' : `${dixieme(ips)}${f.ips_rentree ? ` (${f.ips_rentree})` : ''}`],
      ['Éducation prioritaire', EDUCATION_PRIORITAIRE[t.rep[i]] || 'non'],
      ['Cité éducative', f.cite ?? 'non'],
      ['Restauration', ouiNonInconnu(f.restauration)],
      f.qpv ? ['Quartier prioritaire', f.qpv.m === 0 ? `dans ${f.qpv.nom}` : `${f.qpv.nom}, à ${metres(f.qpv.m)}`] : null,
      f.iris && ['Quartier (IRIS)', h('span', {}, f.iris.nom, h('span', { classe: 'sous' }, [
        f.iris.familles !== undefined && pluriel(f.iris.familles, 'famille avec enfants', 'familles avec enfants'),
        f.iris.revenu !== undefined && `revenu médian ${euros(f.iris.revenu)}`,
        f.iris.pauvrete !== undefined && `pauvreté ${pourcent(f.iris.pauvrete)}`,
      ].filter(Boolean).join(' · ')))],
    ),
    provenance(f.p, meta),
  );
}

// ------------------------------------------------------------------ acteurs liés
const MOTIF: Record<string, string> = { adresse: 'même adresse', distance: 'à proximité', nom: 'nom proche' };

const boutonVoir = (xy: [number, number] | undefined, ctx: ContexteFiche): HTMLElement | null =>
  xy ? h('button', { type: 'button', classe: 'lien', onclick: () => ctx.voir(xy) }, 'voir sur la carte') : null;

function blocAccueils(f: FicheEcole, fiche: Fiche, ctx: ContexteFiche): HTMLElement {
  const { meta } = ctx.modele;
  const lignes = (f.accueils ?? []).flatMap((l) => {
    const a = fiche.accueils?.[l.id];
    if (!a) return [];
    return [h(
      'li', {},
      h('b', {}, a.nom), ' ', etiquette(`${metres(l.m)} · ${MOTIF[l.motif] ?? l.motif}`),
      h('span', { classe: 'sous' }, `Soir : ${ouiNonInconnu(a.soir)} · mercredi : ${ouiNonInconnu(a.mercredi)}`,
        a.horaires && ` · ${a.horaires}`),
      h('span', { classe: 'sous' }, 'Gestionnaire : ', a.gestionnaire ?? 'inconnu',
        a.gestionnaire_type && ` (${LIBELLE_GESTIONNAIRE[a.gestionnaire_type]})`),
      a.adresse && h('span', { classe: 'sous' }, a.adresse, ' ', boutonVoir(a.xy, ctx)),
      provenance(a.p, meta),
    )];
  });
  return bloc(
    'Accueils périscolaires',
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
      h('b', {}, a.nom), ' ', etiquette(`rattachement ${pourcent(100 * l.c)}`),
      h('span', { classe: 'sous' }, [
        a.federation ?? 'sans fédération connue', a.creation && `créée le ${date(a.creation)}`,
        a.rna && `RNA ${a.rna}`,
      ].filter(Boolean).join(' · ')),
      a.siege && h('span', { classe: 'sous' }, `Siège : ${a.siege} `, boutonVoir(a.xy, ctx)),
      h('span', { classe: 'sous' },
        a.activite ? ['Dernière activité en ligne : ', lien(a.activite_url, date(a.activite)) ?? date(a.activite)]
          : 'Dernière activité en ligne inconnue',
        a.site && [' · ', lien(a.site, 'site web')]),
      provenance(a.p, meta),
    )];
  });
  return bloc(
    'Associations de parents',
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
    const xy = g.geometry.coordinates as [number, number];
    return [h(
      'li', { classe: 'proche' },
      h('span', {},
        h('button', { type: 'button', classe: 'lien fort', onclick: () => ctx.voir(xy) }, x.nom),
        h('span', { classe: 'sous' }, x.activites),
        !x.compte && h('span', { classe: 'sous' }, `Adresse : ${LIBELLE_ADRESSE[x.adresse_type]} — non compté dans la jauge`)),
      trajet(p),
    )];
  });
  const comptes = dedans.filter((p) => ctx.producteurs.features[p.rang]?.properties.compte).length;
  return bloc(
    'Producteurs bio dans le rayon',
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
    const xy = g.geometry.coordinates as [number, number];
    const l = parType.get(x.type) ?? [];
    l.push(h(
      'li', { classe: 'proche' },
      h('span', {},
        h('button', { type: 'button', classe: 'lien fort', onclick: () => ctx.voir(xy) }, x.nom),
        x.adresse && h('span', { classe: 'sous' }, x.adresse)),
      trajet(p),
    ));
    parType.set(x.type, l);
  }
  const contenu: Enfant[] = [...parType].map(([type, l]) => [
    h('h4', {}, LIBELLE_RELAIS[type]), listeRepliee(l, 3),
  ]);
  return bloc(
    'Relais locaux dans le rayon',
    contenu.length ? [h('p', { classe: 'note' }, 'Les dix plus proches de chaque type.'), contenu]
      : vide('Aucun relais dans ce rayon.'),
  );
}
