#!/bin/bash
# Lance le serveur FastAPI d'inference
# Usage: ./run_server.sh

echo "=== Battery Sorting API Server ==="
echo ""

# Verifier les dependances
python3 -m pip install -q --break-system-packages fastapi uvicorn python-multipart Pillow numpy ultralytics 2>/dev/null

# Lancer le serveur
cd "$(dirname "$0")"
python3 -m uvicorn backend.inference_server:app --host 0.0.0.0 --port 8000 --reload
