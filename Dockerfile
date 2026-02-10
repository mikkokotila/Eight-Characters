FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY eight_characters /app/eight_characters

RUN pip install --upgrade pip \
    && pip install .

EXPOSE 8000

CMD uvicorn eight_characters.main:app --host 0.0.0.0 --port 8000
