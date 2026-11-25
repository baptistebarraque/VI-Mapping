# Raccourcis. « make » seul affiche l'aide.
.PHONY: aide installer base collecte maj verifier couverture carte site controles

aide:
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | expand -t 14

installer: ## installe les dépendances Python et web
	uv sync --frozen
	cd web && npm ci

base: ## crée ou met à jour le schéma de la base
	uv run vi migrer

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
