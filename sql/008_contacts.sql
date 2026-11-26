-- Contacts professionnels publiés par les sources, pour la prospection. Chaque contact garde sa provenance :
-- celle de la ligne, ou le groupe « contact » de `provenances` quand il vient d'une autre source.

ALTER TABLE commune ADD COLUMN mairie_formulaire text;
COMMENT ON COLUMN commune.mairie_formulaire IS 'Page « nous contacter » de la mairie (annuaire de l''administration).';

ALTER TABLE producteur
    ADD COLUMN telephone text,
    ADD COLUMN email     text,
    ADD COLUMN site_web  text;
COMMENT ON COLUMN producteur.email IS 'Adresse publiée dans l''annuaire de l''Agence Bio, nominative ou non.';

ALTER TABLE relais_local
    ADD COLUMN telephone text,
    ADD COLUMN email     text;

ALTER TABLE accueil_periscolaire
    ADD COLUMN telephone text,
    ADD COLUMN email     text,
    ADD COLUMN site_web  text;

-- PAT : porteur et point d'entrée publiés par France PAT (aucun e-mail dans le jeu de données).
ALTER TABLE dispositif
    ADD COLUMN porteur   text,
    ADD COLUMN service   text,
    ADD COLUMN telephone text,
    ADD COLUMN site_web  text;
COMMENT ON COLUMN dispositif.service IS 'Service chargé du PAT chez le porteur.';

-- ----------------------------------------------------------------- collectivités autres que les communes
CREATE TABLE organisme (
    siren       char(9) PRIMARY KEY,
    type        text NOT NULL CHECK (type IN ('region', 'departement', 'epci', 'ept', 'syndicat_restauration')),
    nom         text NOT NULL,
    departement char(2),
    communes    text[] NOT NULL DEFAULT '{}',
    telephone   text,
    email       text,
    site_web    text,
    formulaire  text,
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON TABLE organisme IS 'Région, départements, intercommunalités et syndicats de restauration, avec le contact de leur siège.';
COMMENT ON COLUMN organisme.communes IS 'Communes membres (Île-de-France) ; vide pour la région et les départements.';
CREATE INDEX organisme_communes_idx ON organisme USING gin (communes);
ALTER TABLE organisme ADD FOREIGN KEY (source) REFERENCES source_donnees (code);
