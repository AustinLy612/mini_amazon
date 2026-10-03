#!/usr/bin/env bash
# Run in the EXISTING course container, not the macOS terminal.
set -euo pipefail
cd "$(dirname "$0")"
project_db=mini_amazon_carts_dev
if [[ "$(uname -s)" != Linux ]]; then
  echo 'Run this script in the VS Code course-container terminal.' >&2
  exit 1
fi
for command in poetry psql createdb python3; do
  command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }
done
: "${PGHOST:?Course PGHOST is missing}"
: "${PGPORT:?Course PGPORT is missing}"
: "${PGUSER:?Course PGUSER is missing}"
: "${PGPASSWORD:?Course PGPASSWORD is missing}"
if [[ -e .flaskenv ]]; then
  echo '.flaskenv already exists; stopping without overwriting configuration.' >&2
  exit 1
fi
existing=$(psql -X -v ON_ERROR_STOP=1 -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = 'mini_amazon_carts_dev'")
if [[ "$existing" == 1 ]]; then
  echo 'mini_amazon_carts_dev already exists. Nothing was deleted. Inspect it before continuing.' >&2
  exit 1
fi
# Per-command setting: does not change global Poetry configuration.
POETRY_VIRTUALENVS_IN_PROJECT=true poetry install --no-interaction
# createdb fails if another process has already created this name. Never DROP.
createdb "$project_db"
psql -X -v ON_ERROR_STOP=1 -1 -d "$project_db" -f db/create.sql
(cd db/data && psql -X -v ON_ERROR_STOP=1 -1 -d "$project_db" -f ../load.sql)
psql -X -v ON_ERROR_STOP=1 -d "$project_db" -f db/carts_schema.sql
psql -X -v ON_ERROR_STOP=1 -d "$project_db" -f db/carts_demo.sql
# Generate local credentials from the course environment without printing them.
poetry run python - <<'PY'
import os
import secrets
from dotenv import set_key
fd = os.open('.flaskenv', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(fd)
values = {
    'FLASK_APP': 'amazon.py', 'FLASK_RUN_HOST': '0.0.0.0',
    'FLASK_RUN_PORT': '8080', 'SECRET_KEY': secrets.token_hex(32),
    'DB_NAME': 'mini_amazon_carts_dev',
    'DB_HOST': os.environ['PGHOST'], 'DB_PORT': os.environ['PGPORT'],
    'DB_USER': os.environ['PGUSER'], 'DB_PASSWORD': os.environ['PGPASSWORD'],
}
for key, value in values.items():
    set_key('.flaskenv', key, value)
PY
printf '%s\n' 'Project database initialized. Start with: poetry run flask run' 'Open http://localhost:8080 and log in using the skeleton demo account.'
