-- Nouveau statut : le site appartient à une source verrouillée par ses CGU (config/sources.yaml).
ALTER TABLE crawl_site DROP CONSTRAINT crawl_site_statut_check;
ALTER TABLE crawl_site ADD CONSTRAINT crawl_site_statut_check CHECK (statut IN
  ('ok', 'robots_interdit', 'cgu_interdit', 'tdm_reserve', 'anti_robot', 'erreur_http', 'injoignable', 'vide'));
