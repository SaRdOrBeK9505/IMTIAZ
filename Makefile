# IMTIAZ — Makefile
# Tez-tez ishlatiladigan buyruqlar

PYTHON = .venv/Scripts/python.exe
MANAGE = $(PYTHON) manage.py

# ─── SETUP ────────────────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

# ─── DATABASE ─────────────────────────────────────────────────────────────────
migrate:
	$(MANAGE) migrate

migrations:
	$(MANAGE) makemigrations

superuser:
	$(MANAGE) createsuperuser

# ─── DEVELOPMENT ──────────────────────────────────────────────────────────────
run:
	$(MANAGE) runserver 0.0.0.0:8000

shell:
	$(MANAGE) shell

check:
	$(MANAGE) check

# ─── CELERY ───────────────────────────────────────────────────────────────────
worker:
	$(PYTHON) -m celery -A config worker --loglevel=info

beat:
	$(PYTHON) -m celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# ─── API DOCS ─────────────────────────────────────────────────────────────────
schema:
	$(MANAGE) spectacular --color --file schema.yml

# ─── STATIC ───────────────────────────────────────────────────────────────────
collectstatic:
	$(MANAGE) collectstatic --noinput

.PHONY: install migrate migrations superuser run shell check worker beat schema collectstatic
