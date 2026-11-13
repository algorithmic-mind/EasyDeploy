# Development entry points (Linux / WSL2). See CLAUDE.md for Windows-native commands.
.PHONY: install dev dev-api dev-worker dev-agent dev-web dev-redis lint typecheck test check \
        frontend-build schema client seed clean

UV ?= uv
DJANGO = $(UV) run python backend/manage.py
export DJANGO_SETTINGS_MODULE ?= easydeploy.settings.dev

install:
	$(UV) sync --all-packages
	cd frontend && pnpm install

dev:  ## Redis + API + worker + agent (DryRun) + Vite, in parallel
	$(MAKE) -j5 dev-redis dev-agent dev-api dev-worker dev-web

dev-redis:
	redis-server --port 0 --unixsocket var/redis.sock --unixsocketperm 700 --save "" --appendonly no

dev-agent:
	$(UV) run python -m easydeploy_agent --dev

dev-api:
	$(DJANGO) migrate --database default && $(DJANGO) migrate --database monitor
	$(UV) run uvicorn easydeploy.asgi:application --app-dir backend --reload --port 8000

dev-worker:
	cd backend && $(UV) run celery -A easydeploy worker -B -Q default,deploy,backup,monitor --concurrency 2 -l info

dev-web:
	cd frontend && pnpm dev

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	python scripts/check_no_shell.py
	cd frontend && pnpm lint

typecheck:
	$(UV) run mypy agent/easydeploy_agent cli/edctl
	cd backend && $(UV) run mypy .
	cd frontend && pnpm type-check

test:
	$(UV) run pytest
	cd frontend && pnpm test

check: lint typecheck test

frontend-build:
	cd frontend && pnpm build

schema:  ## Export OpenAPI schema and regenerate the TS client
	$(DJANGO) spectacular --file frontend/openapi.yaml --validate
	cd frontend && pnpm gen:api

seed:
	$(DJANGO) seed_demo

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache frontend/dist
