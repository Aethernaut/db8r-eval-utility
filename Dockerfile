# db8r-eval-utility API (FastAPI) — production image.
# Build context: db8r-eval-utility/   (pyproject + eval_utility/ live here)
#
# NOTE: when the Postgres store + auth land, pyproject must gain those deps
# (e.g. psycopg[binary]/sqlalchemy/asyncpg, passlib/argon2, python-jose or itsdangerous).
# This Dockerfile installs whatever pyproject declares, so no change is needed here.
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root

COPY eval_utility ./eval_utility

EXPOSE 8000
# Runtime config (DATABASE_URL, JWT secret, CLAIMCHECK_BASE_URL, DB8R_MCTS_BASE_URL,
# FIXTURES_DIR) comes from the environment. Fixtures live on a mounted volume.
CMD ["uvicorn", "eval_utility.server:app", "--host", "0.0.0.0", "--port", "8000"]
