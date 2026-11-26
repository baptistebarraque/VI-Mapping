# Mettre la carte en ligne

La carte est un site statique : `web/dist`, environ 80 Mo et 1 300 fichiers. Elle contient les contacts collectés,
dont des adresses nominatives : elle ne doit jamais être publique. Elle est donc déposée sur **Cloudflare Pages**,
derrière **Cloudflare Access**. Les deux sont gratuits (Access : jusqu'à 50 personnes).

Pour la personne qui consulte : elle ouvre le lien, tape son adresse e-mail, reçoit un code à 6 chiffres et le
saisit. Pas de compte, pas de mot de passe. Seules les adresses autorisées reçoivent un code.

En ligne, tout fonctionne (filtres, fiches, contacts, exports CSV), sauf « Relancer l'analyse », qui demande la
base locale : le bouton n'y est pas affiché.

## Première mise en ligne

L'ordre compte : la protection est posée **avant** le premier dépôt. `scripts/publier.sh` refuse de déposer quoi
que ce soit tant que l'adresse ne demande pas de connexion.

### 1. Compte Cloudflare

Créer un compte sur [cloudflare.com](https://dash.cloudflare.com/sign-up) (offre gratuite).

### 2. Réserver l'adresse du site

```bash
npx --yes wrangler@4 login
```

```bash
npx --yes wrangler@4 pages project create vi-mapping --production-branch main
```

À lancer depuis la racine du dépôt, **pas depuis `web/`** : là, Wrangler 4.16x reconnaît un projet Vite, le
convertit en Worker et le publie sans protection sur une adresse `workers.dev`. `scripts/publier.sh` passe `--force`
pour la même raison.

La première commande ouvre le navigateur pour autoriser Wrangler (l'outil de Cloudflare). La seconde crée un projet
vide et affiche son adresse, normalement `vi-mapping.pages.dev`. Si Cloudflare en donne une autre (nom déjà pris),
la noter : elle servira aux étapes 3 et 4.

### 3. Protéger l'adresse avec Access

Dans le tableau de bord Cloudflare :

1. **Zero Trust**. La première fois : choisir un nom d'équipe (il apparaît sur la page de connexion, par exemple
   `vraiment-irresistibles`) et l'offre **Free**. Cloudflare peut demander un moyen de paiement même pour l'offre
   gratuite à 0 €.
2. **Access → Applications → Add an application → Self-hosted**.
3. Nom : `Carte V.i`. Durée de session : 24 h (ou plus).
4. Domaines : ajouter `vi-mapping.pages.dev`, puis une seconde ligne `*.vi-mapping.pages.dev` (les adresses de
   chaque dépôt).
5. Règle (policy) : nom `Équipe et cliente`, action **Allow**, **Include → Emails** : les adresses autorisées. Pour
   tout un domaine : **Emails ending in** `@exemple.fr`.
6. Méthode de connexion : décocher « Accept all available identity providers », choisir **One-time PIN** (code par
   e-mail) seul ; « Instant Auth » s'active alors. S'il n'apparaît pas dans la liste, l'ajouter d'abord dans
   **Integrations → Identity providers → Add an identity provider → One-time PIN** : sur un compte neuf, seul
   « Cloudflare » (connexion avec un compte Cloudflare) existe, et la cliente ne pourrait pas entrer.
7. Enregistrer.

Vérifier : ouvrir `https://vi-mapping.pages.dev` dans une fenêtre de navigation privée doit afficher la page de
connexion Cloudflare.

> Le réglage « Enable access policy » de la page du projet Pages ne protège que les dépôts de prévisualisation, pas
> l'adresse principale : il ne suffit pas.

### 4. Déposer la carte

```bash
make publier
```

La commande exporte les données, vérifie la protection, construit le site, le dépose, puis vérifie que le site et
`donnees/contacts.json` demandent toujours la connexion. Adresse différente de `vi-mapping.pages.dev` :

```bash
make publier PROJET=vi-mapping DOMAINE=autre-nom.pages.dev
```

Sans base locale, avec des données déjà présentes dans `web/public/donnees` : `./scripts/publier.sh`.

### 5. Envoyer le lien

`https://vi-mapping.pages.dev`. Un lien vers une vue précise marche aussi : l'adresse de la page garde l'étape, les
filtres et la fiche ouverte.

## Ensuite

| Besoin | Où |
|---|---|
| Mettre à jour la carte après une collecte | `make publier` |
| Ajouter ou retirer une personne | Zero Trust → Access → Applications → Carte V.i → Policies |
| Voir qui s'est connecté | Zero Trust → Logs → Access |
| Couper l'accès à tout le monde | supprimer la règle, ou le projet Pages |

Le site n'est jamais indexé par les moteurs de recherche (`robots.txt` et en-tête `X-Robots-Tag`), en plus de la
connexion.
