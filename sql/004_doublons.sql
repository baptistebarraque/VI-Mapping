-- Un même lieu peut venir de plusieurs sources (RNA, Sirene, OSM…) : on garde chaque ligne,
-- avec sa provenance, et on désigne la fiche principale. Renseigné par « vi rattacher ».
ALTER TABLE accueil_periscolaire ADD COLUMN doublon_de text REFERENCES accueil_periscolaire (id) ON DELETE SET NULL;
ALTER TABLE relais_local ADD COLUMN doublon_de text REFERENCES relais_local (id) ON DELETE SET NULL;
ALTER TABLE asso_parents ADD COLUMN doublon_de text REFERENCES asso_parents (id) ON DELETE SET NULL;

-- Nom brut de l'exploitant donné par la source (jamais une personne physique), avant identification au Siren.
ALTER TABLE accueil_periscolaire ADD COLUMN exploitant text;
COMMENT ON COLUMN accueil_periscolaire.doublon_de IS 'Fiche principale décrivant le même lieu ; NULL pour une fiche principale.';
