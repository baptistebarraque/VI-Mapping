-- Étape « communes » de la demande V.i : cuisines centrales, associations d'alimentation durable,
-- soutiens territoriaux (référentiel curé), contacts des mairies et des écoles et score propre de chaque commune.

-- ----------------------------------------------------------------- cuisines centrales (ma cantine + Sirene)
CREATE TABLE cuisine_centrale (
    siret               char(14) PRIMARY KEY,
    nom                 text NOT NULL,
    type                text NOT NULL CHECK (type IN
                          ('municipale', 'caisse_des_ecoles', 'intercommunale', 'autre_public', 'privee', 'inconnu')),
    categorie_juridique text,
    commune             char(5) REFERENCES commune (code_insee) ON DELETE SET NULL,
    gestion             text CHECK (gestion IN ('regie', 'concedee')),
    nb_cantines         integer NOT NULL DEFAULT 0,
    repas_jour          integer,
    pct_bio             numeric(5, 2) CHECK (pct_bio BETWEEN 0 AND 100),
    pct_egalim          numeric(5, 2) CHECK (pct_egalim BETWEEN 0 AND 100),
    annee               smallint,
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON COLUMN cuisine_centrale.type IS 'Déduit de la catégorie juridique Sirene du Siren (7210 commune, 7362 caisse des écoles, 734x-735x intercommunalité).';
COMMENT ON COLUMN cuisine_centrale.nb_cantines IS 'Restaurants scolaires du 1er degré d''Île-de-France qu''elle livre.';

ALTER TABLE commune
    ADD COLUMN cantine_nb_satellites   integer,
    ADD COLUMN cantine_nb_sur_place    integer,
    ADD COLUMN cantine_part_regie      numeric(4, 3) CHECK (cantine_part_regie BETWEEN 0 AND 1),
    ADD COLUMN cantine_repas_jour      integer,
    ADD COLUMN cantine_pat             text[] NOT NULL DEFAULT '{}',
    ADD COLUMN cuisine_centrale_siret  char(14),  -- sans clé étrangère : cuisine_centrale référence déjà commune
    ADD COLUMN mairie_telephone        text,
    ADD COLUMN mairie_email            text;
COMMENT ON COLUMN commune.cantine_pat IS 'PAT (dispositif.id) déclarés par les cantines scolaires de la commune sur ma cantine.';
COMMENT ON COLUMN commune.cuisine_centrale_siret IS 'Cuisine centrale qui livre le plus de repas scolaires de la commune.';
COMMENT ON COLUMN commune.mairie_email IS 'Adresse de la mairie (annuaire de l''administration), nominative ou non.';

-- ----------------------------------------------------------------- contacts des écoles
ALTER TABLE ecole
    ADD COLUMN telephone text,
    ADD COLUMN email     text;
COMMENT ON COLUMN ecole.email IS 'Adresse de l''école (annuaire de l''éducation), nominative ou non.';

-- ----------------------------------------------------------------- producteurs
ALTER TABLE producteur ADD COLUMN vente_restauration_collective boolean;

-- ----------------------------------------------------------------- associations d'alimentation durable (RNA)
CREATE TABLE asso_alimentation (
    id            text PRIMARY KEY,
    rna           text NOT NULL,
    nom           text NOT NULL,
    categorie     text NOT NULL CHECK (categorie IN
                    ('amap_circuits_courts', 'jardins_agriculture_urbaine', 'education_alimentaire',
                     'solidarite_anti_gaspi')),
    objet         text,
    commune       char(5) NOT NULL REFERENCES commune (code_insee),
    date_creation date,
    derniere_declaration date,
    site_web      text,
    geom          geometry(Point, 4326),
    geom_l93      geometry(Point, 2154) GENERATED ALWAYS AS (ST_Transform(geom, 2154)) STORED,
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON TABLE asso_alimentation IS 'Siège social seulement : pas forcément le lieu d''activité. Classement par mots-clés, à vérifier avant contact.';
CREATE INDEX asso_alimentation_commune_idx ON asso_alimentation (commune);

-- ----------------------------------------------------------------- dispositifs : référentiel curé et soutiens
ALTER TABLE dispositif DROP CONSTRAINT dispositif_type_check;
ALTER TABLE dispositif ADD CONSTRAINT dispositif_type_check CHECK (type IN
    ('pat', 'cite_educative', 'qpv', 'laureat_aap', 'soutien_territorial', 'laureat_aap_mgp',
     'syndicat_restauration'));
ALTER TABLE dispositif
    ADD COLUMN axe_restauration_collective boolean,
    ADD COLUMN axe_education_verifie       boolean,
    ADD COLUMN priorites                   text,
    ADD COLUMN niveau_num                  smallint CHECK (niveau_num BETWEEN 0 AND 2),
    ADD COLUMN perimetre_precision         text,
    ADD COLUMN communes_ajoutees           text[] NOT NULL DEFAULT '{}',
    ADD COLUMN echelon                     text CHECK (echelon IN ('region', 'departement', 'interco')),
    ADD COLUMN score                       smallint CHECK (score BETWEEN 0 AND 2),
    ADD COLUMN editions                    text,
    ADD COLUMN provenances                 jsonb NOT NULL DEFAULT '{}';
COMMENT ON COLUMN dispositif.axe_education_verifie IS 'Axe éducation alimentaire lu dans la fiche DRIAAF ; prime sur axe_education_alimentaire (mot-clé).';
COMMENT ON COLUMN dispositif.priorites IS 'PAT : axes et priorités ; soutien : description du dispositif.';
COMMENT ON COLUMN dispositif.communes_ajoutees IS 'PAT : communes hors périmètre déclaré qui s''y rattachent (ma cantine, DRIAAF).';
COMMENT ON COLUMN dispositif.score IS 'Soutien territorial : 0 aucun, 1 dispositif identifié, 2 politique forte et outillée.';
CREATE INDEX dispositif_ajoutees_idx ON dispositif USING gin (communes_ajoutees);

-- ----------------------------------------------------------------- score propre de chaque commune
CREATE TABLE jauge_commune (
    code_insee  char(5) PRIMARY KEY REFERENCES commune (code_insee) ON DELETE CASCADE,
    score       numeric(5, 1) CHECK (score BETWEEN 0 AND 100),
    details     jsonb NOT NULL,
    config_hash text NOT NULL,
    LIKE modele_provenance INCLUDING CONSTRAINTS
);
COMMENT ON COLUMN jauge_commune.details IS 'Valeur (0-100 ou NULL = inconnu) et détail de chaque critère communal.';

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['cuisine_centrale', 'asso_alimentation', 'jauge_commune']
    LOOP
        EXECUTE format('ALTER TABLE %I ADD FOREIGN KEY (source) REFERENCES source_donnees (code)', t);
    END LOOP;
END $$;
