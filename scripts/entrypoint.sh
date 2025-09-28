#!/usr/bin/env bash
set -euo pipefail

# Wait a bit for Cloud SQL socket/GCS mount if needed
sleep 1

# Apply database migrations
python manage.py migrate --noinput

# Collect static files (no-op if using GCS storages)
python manage.py collectstatic --noinput || true

# Start Gunicorn
exec gunicorn legalai.wsgi:application \
  --bind 0.0.0.0:${PORT:-8080} \
  --workers ${WEB_CONCURRENCY:-3} \
  --timeout 120
