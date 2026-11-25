# Utiliser la carte

La carte aide à trouver les 5 à 15 écoles d'Île-de-France les plus favorables au projet V.i, en deux étapes :

1. **Communes** : repérer les communes où le projet a le plus de chances de prendre (PAT, cuisine centrale publique,
   producteurs bio proches, associations, soutien du département…).
2. **Écoles** : parmi les écoles de ces communes, choisir les plus engagées (périscolaire, parents, familles…).

Le détail des calculs est dans [METHODE.md](METHODE.md).

## Lancer la carte

Depuis le dossier du projet : `make carte` (ou, si les données sont déjà exportées, `cd web && npm run dev`), puis
ouvrir <http://localhost:5173/>.

## L'écran

| Zone | Contenu |
|---|---|
| Gauche | **Réglages** : étape, filtres, poids des critères, rayon des producteurs, couches de la carte |
| Centre | **Carte** : communes, écoles, acteurs ; un clic ouvre la fiche |
| Droite | **Classement** de l'étape en cours, ou la **fiche** ouverte (« ← Classement » pour revenir) |

Sur un petit écran, les trois zones deviennent des onglets en bas : Carte, Réglages, Classement.

## Étape 1 : classer les communes

Choisir **« 1. Communes »** en haut à gauche (c'est l'étape par défaut).

- **La carte** colore chaque commune selon son score : plus le vert est foncé, plus la commune est favorable.
  Une commune sans couleur n'a pas assez de données pour être notée.
- **Le classement** (à droite) liste les communes de la meilleure à la moins bonne. Les huit petites barres sont les
  huit critères (PAT, soutiens, cuisine, bio, producteurs, associations, communication, élèves) ; un trait pointillé
  veut dire « inconnu ». « 6/8 critères » indique combien de critères sont connus. Survoler une ligne affiche les valeurs.
- **Les poids** (« Poids des critères communaux », à gauche) règlent l'importance de chaque critère ; le classement
  et la carte se mettent à jour aussitôt. « Poids par défaut » revient au réglage d'origine.
- **Les filtres** : départements, et « Critères connus, au moins » pour écarter les communes trop peu documentées
  (une commune peu documentée peut sinon se retrouver en tête).
- **Cliquer sur une commune** (dans le classement ou sur la carte) ouvre sa fiche : détail du score, cantine et
  cuisine centrale, soutiens territoriaux, associations d'alimentation durable, élus, contact de la mairie, écoles.

### Retenir des communes

- Cocher la case à gauche d'une commune pour la retenir, ou utiliser **« Retenir les [10] premières »**.
- **« Voir leurs écoles → »** passe à l'étape 2. **« Effacer »** vide la sélection.
- **« Exporter en CSV »** télécharge le classement (colonne « retenue » comprise), lisible dans un tableur.

## Étape 2 : classer les écoles

Choisir **« 2. Écoles »** (ou « Voir leurs écoles → » depuis l'étape 1).

> **Seules les écoles des communes retenues sont affichées.** Avec une seule commune cochée, la carte ne montre que
> ses écoles : c'est voulu. Le rappel est en haut des filtres (« Écoles de N communes retenues à l'étape 1 ») ;
> le bouton **« Toutes les communes »** les remet toutes. Sans commune retenue, toutes les écoles sont classées.

- **Chaque école** est notée sur cinq jauges : engagement de la collectivité, périscolaire, parents, producteurs,
  familles. Le score est leur moyenne pondérée (« Poids du score », à gauche).
- **Filtres** : commune, secteur (public, privé sous contrat), type, nombre d'élèves, nombre minimal de jauges
  connues, seuil minimal par jauge.
- **« Seulement les [50] premières »** (au-dessus du classement) ne garde que le haut du classement, sur la carte aussi.
- **La fiche d'une école** détaille ses jauges, l'accueil périscolaire et l'association de parents rattachés, les
  producteurs bio dans le rayon (avec la durée du trajet), et le contact de l'école. Les flèches en haut de la fiche
  passent à l'école précédente ou suivante du classement.
- **« Exporter en CSV »** télécharge le classement des écoles.

## Réglages communs aux deux étapes

- **Rayon des producteurs** : un producteur bio compte s'il est à moins de 10 km **ou** 15 min de l'école par la
  route (réglage par défaut, distance annoncée par V.i). Changer le rayon recalcule la jauge Producteurs des écoles et
  le critère Producteurs des communes.
- **Couches de la carte** : couleur des écoles (score ou une jauge), points à afficher (accueils périscolaires,
  associations de parents, producteurs bio, relais locaux), zones (communes, PAT, cités éducatives, quartiers
  prioritaires, IRIS) ; « Voir un PAT » ouvre la fiche d'un projet alimentaire territorial.
- **Méthode et sources** (en haut) : d'où vient chaque donnée, sa date, et le taux de remplissage par département.

## Lire les notes

- Toutes les notes vont de 0 à 100.
- **« Inconnu » n'est jamais compté 0** : un critère sans donnée sort de la moyenne. En dessous de la moitié des
  poids connus, la note devient « données insuffisantes ».
- Chaque information de la fiche porte sa source et sa date (lien sous l'information).

## Partager une vue

L'adresse de la page garde tout : étape, poids, rayon, filtres, communes retenues, fiche ouverte. Copier l'adresse
et l'envoyer suffit pour que quelqu'un retrouve exactement la même vue.

## Mettre à jour les données

| Besoin | Commande |
|---|---|
| Tout recollecter puis recalculer | `make collecte` puis `uv run vi exporter` |
| Après un changement de poids par défaut (`config/jauges.yaml`) | `uv run vi jauges && uv run vi exporter` |
| Après une correction du référentiel (`config/referentiel/*.csv`) | `uv run vi collecter referentiel_vi`, puis `uv run vi jauges && uv run vi exporter` |
