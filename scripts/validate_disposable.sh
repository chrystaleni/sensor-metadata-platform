#!/usr/bin/env bash
# Run from the independent integration clone. Never targets an existing database.
set -euo pipefail
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
PYTHON=${PYTHON:-"$REPO_ROOT/backend/.venv/bin/python"}
if [ ! -x "$PYTHON" ]; then
  echo 'Set PYTHON to a virtualenv Python with backend/requirements.txt installed.' >&2
  exit 2
fi
docker info >/dev/null 2>&1 || { echo 'Docker unavailable. Run this script in your Mac Terminal with Docker Desktop running.' >&2; exit 2; }
IMAGE=${POSTGIS_TEST_IMAGE:-ghcr.io/cargosense/postgis:17-3.5-alpine}
docker image inspect "$IMAGE" >/dev/null || { echo "Download the approved PostGIS image first: $IMAGE" >&2; exit 2; }
RUN_ID=$("$PYTHON" -c 'import secrets; print(secrets.token_hex(6))')
RESULTS=$(mktemp -d /tmp/sensor-phase3-validation.XXXXXX)
CONTAINER_ID='';BACKEND_PID='';FRONTEND_PID=''
cleanup(){
  rc=$?
  trap - EXIT
  [ -z "$FRONTEND_PID" ] || kill "$FRONTEND_PID" 2>/dev/null || true
  [ -z "$BACKEND_PID" ] || kill "$BACKEND_PID" 2>/dev/null || true
  if [ -n "$CONTAINER_ID" ]; then
    docker logs "$CONTAINER_ID" >"$RESULTS/postgres.log" 2>&1 || true
    docker rm -f "$CONTAINER_ID" >/dev/null || true
  fi
  echo "Validation exit code: $rc; results: $RESULTS"
  exit "$rc"
}
trap cleanup EXIT
export POSTGRES_DB="sensor_validation_$RUN_ID" POSTGRES_USER=sensor_validation
export POSTGRES_PASSWORD=$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(32))')
CONTAINER_ID=$(docker run --pull=never --detach --name "sensor-validation-$RUN_ID" \
 --label sensor.disposable-validation=true \
 --tmpfs /var/lib/postgresql/data:rw \
 --publish 127.0.0.1::5432 \
 --env POSTGRES_DB --env POSTGRES_USER --env POSTGRES_PASSWORD "$IMAGE")
# TCP readiness excludes the temporary socket-only init server. Avoid racing its extension scripts.
ready=false
for ((attempt=0;attempt<90;attempt++)); do
 if docker exec "$CONTAINER_ID" pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then ready=true;break;fi
 sleep 1
done
[ "$ready" = true ] || { echo 'Disposable PostGIS did not become ready.' >&2; exit 1; }
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=$(docker port "$CONTAINER_ID" 5432/tcp | head -1 | awk -F: '{print $NF}')
# Only the newly created, tmpfs-backed container is addressed below.
docker exec "$CONTAINER_ID" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS postgis;' >"$RESULTS/database-init.log" 2>&1
if ! docker exec "$CONTAINER_ID" psql -U "$POSTGRES_USER" -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='template_postgis'" | grep -qx 1; then
 docker exec "$CONTAINER_ID" createdb -U "$POSTGRES_USER" --template=template0 template_postgis
fi
docker exec "$CONTAINER_ID" psql -U "$POSTGRES_USER" -d template_postgis -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS postgis;' >>"$RESULTS/database-init.log" 2>&1
export PYTHONDONTWRITEBYTECODE=1 DJANGO_DATABASE_ENGINE=postgis DJANGO_DEBUG=False
export DJANGO_SECRET_KEY=$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(64))')
export DJANGO_SETTINGS_MODULE=config.settings
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver
export METADATA_ACCESS_POLICY=metadata.access.NoAccessPolicy
unset METADATA_PLATFORM_DEPARTMENT_ID DEPARTMENT_ORGANISATION_BACKFILL || true
if [ -f /Applications/QGIS.app/Contents/Frameworks/libgdal.dylib ]; then
 export GDAL_LIBRARY_PATH=/Applications/QGIS.app/Contents/Frameworks/libgdal.dylib
 export GEOS_LIBRARY_PATH=/Applications/QGIS.app/Contents/Frameworks/libgeos_c.dylib
