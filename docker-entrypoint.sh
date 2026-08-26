#!/bin/sh
# Single-service entrypoint: apply database migrations (when a database is
# configured) and then start the process selected by REGUROLOG_PROCESS.
set -e

if [ -n "${DATABASE_URL}" ]; then
  echo "Running database migrations..."
  alembic -c apps/api/alembic.ini upgrade head
fi

exec python -m regurolog_api.process
