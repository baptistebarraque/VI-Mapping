/** Bouton « Relancer l'analyse » d'une école : la carte locale recollecte et recalcule, puis se recharge. */

import { h } from './dom';
import { nombre } from './format';

interface Bilan {
  uai: string;
  visite: string;
  echecs: string[];
}
interface Trace extends Bilan {
  avant: number | null;
}

const CLE = 'vi-relance';
const VISITE: Record<string, string> = {
  faite: 'site de la mairie revisité',
  recente: 'site de la mairie déjà vu il y a moins de 25 jours',
  plafond: 'site de la mairie non visité : quota du mois atteint (VI_CONTACT absent)',
  sans_site: 'aucun site de mairie connu',
  echec: 'visite du site de la mairie en échec',
};
const ETAPE: Record<string, string> = {
  sites_mairies: 'site de la mairie', rattachements: 'rattachements', osrm: 'distances', jauges: 'jauges',
};

/** École en cours d'analyse : la fiche peut être redessinée entre-temps. */
let enCours: string | null = null;
/** Met à jour le bouton de la fiche affichée, qui n'est plus forcément celle d'où l'analyse est partie. */
let rafraichir = (): void => {};
let erreur: { uai: string; texte: string } | null = null;

function trace(uai: string): Trace | null {
  try {
    const t = JSON.parse(sessionStorage.getItem(CLE) ?? 'null') as Trace | null;
    return t?.uai === uai ? t : null;
  } catch {
    return null;
  }
}

const points = (x: number | null): string => (x === null ? 'données insuffisantes' : nombre(x));

function compteRendu(t: Trace, score: number | null): string {
  const avant = points(t.avant);
  const apres = points(score);
  return [
    `Analyse refaite. Score ${avant === apres ? `inchangé (${apres})` : `: ${avant} → ${apres}`}`,
    VISITE[t.visite] ?? t.visite,
    t.echecs.length > 0 && `étapes en échec : ${t.echecs.map((e) => ETAPE[e] ?? e).join(', ')}`,
  ].filter(Boolean).join(' ; ');
}

async function demander(uai: string): Promise<Bilan> {
  const r = await fetch(`${import.meta.env.BASE_URL}api/analyse/${uai}`, {
    method: 'POST', headers: { 'X-VI-Analyse': '1' },
  });
  const corps = (await r.json()) as Bilan & { erreur?: string };
  if (!r.ok) throw new Error(corps.erreur ?? `HTTP ${r.status}`);
  return corps;
}

export function blocRelance(uai: string, score: number | null): HTMLElement {
  const etat = h('p', { classe: 'note', role: 'status' });
  const bouton = h('button', { type: 'button', onclick: () => void lancer() }, 'Relancer l’analyse');
  const t = trace(uai);

  function afficher(): void {
    bouton.disabled = enCours !== null;
    if (enCours === uai) etat.textContent = 'Analyse en cours, une minute environ. La carte se rechargera.';
    else if (enCours !== null) etat.textContent = 'L’analyse d’une autre école est en cours.';
    else if (erreur?.uai === uai) etat.textContent = erreur.texte;
    else etat.textContent = t ? compteRendu(t, score) : '';
  }

  async function lancer(): Promise<void> {
    enCours = uai;
    erreur = null;
    afficher();
    try {
      const bilan = await demander(uai);
      sessionStorage.setItem(CLE, JSON.stringify({ ...bilan, avant: score } satisfies Trace));
      location.reload();
    } catch (e) {
      erreur = { uai, texte: e instanceof Error ? e.message : String(e) };
      enCours = null;
      rafraichir();
    }
  }

  rafraichir = afficher;
  afficher();
  return h('div', { classe: 'relance' }, bouton, etat);
}
