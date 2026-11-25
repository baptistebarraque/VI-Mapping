/**
 * Serveur de développement : POST /api/analyse/<UAI> lance « vi analyser <UAI> », une analyse à la fois.
 * Absent du site construit (web/dist), qui est statique.
 */

import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const CHEMIN = '/api/analyse/';
const RACINE = fileURLToPath(new URL('../..', import.meta.url));
const DELAI_MAX_MS = 10 * 60 * 1000;

/** Refus éventuel d'une demande. L'en-tête maison et l'origine empêchent un autre site de la déclencher. */
export function refus(req, uai) {
  if (req.method !== 'POST') return 405;
  if (req.headers['x-vi-analyse'] !== '1') return 403;
  const { origin, host } = req.headers;
  if (origin !== `http://${host}` && origin !== `https://${host}`) return 403;
  return /^\d{7}[A-Z]$/.test(uai) ? null : 400;
}

/** Bilan : dernière ligne de la sortie de « vi analyser ». */
export function lireBilan(sortie) {
  return JSON.parse(sortie.trim().split('\n').at(-1));
}

export function serveurAnalyse() {
  let enCours = false;
  return {
    name: 'vi-analyse',
    apply: 'serve',
    configureServer(serveur) {
      serveur.middlewares.use((req, res, suite) => {
        const chemin = (req.url ?? '').split('?')[0];
        if (!chemin.startsWith(CHEMIN)) return suite();
        const repondre = (statut, corps) => {
          res.statusCode = statut;
          res.setHeader('Content-Type', 'application/json; charset=utf-8');
          res.end(JSON.stringify(corps));
        };
        const uai = chemin.slice(CHEMIN.length);
        const code = refus(req, uai);
        if (code !== null) return repondre(code, { erreur: 'Demande refusée.' });
        if (enCours) return repondre(409, { erreur: 'Une analyse est déjà en cours.' });
        enCours = true;
        execFile('uv', ['run', 'vi', 'analyser', uai], { cwd: RACINE, timeout: DELAI_MAX_MS }, (e, sortie, erreurs) => {
          enCours = false;
          if (e) {
            serveur.config.logger.error(`vi analyser ${uai} :\n${sortie}\n${erreurs}`);
            return repondre(500, { erreur: 'L’analyse a échoué : voir le terminal où la carte est lancée.' });
          }
          try {
            repondre(200, lireBilan(sortie));
          } catch {
            repondre(500, { erreur: 'Bilan illisible.' });
          }
        });
      });
    },
  };
}
