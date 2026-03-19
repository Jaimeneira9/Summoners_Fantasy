#!/usr/bin/env bash
# Inicia backend (FastAPI :8000) y frontend (Next.js :3000) en paralelo.
# Ctrl+C detiene ambos.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

trap 'echo ""; echo "Deteniendo servicios..."; kill 0' EXIT

echo "Iniciando backend en :8000 ..."
(cd "$ROOT/backend" && source venv/bin/activate && uvicorn main:app --reload) &

echo "Iniciando frontend en :3000 ..."
(cd "$ROOT/frontend" && npm run dev) &

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "  Debug: Forzar refresco del mercado:"
echo "    curl -s http://localhost:8000/debug/market-refresh | jq"
echo ""
echo "  Ctrl+C para detener todo."
echo ""

wait
