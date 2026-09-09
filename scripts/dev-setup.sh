#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Prescripto — Dev Environment Setup ==="
echo ""

# 1. Check Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed. Install it first: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running. Start Docker first."
    exit 1
fi

# 2. Create backend .env from .env.example if missing
if [ ! -f "$ROOT_DIR/backend/.env" ]; then
    echo "[1/4] Creating backend/.env from .env.example..."
    cp "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/backend/.env"
    echo "      -> Edit backend/.env to add your MISTRAL_API_KEY"
else
    echo "[1/4] backend/.env already exists, skipping."
fi

# 3. Create client .env from .env.example if missing
if [ ! -f "$ROOT_DIR/client/.env" ]; then
    echo "[2/4] Creating client/.env from .env.example..."
    cp "$ROOT_DIR/client/.env.example" "$ROOT_DIR/client/.env"
else
    echo "[2/4] client/.env already exists, skipping."
fi

# 4. Start Docker services
echo "[3/4] Starting Docker services (PostgreSQL, Qdrant, pgAdmin)..."
docker compose -f "$ROOT_DIR/docker-compose.dev.yml" up -d

# 5. Wait for services to be healthy
echo "[4/4] Waiting for services to be ready..."

echo -n "  PostgreSQL... "
until docker exec prescripto-postgres pg_isready -U prescripto &> /dev/null; do
    sleep 1
done
echo "OK"

echo -n "  Qdrant... "
until curl -sf http://localhost:6333/healthz &> /dev/null; do
    sleep 1
done
echo "OK"

echo ""
echo "=== Dev environment ready ==="
echo ""
echo "Services:"
echo "  PostgreSQL : localhost:5432  (user: prescripto / password: password)"
echo "  Qdrant     : http://localhost:6333/dashboard"
echo "  pgAdmin    : http://localhost:5050  (admin@prescripto.fr / prescripto_dev_admin)"
echo ""
echo "Next steps:"
echo "  1. Add your MISTRAL_API_KEY in backend/.env"
echo "  2. cd backend && uv sync --extra dev && uv run alembic upgrade head"
echo "  3. cd client && pnpm install"
echo "  4. pnpm dev"
