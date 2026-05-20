#!/usr/bin/env bash
set -e

# This script exports the OpenAPI JSON schema from the FastAPI app
# It must be run from the repository root directory.

echo "Exporting OpenAPI schema..."
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Set a dummy REDIS_URL and DATABASE_URL so main.py doesn't crash on import if it initializes clients globally
export REDIS_URL="redis://localhost:6379/0"
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"

python3 -c "
import json
import sys
from backend.app.main import app

schema = app.openapi()
with open('openapi.json', 'w') as f:
    json.dump(schema, f, indent=2)
"

echo "Success! Schema exported to openapi.json"
