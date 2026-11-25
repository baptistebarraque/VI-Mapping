# Méthode

Les valeurs citées ici sont celles par défaut. Elles se règlent dans `config/idf.yaml` et `config/jauges.yaml`.

## Rattachements

| Lien | Règle | Confiance |
|---|---|---|
| accueil ↔ école | même adresse | 0,95 |
| | moins de 300 m | 0,80 |
| | nom proche, même commune, moins de 1,5 km | 0,70 |
| asso ↔ école | nom ou adresse de l'école dans le nom ou l'objet | + 0,60 |
| | commune dans le nom ou l'objet | + 0,15 |
| | siège proche (plein à 80 m, nul à 1 km) | + 0,25 |
| | seule école possible de la commune | + 0,20 |

Une association n'est rattachée qu'à partir de 0,35, à six écoles au plus. La confiance est divisée par deux si le niveau,
le secteur ou le numéro de rue ne correspond pas.

Une même fiche trouvée dans plusieurs sources n'est pas supprimée : la plus précise devient principale, les autres
portent `doublon_de`. La carte et le rapport ne comptent que les fiches principales.

## Proximité

Distance à vol d'oiseau pour toutes les paires école-producteur et école-relais jusqu'à 50 km, puis distance et temps
par la route (OSRM sur OpenStreetMap, voiture, sans trafic) pour ces paires seulement.

Rayon par défaut : 10 km ou 15 min par la route, distance annoncée par V.i entre les écoles et les producteurs.

Producteurs retenus : bio ou en conversion, maraîchage ou fruits, vente directe. L'adhésion à une AMAP n'est pas connue
(source verrouillée). Un producteur connu par son seul siège est affiché mais pas compté : le siège n'est pas forcément
la ferme.

## Score des communes (étape 1)

La demande V.i procède en deux temps : repérer les communes les plus favorables, puis leurs écoles. Chaque commune
(arrondissement pour Paris) a son propre score, moyenne pondérée de ses critères **connus**, même règle que les jauges.
Dans la carte, l'étape 1 classe les communes ; on en retient quelques-unes, et l'étape 2 ne classe que leurs écoles.

| Critère | Poids | Calcul (100 = le mieux) |
|---|---:|---|
| PAT | 20 | meilleur PAT couvrant la commune : niveau 60 (niveau 2 = plein ; niveau inconnu compté 1), axe restauration collective 20, axe éducation alimentaire 20 ; 0 sans PAT |
| Soutiens | 10 | département 50 (score 0 à 2), intercommunalité ou EPT 25 (0 à 2), lauréat de l'AAP MGP « Restauration collective bio et locale » 25 |
| Cuisine | 15 | cuisine centrale principale : municipale ou caisse des écoles 100, intercommunale 80, autre public 70, privée 20 ; sinon cuisines sur place en régie 90, concédées 30 ; sinon membre d'un syndicat de restauration 80 |
| Bio en cantine | 10 | 100 à 40 % de bio déclaré (barème de la jauge Engagement) |
| Producteurs | 15 | moyenne de la jauge Producteurs des écoles de la commune : suit le rayon choisi dans la carte |
| Associations | 10 | associations d'alimentation durable (siège) : 50 pour le nombre (plein à 5), 50 pour la densité (plein à 3 pour 10 000 habitants) |
| Communications | 10 | thèmes alimentaires récents sur le site de la mairie (barème du critère « web » de la jauge Engagement) |
| Élèves | 10 | élèves des écoles du périmètre, plein à 1 500 |

Sources propres à cette étape :

- **PAT** : périmètre France PAT, complété par les communes que la DRIAAF rattache au PAT et par les PAT que les
  cantines déclarent dans ma cantine. Axes et priorités lus dans le livret DRIAAF ; l'axe éducation alimentaire de la
  DRIAAF prime sur le repérage par mot-clé de France PAT (qui le donne à tous les PAT franciliens).
- **Soutiens, lauréats MGP, syndicats** : référentiel relevé à la main (`config/referentiel/`), une source par ligne.
  Score 0 à 2 : 0 aucune politique identifiée (77, 78 et 95 restent à approfondir), 1 dispositif identifié, 2 politique
  forte et outillée.
