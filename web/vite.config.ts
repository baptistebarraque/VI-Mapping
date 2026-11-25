import { defineConfig } from 'vite';

import { serveurAnalyse } from './serveur/analyse.mjs';

export default defineConfig({
  base: './', // le dossier dist/ peut être déposé n'importe où
  plugins: [serveurAnalyse()],
  worker: { format: 'es' },
  optimizeDeps: { exclude: ['maplibre-gl'] }, // son worker est un module voisin, à ne pas déplacer
  build: { target: 'es2022', chunkSizeWarningLimit: 1500 },
});
