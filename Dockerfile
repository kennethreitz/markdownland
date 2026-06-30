# markdownland — Responder app on Granian, with pandoc + tectonic for conversions.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# System tools the conversion engine shells out to.
RUN apt-get update && apt-get install -y --no-install-recommends \
        pandoc poppler-utils curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Tectonic (self-contained LaTeX engine) for PDF output. Static musl binary.
ARG TECTONIC_VERSION=0.15.0
ARG TARGETARCH=amd64
RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) arch=x86_64 ;; \
      arm64) arch=aarch64 ;; \
      *) echo "unsupported arch ${TARGETARCH}" && exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-${arch}-unknown-linux-musl.tar.gz" \
      | tar -xz -C /usr/local/bin tectonic

WORKDIR /app

# Install dependencies first (cached layer), then the project.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

ENV HOST=0.0.0.0 PORT=8000 RESPONDER_SECRET_KEY=change-me
EXPOSE 8000

CMD ["uv", "run", "main.py"]
