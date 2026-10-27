# Image de production : Python 3.12, dépendances installées par uv depuis uv.lock.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app
# D'abord les dépendances seules : cette couche reste en cache tant que uv.lock ne change pas.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
COPY config ./config
# Le lot B ajoute : COPY donnees ./donnees
RUN uv sync --frozen --no-dev

# Un utilisateur sans privilège pour faire tourner le programme.
RUN useradd --create-home epreuve
USER epreuve

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
CMD ["python", "-m", "epreuve.main"]
