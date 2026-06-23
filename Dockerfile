FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    GARMINTOKENS=/root/.garminconnect

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv pip install -e .

COPY tests/ ./tests/
COPY pytest.ini ./
COPY start_railway.sh ./
RUN chmod +x /app/start_railway.sh

RUN mkdir -p /root/.garminconnect && chmod 700 /root/.garminconnect
COPY garmin_tokens.json /root/.garminconnect/garmin_tokens.json

ENTRYPOINT ["/bin/bash", "/app/start_railway.sh"]
