PYTHON?=python3
POETRY?=poetry
PIP?=pip

ENV_FILE?=.env

.PHONY: setup dev migrate alembic fmt lint test worker scheduler observer bot

setup:
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

migrate:
	$(PYTHON) -m alembic upgrade head

alembic:
	$(PYTHON) -m alembic revision --autogenerate -m "update"

dev:
	$(PYTHON) -m uvicorn tgac.api.main:app --host 0.0.0.0 --port 8080 --reload

worker:
	$(PYTHON) -m tgac.workers.worker

scheduler:
	$(PYTHON) -m tgac.workers.scheduler

observer:
	$(PYTHON) -m tgac.workers.observer

bot:
	$(PYTHON) -m tgac.bot.app

fmt:
	$(PYTHON) -m black tgac tests
	$(PYTHON) -m isort tgac tests

lint:
	$(PYTHON) -m ruff check tgac tests

lint-fix:
	$(PYTHON) -m ruff check tgac tests --fix

check: fmt lint test

test:
	$(PYTHON) -m pytest -q
