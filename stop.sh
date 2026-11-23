#!/bin/bash
# Stop all AI Video Director services
cd "$(dirname "$0")"

echo "Stopping services..."

# Stop frontend (Vite on :5174)
for pid in $(netstat -ano 2>/dev/null | grep ":5174.*LISTENING" | awk '{print $NF}' | sort -u); do
    taskkill //F //PID "$pid" 2>/dev/null && echo "  Stopped frontend (PID $pid)"
done

# Stop backend (uvicorn on :8000)
for pid in $(netstat -ano 2>/dev/null | grep ":8000.*LISTENING" | awk '{print $NF}' | sort -u); do
    taskkill //F //PID "$pid" 2>/dev/null && echo "  Stopped backend (PID $pid)"
done

# Stop ComfyUI container
if docker ps --filter name=ai-video-gen -q 2>/dev/null | grep -q .; then
    docker compose down 2>/dev/null && echo "  Stopped ComfyUI container"
fi

echo "All services stopped."
