-- Les jauges portent la même provenance que les autres lignes ;
-- confiance = part des poids connus dans le score (1 : aucun critère manquant).
TRUNCATE jauge_ecole;
ALTER TABLE jauge_ecole
    ADD COLUMN source      text NOT NULL REFERENCES source_donnees (code),
    ADD COLUMN url         text NOT NULL,
    ADD COLUMN methode     methode_collecte NOT NULL,
    ADD COLUMN collecte_le timestamptz NOT NULL,
    ADD COLUMN confiance   numeric(3, 2) NOT NULL CHECK (confiance BETWEEN 0 AND 1),
    DROP COLUMN calcule_le;
