import type { Plugin } from 'vite';

interface Demande {
  method?: string;
  headers: Record<string, string | string[] | undefined>;
}

export function refus(req: Demande, uai: string): number | null;
export function lireBilan(sortie: string): { uai: string; visite: string; echecs: string[] };
export function serveurAnalyse(): Plugin;