fi
cd "$REPO_ROOT/backend"
"$PYTHON" manage.py check >"$RESULTS/system-checks.log" 2>&1
"$PYTHON" manage.py migrate --noinput >"$RESULTS/migrations.log" 2>&1
"$PYTHON" manage.py makemigrations --check --dry-run >"$RESULTS/migration-drift.log" 2>&1
"$PYTHON" -m pytest -v --junitxml="$RESULTS/backend.xml" 2>&1 | tee "$RESULTS/backend.log"
cd "$REPO_ROOT/frontend"
npm test -- --run 2>&1 | tee "$RESULTS/frontend.log"
npm run lint 2>&1 | tee "$RESULTS/lint.log"
npm run build 2>&1 | tee "$RESULTS/build.log"
# Enable the real adapter only for the separate, explicitly disposable E2E fixture database.
export SENSOR_DISPOSABLE_VALIDATION=1 SENSOR_VALIDATION_INSTANCE="$RUN_ID"
export METADATA_ACCESS_POLICY=platform_security.access.DepartmentAccessPolicy
export E2E_PASSWORD=$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(24))')
export E2E_IMPORT_WORKBOOK="$RESULTS/import.xlsx"
cd "$REPO_ROOT/backend"
"$PYTHON" manage.py shell -c 'exec(open("../scripts/seed_disposable.py").read())' >"$RESULTS/seed.log" 2>&1
export METADATA_PLATFORM_DEPARTMENT_ID=$("$PYTHON" manage.py shell -c 'from local_departments.models import Department; print(Department.objects.get(organisation__code="platform").pk)' | tail -1)
export E2E_SOUTH_DEVICE_ID=$("$PYTHON" manage.py shell -c 'from metadata.models import PhysicalDevice; print(PhysicalDevice.objects.get(name="Restricted South Device").pk)' | tail -1)
# Let the OS select temporary loopback ports. The readiness nonce and owned process checks reject reused ports.
BACKEND_PORT=$("$PYTHON" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
FRONTEND_PORT=$("$PYTHON" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
export DJANGO_CSRF_TRUSTED_ORIGINS="http://127.0.0.1:$FRONTEND_PORT"
"$PYTHON" manage.py runserver "127.0.0.1:$BACKEND_PORT" --noreload >"$RESULTS/backend-server.log" 2>&1 & BACKEND_PID=$!
cd "$REPO_ROOT/frontend"
export VITE_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT"
./node_modules/.bin/vite --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort >"$RESULTS/frontend-server.log" 2>&1 & FRONTEND_PID=$!
export E2E_BASE_URL="http://127.0.0.1:$FRONTEND_PORT" E2E_PYTHON="$PYTHON" E2E_BACKEND_DIR="$REPO_ROOT/backend"
export E2E_RESULTS_DIR="$RESULTS/browser" E2E_JUNIT="$RESULTS/e2e.xml"
ready=false
for ((attempt=0;attempt<40;attempt++)); do
 kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null || { echo 'An owned test server exited; refusing to target a reused port.' >&2;exit 1; }
 if curl --fail --silent -D "$RESULTS/readiness-headers" --output /dev/null "$E2E_BASE_URL/ready/" && grep -qi "X-Sensor-Validation-Instance: $RUN_ID" "$RESULTS/readiness-headers";then ready=true;break;fi
 sleep 1
done
[ "$ready" = true ] || { echo 'Disposable application servers did not become ready.' >&2;exit 1; }
# Install browser once beforehand: npm --prefix frontend exec -- playwright install chromium
npm run test:e2e 2>&1 | tee "$RESULTS/e2e.log"
echo 'All disposable validation stages passed.'
