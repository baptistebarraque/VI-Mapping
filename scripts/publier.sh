#!/usr/bin/env bash
# Met la carte en ligne sur Cloudflare Pages, derrière Cloudflare Access.
#
# Refuse de déposer quoi que ce soit si l'adresse du site n'est pas déjà protégée
# par Access : la carte contient des contacts, elle ne doit jamais être publique,
# même une minute. Voir docs/PUBLIER.md.
set -euo pipefail

PROJET="${PROJET:-vi-mapping}"
DOMAINE="${DOMAINE:-$PROJET.pages.dev}"
WRANGLER="npx --yes wrangler@4"
cd "$(dirname "$0")/../web"

protege() {
  # Access répond par une redirection vers sa page de connexion (*.cloudflareaccess.com).
  curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "$1" | grep -Eq '^30[0-9] https://[^/]*cloudflareaccess\.com/'
}

if ! protege "https://$DOMAINE/"; then
  echo "Arrêt : https://$DOMAINE/ n'est pas protégé par Cloudflare Access." >&2
  echo "Créer d'abord l'application Access (docs/PUBLIER.md, étape 3), puis relancer." >&2
  exit 1
fi

test -f public/donnees/meta.json || { echo "Arrêt : pas de données, lancer « uv run vi exporter »." >&2; exit 1; }
npm run build
# --force : dépôt sur Cloudflare Pages lui-même. Sans lui, Wrangler 4.16x convertit le projet en Worker
# (modifie package.json et vite.config.ts) et le publie sur une adresse workers.dev, hors de la protection Access.
$WRANGLER pages deploy dist --project-name "$PROJET" --branch main --commit-dirty=true --force

# Contrôle après coup : le site et ses données doivent toujours demander la connexion.
for chemin in "" donnees/meta.json donnees/contacts.json; do
  if ! protege "https://$DOMAINE/$chemin"; then
    echo "ALERTE : https://$DOMAINE/$chemin est accessible sans connexion. Vérifier Access tout de suite." >&2
    exit 1
  fi
done
echo "En ligne et protégé : https://$DOMAINE/"
