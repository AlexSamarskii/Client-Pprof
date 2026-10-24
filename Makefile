# Top-level orchestration. Each target fans out to backend / engine / frontend.
# Subproject Makefiles / package.json scripts remain the source of truth for
# what each command actually does — this file just wires them together.

.PHONY: help install install-dev lint format test test-unit hooks

help:
	@echo 'Targets:'
	@echo '  install      Install all subproject deps'
	@echo '  install-dev  Install all dev deps + pre-commit hooks'
	@echo '  lint         Lint backend, engine, frontend'
	@echo '  format       Format backend, engine, frontend'
	@echo '  test         Run all test suites (backend, engine, frontend unit)'
	@echo '  test-unit    Run unit tests only (skip integration / e2e)'
	@echo '  hooks        Run pre-commit on all files'

install:
	$(MAKE) -C backend install
	$(MAKE) -C engine install
	cd frontend && pnpm install --frozen-lockfile

install-dev:
	$(MAKE) -C backend install-dev
	$(MAKE) -C engine install-dev
	cd frontend && pnpm install
	# Single repo-root pre-commit install. Idempotent.
	uv --directory backend run pre-commit install --config ../.pre-commit-config.yaml

lint:
	$(MAKE) -C backend lint
	$(MAKE) -C engine lint-check
	cd frontend && pnpm lint && pnpm typecheck

format:
	$(MAKE) -C backend format
	cd engine && uv run ruff format
	cd frontend && pnpm format

test:
	$(MAKE) -C backend test
	$(MAKE) -C engine test
	cd frontend && pnpm test:unit

test-unit:
	$(MAKE) -C backend test-unit
	$(MAKE) -C engine test
	cd frontend && pnpm test:unit

hooks:
	uv --directory backend run pre-commit run --all-files --config ../.pre-commit-config.yaml
