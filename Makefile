# Raccourcis. « make » seul affiche l'aide.
DONNEES = https://github.com/baptistebarraque/VI-Mapping/releases/latest/download

.PHONY: aide installer base donnees voir archives collecte maj verifier couverture carte site controles

aide:
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | expand -t 14

installer: ## installe les dépendances Python et web
	uv sync --frozen --extra route
	cd web && npm ci

base: ## crée ou met à jour le schéma de la base
	uv run vi migrer

donnees: ## télécharge la base et les données de la carte déjà calculées
	mkdir -p data web/public
	curl -fL -o data/base.zip $(DONNEES)/base.zip
	curl -fL -o data/carte.zip $(DONNEES)/carte.zip
	uv run vi restaurer data/base.zip
	cd web/public && unzip -qo ../../data/carte.zip

voir: ## carte seule, sans base : télécharge ses données et la lance
	mkdir -p data web/public
	curl -fL -o data/carte.zip $(DONNEES)/carte.zip
	cd web/public && unzip -qo ../../data/carte.zip
	cd web && npm ci && npm run dev

archives: ## écrit data/base.zip et data/carte.zip, à joindre à une publication
	uv run vi sauvegarder data/base.zip
	rm -f data/carte.zip && cd web/public && zip -qr ../../data/carte.zip donnees

collecte: ## collecte toutes les sources, puis recalcule
	uv run vi collecter --tout

maj: ## mise à jour planifiée (échéances, calculs, contrôles, rapport, export)
	uv run vi maj

verifier: ## contrôle la base
	uv run vi verifier

couverture: ## écrit le rapport de couverture
	uv run vi couverture

carte: ## exporte les données et lance la carte en local
	uv run vi exporter
	cd web && npm run dev

site: ## construit la carte dans web/dist
	uv run vi exporter
	cd web && npm run build

controles: ## style, types et tests
	uv run ruff check src tests
	uv run pytest -q
	cd web && npx tsc --noEmit && npx vitest run