- **Cuisine centrale** : celle qui livre le plus de repas aux satellites de la commune (ma cantine) ; son gestionnaire
  vient de la catégorie juridique Sirene (7210 commune, 7362 caisse des écoles, 734x-735x intercommunalité).
- **Associations** : RNA, titre puis objet, quatre catégories (AMAP et circuits courts, jardins et agriculture urbaine,
  éducation alimentaire, solidarité et anti-gaspillage). Classement par mots-clés, à vérifier avant tout contact.

Contacts : seulement le standard et l'adresse générique des mairies (annuaire de l'administration) et des écoles
(ce.UAI@ac-….fr). Aucune adresse nominative, aucune étiquette politique.

## Jauges

Une jauge est la moyenne de ses critères **connus**, pondérée par leurs sous-poids. Un critère sans donnée sort de la
moyenne ; il ne compte pas 0. Sous la moitié des sous-poids connus : « données insuffisantes ». Même règle pour le score
global, avec les poids des jauges.

| Jauge | Poids | Critères et sous-poids |
|---|---:|---|
| Engagement | 25 | PAT 35 (100 avec volet éducation alimentaire, 50 sans), % bio déclaré 25 (100 à 40 % de bio), signaux web de moins de 24 mois 25 (100 à 3 thèmes), cité éducative 15 |
| Périscolaire | 25 | accueil du soir à moins de 300 m 50, ouvert le mercredi 30, gestionnaire identifié 20 |
| Parents | 15 | asso rattachée, selon la confiance 50, fédérée 20, active en ligne depuis moins de 12 mois 30 |
| Producteurs | 20 | le plus proche 60 (100 à 15 min ou moins, 0 en bord de rayon), nombre dans le rayon 40 (plafond à 5) |
| Familles | 15 | élèves 30 (100 à 300), familles avec enfants de l'IRIS 30 (100 à 800), mixité sociale 40 (IPS 70, QPV 30) |

La carte recalcule en direct la jauge Producteurs (rayon) et le score (poids). Les deux calculs, Python et TypeScript,
passent les mêmes vecteurs de test (`tests/vecteurs/jauges.json`).

Périscolaire et Parents : les sources ouvertes ne sont pas exhaustives, donc rien trouvé vaut « inconnu », pas 0.
Maternelles : l'IPS n'est pas publié, celui de l'école élémentaire voisine (200 m, même secteur) est repris.

## Limites connues

- **Périscolaire et Parents peu couverts.** monenfant.fr, la carte des AMAP, FCPE Paris et PEEP interdisent la
  collecte. Voir les démarches dans [SOURCES.md](SOURCES.md) et les taux dans [rapport_couverture.md](rapport_couverture.md).
- **Une école peu documentée peut être bien classée** : son score repose sur les critères connus. La carte affiche
  « n/5 jauges », un filtre fixe un minimum, et à score égal la mieux documentée passe devant.
- **La jauge Producteurs départage peu** avec le rayon demandé (30 km ou 45 min) : presque toutes les écoles franciliennes
  ont cinq producteurs à portée. Un rayon de 8 à 10 km, réglable dans la carte, rend la jauge discriminante.
- **Sites de mairies** : sans `VI_CONTACT`, échantillon des 120 communes qui ont le plus d'élèves. Ailleurs, les signaux
  web sont inconnus, pas absents.
- **Temps de trajet sans trafic** : `facteur_duree` (1,3 à 1,5) donne une durée d'heure de pointe.
- **Dates** : année scolaire, millésime ou campagne diffèrent selon la source. La fiche montre la date de collecte.
- **Une commune peu documentée peut être bien classée**, comme une école : la carte affiche « n/8 critères » et un
  filtre fixe un minimum. Les critères les plus souvent inconnus sont la cuisine et le bio (communes absentes de
  ma cantine) et les communications (site de la mairie pas encore visité).
- **Locaux communaux, activité des parents, labels E3D, potager** : pas de source ouverte ; prévus en saisie terrain.
