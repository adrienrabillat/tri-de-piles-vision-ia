#!/bin/bash
# Lance le frontend React
# Usage: ./run_frontend.sh

echo "=== Battery Sorting Dashboard ==="
echo ""

cd "$(dirname "$0")/frontend"

# Installer les dependances si necessaire
if [ ! -d "node_modules" ]; then
    echo "[INFO] Installation des dependances..."
    npm install
fi

# Lancer le serveur de dev
REACT_APP_API_URL=http://localhost:8000 npm start
