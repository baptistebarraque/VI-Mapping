-- Modèle de données métier. Coordonnées en WGS84 (EPSG:4326) ;
-- geom_l93 (EPSG:2154, Lambert 93) sert aux calculs métriques.
--
-- Aucune colonne e-mail ni téléphone. Seules personnes nommées : les élus (RNE).

CREATE TABLE commune (
    code_insee              char(5) PRIMARY KEY,
    nom                     text NOT NULL,
    type                    text NOT NULL DEFAULT 'commune' CHECK (type IN ('commune', 'arrondissement')),
    commune_mere            char(5) REFERENCES commune (code_insee) ON DELETE CASCADE,
    departement             char(2) NOT NULL,
    siren                   char(9),
    epci_siren              char(9),
    epci_nom                text,
    ept_siren               char(9),
    ept_nom                 text,
    population              integer,
    population_annee        smallint,
    superficie_km2          numeric(10, 3),
    densite                 numeric(10, 1) GENERATED ALWAYS AS
                              (CASE WHEN superficie_km2 > 0 THEN round(population / superficie_km2, 1) END) STORED,
    code_postal             text,
    site_web                text,
    cantine_gestion         text CHECK (cantine_gestion IN ('regie', 'concedee', 'mixte')),
    cantine_nb              integer,
    cantine_nb_declarations integer,
    cantine_pct_bio         numeric(5, 2) CHECK (cantine_pct_bio BETWEEN 0 AND 100),
    cantine_pct_egalim      numeric(5, 2) CHECK (cantine_pct_egalim BETWEEN 0 AND 100),
    cantine_annee           smallint,
    geom                    geometry(MultiPolygon, 4326) NOT NULL,
    provenances             jsonb NOT NULL DEFAULT '{}',
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON COLUMN commune.commune_mere IS 'Commune de rattachement d''un arrondissement municipal (75056 pour Paris).';
COMMENT ON COLUMN commune.ept_siren IS 'Établissement public territorial (Métropole du Grand Paris).';
COMMENT ON COLUMN commune.cantine_nb IS 'Restaurants scolaires publics du 1er degré inscrits sur ma cantine.';
COMMENT ON COLUMN commune.cantine_pct_egalim IS 'Part des achats durables et de qualité, bio compris.';
COMMENT ON COLUMN commune.provenances IS 'Provenance par groupe de champs enrichis : {groupe: {source, url, methode, collecte_le, confiance}}.';
CREATE INDEX commune_geom_idx ON commune USING gist (geom);
CREATE INDEX commune_dep_idx ON commune (departement);

CREATE TABLE ecole (
    uai                  char(8) PRIMARY KEY,
    nom                  text NOT NULL,
    commune              char(5) NOT NULL REFERENCES commune (code_insee),
    departement          char(2) NOT NULL,
    type                 text NOT NULL CHECK (type IN ('maternelle', 'elementaire', 'primaire')),
    secteur              text NOT NULL CHECK (secteur IN ('public', 'prive_sous_contrat')),
    adresse              text,
    code_postal          text,
    nb_eleves            integer CHECK (nb_eleves >= 0),
    nb_classes           integer CHECK (nb_classes >= 0),
    effectifs_rentree    smallint,
    ips                  numeric(5, 1),
    ips_rentree          text,
    education_prioritaire text CHECK (education_prioritaire IN ('REP', 'REP+')),
    cite_educative       text,
    restauration         boolean,
    iris                 char(9),
    qpv                  text,
    qpv_distance_m       integer,
    geom                 geometry(Point, 4326),
    geom_l93             geometry(Point, 2154) GENERATED ALWAYS AS (ST_Transform(geom, 2154)) STORED,
    provenances          jsonb NOT NULL DEFAULT '{}',
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON COLUMN ecole.cite_educative IS 'Nom de la cité éducative dont l''école est membre.';
COMMENT ON COLUMN ecole.qpv IS 'QPV contenant l''école, sinon le plus proche (voir qpv_distance_m ; 0 = dedans).';
CREATE INDEX ecole_l93_idx ON ecole USING gist (geom_l93);
CREATE INDEX ecole_commune_idx ON ecole (commune);

CREATE TABLE gestionnaire_perisco (
    siren       char(9) PRIMARY KEY,
    nom         text NOT NULL,
    type        text NOT NULL CHECK (type IN ('regie', 'association', 'entreprise')),
    nb_accueils integer NOT NULL DEFAULT 0,
    LIKE modele_provenance INCLUDING CONSTRAINTS
);

CREATE TABLE accueil_periscolaire (
    id            text PRIMARY KEY,
    nom           text NOT NULL,
    adresse       text,
    commune       char(5) REFERENCES commune (code_insee),
    accueil_soir  boolean,
    accueil_mercredi boolean,
    horaires      text,
    gestionnaire_siren char(9) REFERENCES gestionnaire_perisco (siren) ON DELETE SET NULL,
    geom          geometry(Point, 4326) NOT NULL,
    geom_l93      geometry(Point, 2154) GENERATED ALWAYS AS (ST_Transform(geom, 2154)) STORED,
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON COLUMN accueil_periscolaire.accueil_soir IS 'NULL : la source ne le dit pas (différent de « non »).';
CREATE INDEX accueil_l93_idx ON accueil_periscolaire USING gist (geom_l93);

CREATE TABLE accueil_ecole (
    accueil_id text NOT NULL REFERENCES accueil_periscolaire (id) ON DELETE CASCADE,
    ecole_uai  char(8) NOT NULL REFERENCES ecole (uai) ON DELETE CASCADE,
    motif      text NOT NULL CHECK (motif IN ('adresse', 'distance', 'nom')),
    distance_m integer NOT NULL,
    LIKE modele_provenance INCLUDING CONSTRAINTS,
    PRIMARY KEY (accueil_id, ecole_uai)
);
CREATE INDEX accueil_ecole_uai_idx ON accueil_ecole (ecole_uai);

CREATE TABLE asso_parents (
    id                     text PRIMARY KEY,
    rna                    text,
    siren                  char(9),
    nom                    text NOT NULL,
    objet                  text,
    siege                  text,
    commune                char(5) REFERENCES commune (code_insee),
    federation             text CHECK (federation IN ('FCPE', 'PEEP', 'UNAAPE', 'APEL')),
    niveau                 text NOT NULL CHECK (niveau IN ('premier_degre', 'second_degre', 'indetermine')),
    date_creation          date,
    site_web               text,
    derniere_activite      date,
    derniere_activite_url  text,
    ecole_uai              char(8) REFERENCES ecole (uai) ON DELETE SET NULL,
    confiance_rattachement numeric(3, 2) CHECK (confiance_rattachement BETWEEN 0 AND 1),
    geom                   geometry(Point, 4326),
    geom_l93               geometry(Point, 2154) GENERATED ALWAYS AS (ST_Transform(geom, 2154)) STORED,
    provenances            jsonb NOT NULL DEFAULT '{}',
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON COLUMN asso_parents.ecole_uai IS 'Meilleur rattachement ; tous les rattachements sont dans asso_ecole.';
CREATE INDEX asso_l93_idx ON asso_parents USING gist (geom_l93);
CREATE INDEX asso_ecole_best_idx ON asso_parents (ecole_uai);

CREATE TABLE asso_ecole (
    asso_id   text NOT NULL REFERENCES asso_parents (id) ON DELETE CASCADE,
    ecole_uai char(8) NOT NULL REFERENCES ecole (uai) ON DELETE CASCADE,
    indices   jsonb NOT NULL DEFAULT '{}',
    LIKE modele_provenance INCLUDING CONSTRAINTS,
    PRIMARY KEY (asso_id, ecole_uai)
);
CREATE INDEX asso_ecole_uai_idx ON asso_ecole (ecole_uai);

CREATE TABLE territoire_social (
    iris                  char(9) PRIMARY KEY,
    nom                   text NOT NULL,
    type_iris             text,
    commune               char(5) NOT NULL REFERENCES commune (code_insee),
    familles              integer,
    familles_avec_enfants integer,
    annee_familles        smallint,
    revenu_median         integer,
    taux_pauvrete         numeric(5, 1),
    annee_revenus         smallint,
    qpv                   text[] NOT NULL DEFAULT '{}',
    part_qpv              numeric(4, 3),
    geom                  geometry(MultiPolygon, 4326) NOT NULL,
    provenances           jsonb NOT NULL DEFAULT '{}',
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON TABLE territoire_social IS 'Maille IRIS, données agrégées uniquement (aucune donnée de ménage).';
CREATE INDEX territoire_geom_idx ON territoire_social USING gist (geom);
CREATE INDEX territoire_commune_idx ON territoire_social (commune);

CREATE TABLE relais_local (
    id       text PRIMARY KEY,
    type     text NOT NULL CHECK (type IN
               ('centre_social', 'distribution_amap', 'epicerie_solidaire', 'ferme_pedagogique')),
    nom      text NOT NULL,
    adresse  text,
    commune  char(5) REFERENCES commune (code_insee),
    site_web text,
    geom     geometry(Point, 4326) NOT NULL,
    geom_l93 geometry(Point, 2154) GENERATED ALWAYS AS (ST_Transform(geom, 2154)) STORED,
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
CREATE INDEX relais_l93_idx ON relais_local USING gist (geom_l93);

CREATE TABLE elu (
    id                text PRIMARY KEY,
    commune           char(5) NOT NULL REFERENCES commune (code_insee) ON DELETE CASCADE,
    nom               text NOT NULL,
    prenom            text NOT NULL,
    fonction          text NOT NULL,
    delegation        text,
    delegation_themes text[] NOT NULL DEFAULT '{}',
    debut_mandat      date,
    provenances       jsonb NOT NULL DEFAULT '{}',
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON TABLE elu IS 'Élus municipaux (RNE). Date de naissance, sexe et profession du fichier source ne sont jamais stockés.';
CREATE INDEX elu_commune_idx ON elu (commune);

CREATE TABLE signal_web (
    id          text PRIMARY KEY,
    commune     char(5) NOT NULL REFERENCES commune (code_insee) ON DELETE CASCADE,
    titre       text,
    date_page   date,
    date_origine text CHECK (date_origine IN ('meta', 'sitemap', 'texte', 'http')),
    type_page   text NOT NULL CHECK (type_page IN ('actualite', 'agenda', 'menu', 'document', 'page')),
    theme       text NOT NULL CHECK (theme IN
                  ('bio', 'anti_gaspi', 'potager', 'education_gout', 'alimentation_durable',
                   'periscolaire_soir', 'periscolaire_mercredi')),
    occurrences integer NOT NULL DEFAULT 1,
    LIKE modele_provenance INCLUDING CONSTRAINTS,
    UNIQUE (url, theme)
);
COMMENT ON COLUMN signal_web.date_page IS 'Date de publication ou de mise à jour ; NULL si la page n''en affiche pas.';
CREATE INDEX signal_commune_idx ON signal_web (commune, theme);

CREATE TABLE dispositif (
    id                      text PRIMARY KEY,
    type                    text NOT NULL CHECK (type IN ('pat', 'cite_educative', 'qpv', 'laureat_aap')),
    nom                     text NOT NULL,
    communes                text[] NOT NULL DEFAULT '{}',
    axe_education_alimentaire boolean,
    annee                   smallint,
    niveau                  text,
    geom                    geometry(MultiPolygon, 4326),
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON COLUMN dispositif.communes IS 'Périmètre : codes Insee des communes couvertes, limité à l''Île-de-France.';
CREATE INDEX dispositif_geom_idx ON dispositif USING gist (geom);
CREATE INDEX dispositif_communes_idx ON dispositif USING gin (communes);

CREATE TABLE producteur (
    id            text PRIMARY KEY,
    siret         char(14),
    numero_bio    integer,
    nom           text NOT NULL,
    activites     text[] NOT NULL DEFAULT '{}',
    productions   text[] NOT NULL DEFAULT '{}',
    maraichage    boolean NOT NULL,
    fruits        boolean NOT NULL,
    etat_bio      text NOT NULL CHECK (etat_bio IN ('bio', 'conversion', 'bio_et_conversion', 'inconnu')),
    vente_directe boolean,
    membre_amap   boolean,
    eligible      boolean NOT NULL,
    adresse       text,
    adresse_type  text NOT NULL CHECK (adresse_type IN ('lieu_activite', 'lieu_vente', 'siege')),
    commune       char(5) REFERENCES commune (code_insee),
    geom          geometry(Point, 4326) NOT NULL,
    geom_l93      geometry(Point, 2154) GENERATED ALWAYS AS (ST_Transform(geom, 2154)) STORED,
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON COLUMN producteur.eligible IS 'Compté dans la jauge : bio ou conversion, légumes ou fruits, vente directe ou livraison AMAP.';
COMMENT ON COLUMN producteur.adresse_type IS 'siege : l''adresse n''est pas forcément celle de la ferme (confiance abaissée).';
COMMENT ON COLUMN producteur.nom IS 'Nom commercial ; jamais le nom d''une personne physique (exploitant individuel anonymisé).';
CREATE INDEX producteur_l93_idx ON producteur USING gist (geom_l93);

CREATE TABLE proximite (
    ecole_uai     char(8) NOT NULL REFERENCES ecole (uai) ON DELETE CASCADE,
    cible_type    text NOT NULL CHECK (cible_type IN ('producteur', 'relais_local')),
    cible_id      text NOT NULL,
    km_vol_oiseau real NOT NULL,
    km_route      real,
    minutes       real,
    LIKE modele_provenance INCLUDING CONSTRAINTS,
    PRIMARY KEY (ecole_uai, cible_type, cible_id)
);
COMMENT ON TABLE proximite IS 'Paires école-cible à moins de 50 km à vol d''oiseau ; NULL en km_route/minutes : pas d''itinéraire.';

CREATE TABLE jauge_ecole (
    ecole_uai    char(8) PRIMARY KEY REFERENCES ecole (uai) ON DELETE CASCADE,
    engagement   numeric(5, 1) CHECK (engagement BETWEEN 0 AND 100),
    periscolaire numeric(5, 1) CHECK (periscolaire BETWEEN 0 AND 100),
    parents      numeric(5, 1) CHECK (parents BETWEEN 0 AND 100),
    producteurs  numeric(5, 1) CHECK (producteurs BETWEEN 0 AND 100),
    familles     numeric(5, 1) CHECK (familles BETWEEN 0 AND 100),
    score        numeric(5, 1) CHECK (score BETWEEN 0 AND 100),
    details      jsonb NOT NULL,
    config_hash  text NOT NULL,
    calcule_le   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN jauge_ecole.engagement IS 'NULL = données insuffisantes (jamais compté 0) ; idem pour les autres jauges et le score.';

-- Toute ligne renvoie à une source du registre.
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['commune', 'ecole', 'gestionnaire_perisco', 'accueil_periscolaire', 'accueil_ecole',
                             'asso_parents', 'asso_ecole', 'territoire_social', 'relais_local', 'elu', 'signal_web',
                             'dispositif', 'producteur', 'proximite']
    LOOP
        EXECUTE format('ALTER TABLE %I ADD FOREIGN KEY (source) REFERENCES source_donnees (code)', t);
    END LOOP;
END $$;
