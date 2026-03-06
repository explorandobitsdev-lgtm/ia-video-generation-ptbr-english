FROM python:3.11-slim

ARG INSTALL_VIDEO_AI=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        espeak-ng \
        ffmpeg \
        fonts-dejavu-core \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY tests ./tests
COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && python -m pip install --upgrade pip \
    && if [ "$INSTALL_VIDEO_AI" = "true" ]; then pip install ".[video-ai]"; else pip install .; fi

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
