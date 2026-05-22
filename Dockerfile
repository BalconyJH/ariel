# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_DEFAULT_INDEX=https://mirrors.cloud.tencent.com/pypi/simple/ \
    PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple/

WORKDIR /app

RUN python -m pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY arielbot ./arielbot
COPY Static/Src ./Static/Src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN sed -i \
        -e 's|http://deb.debian.org/debian-security|http://mirrors.cloud.tencent.com/debian-security|g' \
        -e 's|http://deb.debian.org/debian|http://mirrors.cloud.tencent.com/debian|g' \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libegl1 \
        libglib2.0-0 \
        fontconfig \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app /app
RUN mkdir -p /app/plugins /app/Static/Cache /app/data

EXPOSE 8080

CMD ["ariel", "run"]
