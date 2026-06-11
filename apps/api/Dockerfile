# syntax=docker/dockerfile:1
# FastAPI read API + on-demand insight jobs (PRD 002 / 004).
# Build context: repository root (Railway default).

FROM python:3.13-slim AS builder

WORKDIR /build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.13-slim AS runtime

RUN groupadd --system --gid 1000 blackridge \
    && useradd --system --uid 1000 --gid blackridge --home-dir /app blackridge

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Kolkata

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY apps/ apps/
COPY core/ core/
COPY insights/ insights/
COPY metrics.py metrics.py

USER blackridge

EXPOSE 8000

CMD ["python", "-m", "apps.api"]
