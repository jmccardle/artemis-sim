FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./

RUN pip install --no-cache-dir -e .

EXPOSE 8000

# Default: run the web app. Override CMD for workers.
CMD ["uvicorn", "artemis.main:app", "--host", "0.0.0.0", "--port", "8000"]
