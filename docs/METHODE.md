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

Producteurs retenus : bio ou en conversion, maraîchage ou fruits, vente directe. L'adhésion à une AMAP n'est pas connue
(source verrouillée). Un producteur connu par son seul siège est affiché mais pas compté : le siège n'est pas forcément
la ferme.

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
