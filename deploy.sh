#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# MyWeatherHub — homelab deploy script (GHCR pull-and-run)
#
# The image is BUILT in CI (.github/workflows/deploy.yml) and pushed to GHCR.
# This script does NOT build — it pulls the pre-built image and (re)starts the
# container. Same role as before, but no local `docker build`.
#
# Used two ways:
#   • CI: the self-hosted runner runs `bash deploy.sh` with IMAGE/GHCR_* set.
#   • Manual: IMAGE=ghcr.io/phani05353/myweatherhub:latest ./deploy.sh
#     (run `docker login ghcr.io` first, or pass GHCR_USER/GHCR_TOKEN).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/phani05353/myweatherhub:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-myweatherhub}"
HOST_PORT="${HOST_PORT:-5090}"   # host :5090 → container :5000 (tailscale-served at :8449)

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   MyWeatherHub — Deploy (GHCR)       ║"
echo "╚══════════════════════════════════════╝"
echo "  image: $IMAGE"
echo ""

# ── 1. Log in to GHCR (only if creds are provided) ───────────────────────────
# CI passes GHCR_USER/GHCR_TOKEN (the workflow's GITHUB_TOKEN). For a manual run
# where you've already `docker login`-ed, leave them unset and this is skipped.
if [ -n "${GHCR_TOKEN:-}" ]; then
  echo "▶ Step 1/4 — Logging in to ghcr.io as ${GHCR_USER:-?}..."
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-x}" --password-stdin
  echo "  ✓ Logged in"
else
  echo "▶ Step 1/4 — Skipping login (no GHCR_TOKEN; using existing docker auth)"
fi

# ── 2. Pull the pre-built image ──────────────────────────────────────────────
echo ""
echo "▶ Step 2/4 — Pulling image..."
docker pull "$IMAGE"
echo "  ✓ Image pulled"

# ── 3. Stop + remove old container ───────────────────────────────────────────
echo ""
echo "▶ Step 3/4 — Replacing container..."
docker stop "$CONTAINER_NAME" 2>/dev/null && echo "  Stopped old container" || echo "  No running container found"
docker rm   "$CONTAINER_NAME" 2>/dev/null && echo "  Removed old container" || true

# ── 4. Start new container ───────────────────────────────────────────────────
echo ""
echo "▶ Step 4/4 — Starting new container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "${HOST_PORT}:5000" \
  "$IMAGE"
echo "  ✓ Container started"

# Reclaim disk from the now-dangling previous image.
docker image prune -f >/dev/null 2>&1 || true

echo ""
echo "══════════════════════════════════════════"
echo "  ✅ Deploy complete!"
echo "  🌐 http://$(hostname -I | awk '{print $1}'):${HOST_PORT}"
echo "══════════════════════════════════════════"
echo ""
