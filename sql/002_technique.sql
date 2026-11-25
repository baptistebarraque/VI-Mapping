-- Tables techniques : sources, journal des collectes, caches, modèle de provenance.

-- api     : appel d'une API
-- csv     : fichier open data en bloc (CSV, mais aussi XLSX, Parquet, PBF)
-- scraping: page web publique
-- calcul  : ligne dérivée d'autres tables (proximite, rattachements, jauges)
CREATE TYPE methode_collecte AS ENUM ('api', 'csv', 'scraping', 'calcul');

CREATE TABLE source_donnees (
    code          text PRIMARY KEY,
    libelle       text NOT NULL,
    producteur    text NOT NULL,
    url           text NOT NULL,
    licence       text NOT NULL,
    methode       methode_collecte NOT NULL,
    frequence     text NOT NULL CHECK (frequence IN ('mensuelle', 'annuelle')),
    statut        text NOT NULL CHECK (statut IN ('ouverte', 'verrouillee')),
    confiance     numeric(3, 2) NOT NULL CHECK (confiance BETWEEN 0 AND 1),
    verification  jsonb NOT NULL DEFAULT '{}',
    maj_config_le timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE source_donnees IS 'Registre des sources, recopié depuis config/sources.yaml par « vi migrer ».';
COMMENT ON COLUMN source_donnees.statut IS 'verrouillee : collecte interdite par les CGU ou un anti-robot, en attente d''autorisation écrite.';

CREATE TABLE collecte_run (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source     text NOT NULL REFERENCES source_donnees (code),
    debut      timestamptz NOT NULL DEFAULT now(),
    fin        timestamptz,
    statut     text NOT NULL DEFAULT 'en_cours' CHECK (statut IN ('en_cours', 'succes', 'echec', 'ignoree')),
    parametres jsonb NOT NULL DEFAULT '{}',
    compteurs  jsonb NOT NULL DEFAULT '{}',
    message    text
);
CREATE INDEX collecte_run_source_idx ON collecte_run (source, debut DESC);

-- Colonnes obligatoires de chaque ligne collectée ou calculée.
CREATE TABLE modele_provenance (
    source      text NOT NULL,
    url         text NOT NULL,
    methode     methode_collecte NOT NULL,
    collecte_le timestamptz NOT NULL,
    confiance   numeric(3, 2) NOT NULL CHECK (confiance BETWEEN 0 AND 1)
);
COMMENT ON TABLE modele_provenance IS 'Gabarit (toujours vide) repris par LIKE dans toutes les tables métier.';

CREATE TABLE geocodage_cache (
    cle         text PRIMARY KEY,          -- adresse normalisée + code postal + code insee
    lon         double precision,
    lat         double precision,
    score       real,
    type        text,
    code_insee  char(5),
    libelle     text,
    geocode_le  timestamptz NOT NULL DEFAULT now()
);

-- Suivi du scraping : distingue « rien trouvé » de « jamais visité ».
CREATE TABLE crawl_site (
    hote             text NOT NULL,
    objet_type       text NOT NULL CHECK (objet_type IN ('commune', 'asso_parents', 'federation')),
    objet_id         text NOT NULL,
    url_depart       text NOT NULL,
    statut           text NOT NULL CHECK (statut IN
                       ('ok', 'robots_interdit', 'tdm_reserve', 'anti_robot', 'erreur_http', 'injoignable', 'vide')),
    pages_visitees   integer NOT NULL DEFAULT 0,
    pages_interdites integer NOT NULL DEFAULT 0,
    detail           text,
    visite_le        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (objet_type, objet_id, hote)
);
