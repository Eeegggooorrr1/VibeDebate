FROM python:3.12-slim AS backend-runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 POETRY_VIRTUALENVS_CREATE=false
WORKDIR /app/backend
RUN pip install --no-cache-dir poetry==2.2.1
COPY backend/pyproject.toml backend/poetry.lock ./
COPY backend/vibedebate ./vibedebate
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
RUN poetry install --only main
CMD ["uvicorn", "vibedebate.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
FROM backend-runtime AS backend-test
RUN poetry install --with dev --extras test
COPY backend/tests ./tests
CMD ["pytest"]
