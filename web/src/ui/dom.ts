/** Construction du DOM. Tout texte passe par des nœuds texte : jamais d'innerHTML avec des données. */

export type Enfant = Node | string | number | null | undefined | false | Enfant[];
type Valeur = string | number | boolean | null | undefined | ((e: never) => void);
export type Proprietes = Record<string, Valeur>;

function ajouter(parent: Node, enfants: Enfant[]): void {
  for (const e of enfants) {
    if (e === null || e === undefined || e === false) continue;
    if (Array.isArray(e)) ajouter(parent, e);
    else parent.appendChild(e instanceof Node ? e : document.createTextNode(String(e)));
  }
}

function poser(el: Element, proprietes: Proprietes): void {
  for (const [cle, v] of Object.entries(proprietes)) {
    if (v === null || v === undefined || v === false) continue;
    if (typeof v === 'function') el.addEventListener(cle.replace(/^on/, '').toLowerCase(), v as EventListener);
    else if (cle === 'value' || cle === 'checked') (el as HTMLInputElement)[cle as 'value'] = v as string;
    else el.setAttribute(cle === 'classe' ? 'class' : cle, v === true ? '' : String(v));
  }
}

export function h<K extends keyof HTMLElementTagNameMap>(
  nom: K,
  proprietes: Proprietes = {},
  ...enfants: Enfant[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(nom);
  ajouter(el, enfants);
  poser(el, proprietes);
  return el;
}

export function svg(nom: string, attributs: Record<string, string | number>, ...enfants: Node[]): SVGElement {
  const el = document.createElementNS('http://www.w3.org/2000/svg', nom);
  for (const [k, v] of Object.entries(attributs)) el.setAttribute(k, String(v));
  el.append(...enfants);
  return el;
}

/** Lien externe ; null si l'adresse n'est pas en http(s) (données ouvertes : on ne suppose rien). */
export function lien(url: string | undefined, ...contenu: Enfant[]): HTMLAnchorElement | null {
  if (!url || !/^https?:\/\//i.test(url)) return null;
  return h('a', { href: url, target: '_blank', rel: 'noopener noreferrer' }, ...contenu);
}

export function remplacer(el: Element, ...enfants: Enfant[]): void {
  el.replaceChildren();
  ajouter(el, enfants);
}

let compteur = 0;
export const identifiant = (prefixe: string): string => `${prefixe}-${++compteur}`;
