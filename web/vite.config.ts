import { defineConfig } from 'vite';

export default defineConfig({
  base: './', // le dossier dist/ peut être déposé n'importe où
  worker: { format: 'es' },
  optimizeDeps: { exclude: ['maplibre-gl'] }, // son worker est un module voisin, à ne pas déplacer
  build: { target: 'es2022', chunkSizeWarningLimit: 1500 },
});
