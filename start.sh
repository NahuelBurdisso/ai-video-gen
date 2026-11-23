#!/bin/bash
# One-click startup for AI Video Director
# Boots: ComfyUI (Docker) + Ollama + FastAPI backend + Vite frontend

set -e
cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}[start]${NC} $1"; }
ok()  { echo -e "${GREEN}[  OK ]${NC} $1"; }
warn(){ echo -e "${YELLOW}[WARN]${NC} $1"; }
fail(){ echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    log "Shutting down..."
    [ -n "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null
    log "Done."
}
trap cleanup EXIT

# ─── 1. Check prerequisites ───────────────────────────────────────────

log "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || fail "Docker not found. Install Docker Desktop."
command -v python >/dev/null 2>&1 || fail "Python not found."
command -v node >/dev/null 2>&1   || fail "Node.js not found."
python -c "import huggingface_hub" 2>/dev/null || pip install -q huggingface_hub[cli]
export HF_HUB_CACHE="D:/hf_cache"

# ─── 2. Ollama ─────────────────────────────────────────────────────────

log "Checking Ollama..."
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama running"
else
    warn "Ollama not running. Attempting to start..."
    if command -v ollama >/dev/null 2>&1; then
        ollama serve &>/dev/null &
        sleep 3
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            ok "Ollama started"
        else
            fail "Could not start Ollama. Start it manually: ollama serve"
        fi
    else
        fail "Ollama not installed. Get it from https://ollama.com"
    fi
fi

# Check director LLM (override with OLLAMA_MODEL)
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma3:27b}"
if curl -s http://localhost:11434/api/tags 2>/dev/null | grep -q "\"$OLLAMA_MODEL\""; then
    ok "Ollama model $OLLAMA_MODEL available"
else
    warn "$OLLAMA_MODEL not found. Pulling (this takes a while)..."
    ollama pull "$OLLAMA_MODEL"
fi

# ─── 3. ComfyUI Docker ────────────────────────────────────────────────

log "Checking ComfyUI container..."
if docker ps --filter name=ai-video-gen --format "{{.Names}}" 2>/dev/null | grep -q "ai-video-gen"; then
    ok "ComfyUI container running"
else
    log "Starting ComfyUI container..."
    docker compose up -d --build 2>&1 | tail -3
    log "Waiting for ComfyUI to initialize..."
    for i in $(seq 1 60); do
        if curl -s http://localhost:8188/system_stats >/dev/null 2>&1; then
            break
        fi
        sleep 2
    done
    if curl -s http://localhost:8188/system_stats >/dev/null 2>&1; then
        ok "ComfyUI ready on :8188"
    else
        warn "ComfyUI not responding yet (may still be downloading models). Continuing..."
    fi
fi

# ─── 4. Backend (FastAPI) ──────────────────────────────────────────────

log "Starting backend..."

# Install deps if needed
pip install -q -r ui/backend/requirements.txt 2>/dev/null

# Kill any existing backend on :8000
if command -v lsof >/dev/null 2>&1; then
    lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
else
    # Windows fallback
    for pid in $(netstat -ano 2>/dev/null | grep ":8000.*LISTENING" | awk '{print $NF}' | sort -u); do
        taskkill //F //PID "$pid" 2>/dev/null || true
    done
fi
sleep 1

cd ui
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload &>/dev/null &
BACKEND_PID=$!
cd ..

# Wait for backend
for i in $(seq 1 15); do
    if curl -s http://localhost:8000/api/health >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
if curl -s http://localhost:8000/api/health >/dev/null 2>&1; then
    ok "Backend ready on :8000"
else
    fail "Backend failed to start. Check logs."
fi

# ─── 5. Frontend (Vite) ───────────────────────────────────────────────

log "Starting frontend..."

cd ui/frontend
if [ ! -d "node_modules" ]; then
    log "Installing frontend dependencies..."
    npm install --silent 2>/dev/null
fi

npx vite --port 5174 &>/dev/null &
FRONTEND_PID=$!
cd ../..

sleep 2
if curl -s http://localhost:5174 >/dev/null 2>&1; then
    ok "Frontend ready on :5174"
else
    # Vite sometimes takes longer
    sleep 3
fi

# ─── 6. Ready ─────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  AI Video Director — All Systems Online   ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo -e "  UI:       ${CYAN}http://localhost:5174${NC}"
echo -e "  Backend:  http://localhost:8000"
echo -e "  ComfyUI:  http://localhost:8188"
echo -e "  Ollama:   http://localhost:11434"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all services."
echo ""

# Open browser
if command -v start >/dev/null 2>&1; then
    start http://localhost:5174 2>/dev/null
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://localhost:5174 2>/dev/null
fi

# Keep alive
wait
