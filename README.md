# VI-Mapping

Cartographie des parties prenantes de l'éducation alimentaire en Île-de-France : collectivités, écoles et périscolaire,
associations de parents d'élèves, producteurs bio locaux. Une carte interactive note chaque école sur cinq jauges et
aide à repérer les communautés scolaires les plus favorables.

- **Périmètre** : départements 75, 77, 78, 91, 92, 93, 94, 95. Écoles du premier degré, publiques et privées sous contrat.
- **Open data d'abord** : API, puis scraping là où c'est permis ; un petit référentiel relevé à la main
  (`config/referentiel/`) quand aucun jeu ouvert n'existe, avec sa source à chaque ligne.
- **Chaque ligne** porte sa source, son adresse web, sa méthode, sa date de collecte et une confiance de 0 à 1.

| Document | Contenu |
|---|---|
| [docs/UTILISATION.md](docs/UTILISATION.md) | utiliser la carte : étape communes, puis écoles |
| [docs/SOURCES.md](docs/SOURCES.md) | sources, licences, règles du robot, sources verrouillées |
| [docs/METHODE.md](docs/METHODE.md) | rattachements, jauges, limites connues |
| [docs/rapport_couverture.md](docs/rapport_couverture.md) | taux de remplissage par champ et par département |

## Installer

Il faut [uv](https://docs.astral.sh/uv/), Node 22 ou plus, et PostgreSQL 16 ou plus avec PostGIS.

```bash
docker compose up -d          # base prête à l'emploi, ou DATABASE_URL vers la vôtre
cp .env.example .env          # VI_CONTACT : adresse montrée par le robot
make installer
make base
```

## Reprendre sans tout recollecter

La base et la carte déjà calculées sont publiées dans les Releases du dépôt.

```bash
make voir                     # seulement regarder la carte : Node suffit, ni base ni Python
make donnees                  # reprendre le projet : recharge la base (vide) et les données de la carte
```

L'archive de la base omet le cache de géocodage et les messages d'erreur. Pour publier une nouvelle version :
`make archives`, puis `gh release create donnees-AAAA-MM-JJ data/base.zip data/carte.zip`. Licence des données : celle de
chaque source (voir docs/SOURCES.md), Licence Ouverte 2.0 et ODbL pour OpenStreetMap.

## Utiliser

```bash
make collecte                 # toutes les sources, puis rattachements, distances et jauges
make verifier                 # contrôles : données personnelles, périmètre, cohérence
make carte                    # exporte les données et ouvre la carte en local
make site                     # carte prête à déposer sur un serveur web, dans web/dist
```

Compter 1 Go de téléchargements, 5 Go de base, un quart d'heure hors scraping (distances par la route comprises), et
environ deux heures pour visiter tous les sites de mairies, à 2 secondes par page. Les fichiers inchangés ne sont pas
téléchargés à nouveau, les sites vus depuis moins de 25 jours pas visités à nouveau.

| Commande | Rôle |
|---|---|
| `uv run vi sources` | sources, statut, dernière collecte |
| `uv run vi collecter CODE…` | une ou plusieurs sources, puis les calculs (`--sans-calcul` pour s'en passer) |
| `uv run vi collecter --dus` | sources arrivées à échéance |
| `uv run vi maj` | mise à jour planifiée : échéances, calculs, contrôles, rapport, export |
| `uv run vi analyser UAI` | une école : site de sa mairie, calculs, export ; c'est le bouton « Relancer l'analyse » de la carte locale |
| `uv run vi rattacher`, `proximite`, `jauges` | un seul calcul |
| `uv run vi couverture` | rapport de couverture |
| `uv run vi exporter` | fichiers JSON de la carte |

Tout est idempotent : relancer une commande ne duplique rien. Une collecte tient dans une transaction ; si une source
perd d'un coup plus de la moitié de ses lignes, elle est refusée (`--forcer` pour l'accepter).

## Planifier

`vi maj` ne collecte que les sources arrivées à échéance : chaque mois pour le scraping, chaque année pour l'open data.
Lancé chaque semaine, il reprend aussi ce qui a échoué. Si un contrôle échoue, la carte garde son dernier export valable.

- cron : [planification/crontab.exemple](planification/crontab.exemple)
- systemd : [planification/vi-maj.service](planification/vi-maj.service), [planification/vi-maj.timer](planification/vi-maj.timer)

## Régler

| Fichier | Contenu |
|---|---|
| [config/idf.yaml](config/idf.yaml) | périmètre, filtre des producteurs, rattachements, règles du robot |
| [config/jauges.yaml](config/jauges.yaml) | poids, sous-poids, seuils et rayon des jauges |
| [config/sources.yaml](config/sources.yaml) | registre des sources et verrous |
| [config/referentiel/](config/referentiel/) | référentiel V.i relevé à la main : PAT DRIAAF, soutiens, lauréats MGP, syndicats |

Après un changement dans `config/jauges.yaml` : `uv run vi jauges && uv run vi exporter`.

Après un changement dans `config/referentiel/` : `uv run vi collecter referentiel_vi`.

## Organisation

```
sql/                    schéma PostgreSQL + PostGIS, appliqué par « vi migrer »
src/vi_mapping/
  sources/              un module par source open data ou API
  scrapers/             un module par famille de sites, et le robot
  calculs/              rattachements, proximité, formules et jauges
  couverture/           rapport de couverture
  export/               fichiers de la carte
web/                    carte (TypeScript, MapLibre GL, Vite)
planification/          cron, systemd
tests/  web/tests/      pytest et vitest ; tests/vecteurs est commun aux deux
```

Ajouter une source : la déclarer dans `config/sources.yaml`, créer un module dans `sources/` avec
`@connecteur("code")`, puis `uv run vi migrer`.

## Vérifier

```bash
make controles                # ruff, pytest, tsc, vitest
```

Les tests de base créent une base temporaire sur le serveur de `DATABASE_URL`, et sont sautés s'il n'est pas joignable.
