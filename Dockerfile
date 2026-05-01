# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile
#
# Multi-stage build that produces a lean production image for the
# DevRel Discord Bot.
#
# Build:
#   docker build -t devrel-discord-bot .
#
# Run (pass secrets as environment variables, NOT inside the image):
#   docker run --rm \
#     -e DISCORD_TOKEN=xxx \
#     -e YOUTUBE_API_KEY=xxx \
#     devrel-discord-bot
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: dependency installer ────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies for any C-extension wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: production image ─────────────────────────────────────────────────
FROM python:3.12-slim

# Non-root user for least-privilege operation.
RUN addgroup --system botgroup && adduser --system --ingroup botgroup botuser

WORKDIR /app

# Copy installed packages from builder.
COPY --from=builder /install /usr/local

# Copy application source.
COPY . .

# Ensure the data directory (state.json) is writable by the non-root user.
RUN mkdir -p /app/data && chown -R botuser:botgroup /app/data

USER botuser

# Secrets must be supplied at runtime – never bake them into the image.
# ENV DISCORD_TOKEN and YOUTUBE_API_KEY are set by the container host.

CMD ["python", "main.py"]
