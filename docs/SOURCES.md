# Sources

Produit depuis `config/sources.yaml` par `uv run vi sources --markdown > docs/SOURCES.md`.

Open data et API d'abord, scraping ensuite, et seulement là où robots.txt et les conditions d'utilisation le
permettent. Seule exception : le référentiel V.i (`config/referentiel/`), faits publics relevés à la main avec leur
source à chaque ligne, quand aucun jeu ouvert ne les donne. Chaque ligne en base porte `source`, `url`, `methode`,
`collecte_le` et `confiance`.

## Règles du robot

- **Identifié** : nom, version et contact (`VI_CONTACT`) dans le user-agent. Sans contact, un échantillon par mois.
- **robots.txt** lu avant chaque site. Illisible (401, 403, 429, 5xx) : le site n'est pas visité.
- **Réserve de fouille** (TDM : en-tête, balise, `tdmrep.json`) respectée.
- **Cadence** : un délai entre deux pages d'un même site, allongé si robots.txt le demande. Nombre de pages plafonné.
- **Anti-robot, captcha, refus** : arrêt immédiat, sans nouvelle tentative ni contournement, et trace dans `crawl_site`.
- **Réseaux sociaux** jamais visités. **Contenu** des pages jamais conservé : URL, titre, date, thème seulement.

## Données personnelles

