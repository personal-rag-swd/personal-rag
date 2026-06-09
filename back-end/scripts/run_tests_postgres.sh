#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
ROOT_DIR=$(cd "${BACKEND_DIR}/.." && pwd)
COMPOSE_FILE="${ROOT_DIR}/docker-compose.test.yml"

export TEST_POSTGRES_USER="${TEST_POSTGRES_USER:-postgres}"
export TEST_POSTGRES_PASSWORD="${TEST_POSTGRES_PASSWORD:-postgres}"
export TEST_POSTGRES_DB="${TEST_POSTGRES_DB:-personal_rag_test}"
export TEST_POSTGRES_PORT="${TEST_POSTGRES_PORT:-5433}"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://${TEST_POSTGRES_USER}:${TEST_POSTGRES_PASSWORD}@localhost:${TEST_POSTGRES_PORT}/${TEST_POSTGRES_DB}}"

cleanup() {
  if [[ "${KEEP_TEST_POSTGRES:-0}" != "1" ]]; then
    docker compose -f "${COMPOSE_FILE}" down -v >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

docker compose -f "${COMPOSE_FILE}" up -d postgres-test

until docker compose -f "${COMPOSE_FILE}" exec -T postgres-test \
  pg_isready -U "${TEST_POSTGRES_USER}" -d "${TEST_POSTGRES_DB}" >/dev/null 2>&1; do
  sleep 1
done

cd "${BACKEND_DIR}"
uv run pytest "$@"