- Élus municipaux seulement (RNE) : nom, fonction, début de mandat, délégation. Aucune étiquette politique.
- E-mails et téléphones : seulement ceux des mairies (annuaire de l'administration) et des écoles (annuaire de
  l'éducation, téléphone fixe), tels que publiés, adresses nominatives comprises. Aucun ailleurs en base :
  `uv run vi verifier` le contrôle.
- Adresses « chez M. ou Mme X » nettoyées. Exploitants individuels sans nom commercial anonymisés.
- Familles : données agrégées par IRIS.

## Open data et API

| Code | Source | Producteur | Alimente | Méthode | Mise à jour | Licence |
|---|---|---|---|---|---|---|
| `ign_admin_express` | [ADMIN EXPRESS COG CARTO (communes, arrondissements, population Insee)](https://data.geopf.fr/wfs/ows) | IGN / Insee | commune : contour, population, superficie, densité | api | annuelle | Licence Ouverte 2.0 |
| `banatic` | [Banatic, groupements de communes (EPCI, EPT, syndicats de restauration)](https://www.banatic.interieur.gouv.fr/consultation/api/export/pregenere/telecharger/11) | DGCL | commune : EPCI, EPT, Siren ; organisme : intercommunalités, syndicats de restauration et leurs contacts | csv | annuelle | Licence Ouverte 2.0 |
| `annuaire_administration` | [Annuaire de l'administration (contacts des mairies, des départements et de la région)](https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration) | DILA | commune : site web, téléphone, e-mail et formulaire de la mairie ; organisme : région et départements | api | annuelle | Licence Ouverte 2.0 |
| `ma_cantine` | [ma cantine, registre national et télédéclarations](https://www.data.gouv.fr/datasets/registre-national-des-cantines/) | Ministère de l'Agriculture | commune : cantine (régie ou concédée, % bio, % EGalim, satellites), cuisine_centrale, dispositif : communes rattachées à un PAT | csv | annuelle | Licence Ouverte 2.0 |
| `annuaire_education` | [Annuaire de l'éducation](https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-annuaire-education) | Ministère de l'Éducation nationale | ecole : identité, adresse, secteur, éducation prioritaire, restauration, téléphone fixe et e-mail | api | annuelle | Licence Ouverte 2.0 |
| `effectifs_ecoles` | [Effectifs d'élèves par école](https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-ecoles-effectifs-nb_classes) | Ministère de l'Éducation nationale (DEPP) | ecole : élèves, classes | api | annuelle | Licence Ouverte 2.0 |
| `ips_ecoles` | [Indices de position sociale des écoles](https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-ips-ecoles-ap2022) | Ministère de l'Éducation nationale (DEPP) | ecole : IPS | api | annuelle | Licence Ouverte 2.0 |
| `cites_educatives_etablissements` | [Établissements membres d'une cité éducative](https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-cites_educatives) | Ministère de l'Éducation nationale | ecole : cité éducative | api | annuelle | Licence Ouverte 2.0 |
| `ign_iris` | [Contours IRIS](https://data.geopf.fr/wfs/ows) | IGN / Insee | territoire_social : contours | api | annuelle | Licence Ouverte 2.0 |
| `insee_familles_iris` | [Recensement, familles par IRIS (API Melodi)](https://api.insee.fr/melodi/catalog/DS_RP_FAMILLE_COMP_IRIS) | Insee | territoire_social : familles avec enfants | csv | annuelle | Licence Ouverte 2.0 |
| `insee_filosofi_iris` | [Filosofi, revenus et pauvreté par IRIS](https://www.insee.fr/fr/statistiques/8229323) | Insee | territoire_social : revenu médian, taux de pauvreté | csv | annuelle | Licence Ouverte 2.0 |
| `insee_filosofi_communes` | [Filosofi, revenus par commune (communes non découpées en IRIS)](https://api.insee.fr/melodi/catalog/DS_FILOSOFI_CC) | Insee | territoire_social : revenu, pauvreté des communes non découpées | csv | annuelle | Licence Ouverte 2.0 |
| `anct_qpv` | [Quartiers prioritaires de la politique de la ville 2024](https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/qp-politiquedelaville-shp) | ANCT | dispositif : QPV | api | annuelle | Licence Ouverte 2.0 |
| `cdc_qpv` | [Quartiers prioritaires 2024, complément des contours manquants](https://opendata.caissedesdepots.fr/api/explore/v2.1/catalog/datasets/quartiers-prioritaires-de-la-politique-de-la-ville-au-1er-janvier-2024) | ANCT / Caisse des Dépôts | dispositif : contours de QPV manquants | api | annuelle | Licence Ouverte 2.0 |
| `anct_cites_educatives` | [Programme Cités éducatives (communes et QPV couverts)](https://www.data.gouv.fr/datasets/programme-cites-educatives/) | ANCT | dispositif : cités éducatives | csv | annuelle | Licence Ouverte 2.0 |
| `referentiel_vi` | Référentiel V.i (PAT DRIAAF, soutiens territoriaux, lauréats AAP MGP, syndicats de restauration) (`config/referentiel`) | Équipe V.i, d'après DRIAAF, Métropole du Grand Paris et départements (source citée à chaque ligne) | dispositif : niveau et axes des PAT, soutiens territoriaux, lauréats AAP MGP, syndicats de restauration | csv | annuelle | Faits publics relevés avec leur source |
| `france_pat` | [Projets alimentaires territoriaux (PAT) et lauréats PNA](https://www.data.gouv.fr/datasets/pat-projets-alimentaires-territoriaux-description/) | France PAT | dispositif : PAT (porteur, service, téléphone, site), lauréats d'appels à projets | csv | annuelle | Licence Ouverte 2.0 |
| `rne` | [Répertoire national des élus](https://www.data.gouv.fr/datasets/repertoire-national-des-elus-1/) | Ministère de l'Intérieur | elu : nom, fonction, début de mandat | csv | annuelle | Licence Ouverte 2.0 |
| `rna` | [Répertoire national des associations](https://www.data.gouv.fr/datasets/repertoire-national-des-associations/) | Ministère de l'Intérieur | asso_parents, relais_local (AMAP, épiceries, centres sociaux), asso_alimentation | csv | annuelle | Licence Ouverte 2.0 |
| `sirene` | [Base Sirene, stock des établissements](https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/) | Insee | accueil_periscolaire, relais_local | csv | annuelle | Licence Ouverte 2.0 |
| `sirene_unites` | [Base Sirene, stock des unités légales (Siren des associations, nature des cuisines centrales)](https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/) | Insee | asso_parents : Siren ; cuisine_centrale : catégorie juridique | csv | annuelle | Licence Ouverte 2.0 |
| `recherche_entreprises` | [API Recherche d'entreprises](https://recherche-entreprises.api.gouv.fr) | DINUM | accueil_periscolaire, gestionnaire_perisco | api | annuelle | Licence Ouverte 2.0 |
| `osm` | [OpenStreetMap (extrait Île-de-France de Geofabrik)](https://download.geofabrik.de/europe/france/ile-de-france-latest.osm.pbf) | Contributeurs OpenStreetMap | accueil_periscolaire, relais_local (dont contacts) | csv | annuelle | ODbL 1.0 |
| `agence_bio` | [API Professionnels Bio](https://opendata.agencebio.org/api/gouv/operateurs/) | Agence Bio | producteur (dont vente à la restauration collective et contacts) | api | annuelle | Licence Ouverte 2.0 |
| `ban` | [Base adresse nationale (géocodage)](https://data.geopf.fr/geocodage/search/csv) | IGN / DINUM | positions des adresses sans coordonnées | api | annuelle | Licence Ouverte 2.0 |

## Scraping

| Code | Source | Producteur | Alimente | Méthode | Mise à jour | Licence |
|---|---|---|---|---|---|---|
| `sites_mairies` | [Sites web des mairies (signaux, délégations, périscolaire)](https://www.service-public.fr) | Communes | signal_web, elu : délégations, accueil_periscolaire | scraping | mensuelle | Faits extraits (URL, date, thème) ; aucun contenu reproduit |
| `fcpe_departements` | [FCPE 93 et 95, conseils locaux](https://fcpe93.fr) | FCPE 93 / FCPE 95 | asso_parents : conseils locaux | scraping | mensuelle | Faits extraits (nom, commune, site) ; aucun contenu reproduit |
| `sites_assos` | [Sites des associations de parents (date de dernière activité)](https://www.data.gouv.fr/datasets/repertoire-national-des-associations/) | Associations | asso_parents : dernière activité en ligne | scraping | mensuelle | Faits extraits (date) ; aucun contenu reproduit |

- `sites_mairies`, vérifié le 25/11/2026 : robots.txt vérifié site par site à chaque passage, réserve TDM (en-tête et balise tdm-reservation) respectée. Seuls sont conservés l'URL, le titre, la date et le thème.
- `fcpe_departements`, vérifié le 25/11/2026 : FCPE 95 : mentions légales sans clause de réutilisation. FCPE 93 : pas de mentions légales publiées. FCPE 92 : aucun annuaire de conseils locaux. FCPE 77, 78, 91 et 94 : pas de site joignable.
- `sites_assos`, vérifié le 25/11/2026 : robots.txt vérifié site par site. Réseaux sociaux exclus (CGU).

## Calculs

| Code | Source | Producteur | Alimente | Méthode | Mise à jour | Licence |
|---|---|---|---|---|---|---|
| `rattachements` | Rattachements automatiques (accueils, associations) (`config/idf.yaml`) | Calcul | accueil_ecole, asso_ecole, IRIS et QPV des écoles, doublons | calcul | mensuelle | Sans objet |
| `osrm` | [Distances et temps par la route (OSRM sur OpenStreetMap)](https://download.geofabrik.de/europe/france/ile-de-france-latest.osm.pbf) | Calcul | proximite | calcul | annuelle | ODbL 1.0 |
| `jauges` | Jauges et score global (`config/jauges.yaml`) | Calcul | jauge_ecole, jauge_commune | calcul | mensuelle | Sans objet |

## Sources verrouillées

Leurs conditions interdisent l'extraction automatique. Le moteur refuse de les collecter, et tous les robots refusent leurs domaines, tant que `autorisation` (date et référence d'un accord écrit) n'est pas renseignée dans `config/sources.yaml`.

### monenfant.fr (accueils périscolaires)

- Code : `monenfant`. Aurait alimenté : accueil_periscolaire, gestionnaire_perisco.
- Conditions (https://monenfant.fr/mentions-legales), lues le 25/11/2026 : Les conditions limitent l'usage à des fins personnelles et non commerciales, interdisent toute exploitation commerciale et annoncent des poursuites pénales pour toute autre utilisation que la mise en relation des familles avec les structures d'accueil.
- robots.txt : autorisé (Disallow vide).
- Anti-robot : Radware Bot Manager (redirection vers validate.perfdrive.com).
- Domaines refusés : monenfant.fr, caf.fr.
- Remplacée par : `osm`, `sirene`, `recherche_entreprises`, `sites_mairies`.
- Démarche : Demander à la Cnaf (Direction des politiques familiale et sociale) un accès ou un export.

### Carte du Réseau AMAP Île-de-France

- Code : `amap_idf`. Aurait alimenté : relais_local, producteur : membre d'une AMAP.
- Conditions (https://amap-idf.org/infos-legales), lues le 25/11/2026 : Reproduction totale ou partielle prohibée ; transfert d'informations vers un site tiers interdit.
- robots.txt : autorisé (Disallow vide).
- Domaines refusés : amap-idf.org.
- Remplacée par : `rna`, `osm`.
- Démarche : Demander un export au Réseau AMAP IdF (partenaire naturel du projet).

### FCPE Paris, conseils locaux

- Code : `fcpe_paris`. Aurait alimenté : asso_parents.
- Conditions (https://www.fcpe75.org/mentions-legales/), lues le 25/11/2026 : Toute reproduction, même partielle, interdite sans accord exprès par écrit.
- robots.txt : autorisé.
- Domaines refusés : fcpe75.org, fcpe.asso.fr.
- Remplacée par : `rna`.
- Démarche : Demander l'accord écrit de la FCPE Paris.

### PEEP, associations locales

- Code : `peep_national`. Aurait alimenté : asso_parents.
- Conditions (https://peep.asso.fr/mentions-legales/), lues le 25/11/2026 : Reproduction autorisée pour un usage personnel et privé uniquement ; toute autre utilisation expressément interdite. Aucun site départemental francilien joignable.
- robots.txt : autorisé (Disallow vide).
- Domaines refusés : peep.asso.fr.
- Remplacée par : `rna`.
- Démarche : Demander l'accord écrit de la PEEP.
