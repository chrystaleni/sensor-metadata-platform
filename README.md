# Sensor Metadata Management Platform

The Sensor Metadata Management Platform is a modular monolith for managing sensor and infrastructure metadata for HMY317 at the University of Cyprus, in collaboration with KIOS CoE.

## Problem domains

- **Measurements** — metadata about sensor measurements.
- **Physical Devices** — metadata about physical sensing devices.
- **Network Elements** — metadata about the network infrastructure connecting devices.

## Technology stack

- Frontend: React and Vite
- Backend: Django and Django REST Framework
- Database: PostgreSQL with PostGIS
- Spatial functionality: GeoDjango
- Development environment: Docker Compose
- Automated testing: pytest
- CI: GitHub Actions

The backend framework was changed from FastAPI to Django following a client request from KIOS CoE. Django REST Framework is the team's implementation choice for providing REST APIs to the React frontend.

## Architecture

The system follows a three-tier modular monolith architecture: a React/Vite frontend, a Django backend organized around the three problem domains, and a PostgreSQL/PostGIS data tier. GeoDjango provides the implemented spatial fields and validation. The tiers are developed and run together as one application system.

## Team responsibilities

- **Chrystaleni Argyrou** — architecture, infrastructure, security, and integration
- **Antri Kelli** — frontend and UI/UX
- **Argyris Fellas** — backend metadata management

## Development status

The Django backend implements metadata management for Measurements, Physical Devices and Network Elements. Argyris's contribution includes shared controlled lists, PostGIS geometry, search and filtering, atomic Excel import and audited logical deletion. See the [backend handover](docs/development/argyris-backend.md) for setup, API examples, validation results and the shared security integration boundary. This local integration branch also incorporates the existing Organisation, session/role/membership and React implementations, scoped API keys and full Compose services. Read the [integration and validation guide](docs/development/phase3-integration.md) before starting. Full PostGIS/E2E validation of the combined branch remains required; historical passing results are not proof of this revision.

## Quick start (run locally with Docker)

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine with Compose) and Git. Nothing else needs to be installed.

```sh
git clone https://github.com/chrystaleni/sensor-metadata-platform.git
cd sensor-metadata-platform
cp .env.example .env
```

Edit `.env` and set your own `POSTGRES_PASSWORD` and a unique `DJANGO_SECRET_KEY` (the backend refuses the insecure example value). Also add:

```dotenv
METADATA_ACCESS_POLICY=platform_security.access.DepartmentAccessPolicy
```

Build, create the database and the shared Platform Department:

```sh
docker compose build
docker compose up -d db
docker compose run --rm backend python manage.py migrate --noinput
docker compose run --rm backend python manage.py provision_platform_department
```

Copy the Department ID printed by the last command into `.env` as `METADATA_PLATFORM_DEPARTMENT_ID=<id>`, then create your first System Administrator (you will be asked for a password) and start the application:

```sh
docker compose run --rm backend python manage.py configure_platform_user admin --create --role SYSTEM_ADMIN
docker compose up -d backend frontend
```

Open <http://localhost:8080> and sign in. More users can then be created in **Administration**.

Useful commands: `docker compose logs -f backend` to see logs, `docker compose stop` to pause, and `docker compose up -d backend frontend` to start again. `docker compose down` keeps your data; `docker compose down --volumes` deletes it. The map needs an internet connection for its basemap tiles. See the [integration guide](docs/development/phase3-integration.md) for details.

## Frontend development

Run these commands from the `frontend/` directory. Install dependencies and start the development server:

```sh
npm install
npm run dev
```

Run the frontend tests and lint check:

```sh
npm test -- --run
npm run lint
```

Create a production build with:

```sh
npm run build
```

## Backend development

PostgreSQL with PostGIS is the standard database for local development and CI. Copy the root example file once; Django reads the repository-root `.env` automatically through `python-dotenv`, regardless of the current directory. Existing operating-system or CI environment variables take precedence.

From the repository root, create the local environment file and start PostgreSQL/PostGIS:

```sh
cp .env.example .env
docker compose up -d db
docker compose ps
```

Wait for `db` to report `healthy`. Verify PostgreSQL and PostGIS with:

```sh
docker compose exec db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT PostGIS_Version();"'
```

GeoDjango in PostGIS mode requires GDAL, GEOS, and PROJ on the host. On macOS install them with `brew install gdal geos proj`; on Debian/Ubuntu use `sudo apt-get install binutils libproj-dev gdal-bin libgdal-dev libgeos-dev`.

From `backend/`, create and activate a virtual environment, install dependencies, and run checks and migrations:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py check
# Fresh database only; existing data requires the approved Organisation backfill.
python manage.py migrate
```

Start the Django development server from `backend/`:

```sh
python manage.py runserver
```

Run the backend tests from `backend/`:

```sh
python -m pytest -v
```

GitHub Actions starts PostgreSQL 16 with PostGIS 3.7, waits for its health check, then runs Django checks, migrations, and all backend tests against that service.

The metadata models and migrations require PostgreSQL/PostGIS. Use the PostGIS configuration for the complete backend and test suite; SQLite does not support these spatial migrations. The integration test asserts the configured PostGIS backend and executes `SELECT PostGIS_Version()`.

The unauthenticated `GET /health/` endpoint returns HTTP 200 with `{"status": "ok"}`.

Stop Docker without deleting the database data with `docker compose stop db` or `docker compose down`. To intentionally delete the data volume, run `docker compose down --volumes` from the repository root.

## Metadata integration configuration

The metadata API defaults to `metadata.access.NoAccessPolicy`. A session alone does not grant metadata access; Chrystaleni's adapter supplies Department scopes and shared-list management permission. Session, CSRF bootstrap, login/logout and capability context endpoints are registered; see the [session contract](docs/development/session-authentication.md).

PR #31 changes `METADATA_PLATFORM_DEPARTMENT_ID` from an implicit ID 1 to explicit configuration. With that change present, set the approved existing Platform Department ID in the root `.env`. Missing, invalid, non-positive or out-of-range values leave Platform unconfigured. A setting does not create a Department, move catalog values or grant access.

The optional demo fixtures use Platform ID 1 only in an empty isolated demo database. Do not infer the shared Platform ID from those fixture values. Operational data belongs to its selected business Department; shared catalog values belong to Platform.

`METADATA_DEPARTMENT_MODEL` defaults to `local_departments.Department`. Agree the shared model and migration strategy before using a shared database. `METADATA_ACCESS_POLICY` must point to the team's real installed adapter for authorized metadata workflows.

See the [API contract and permission boundary](docs/development/argyris-api-examples.md), [backend handover](docs/development/argyris-backend.md) and [database upgrade runbook](docs/development/argyris-database.md). The local integration retains the PR #31 explicit configuration and PR #32 replacement migration. Follow the [integration guide](docs/development/phase3-integration.md) for Organisation backfill, role provisioning, safe Compose startup and disposable validation.

## Continuous integration

GitHub Actions runs automated checks on every branch push, on pull requests targeting `main`, and when manually started with `workflow_dispatch`. The backend job installs `backend/requirements.txt`, runs Django's system check, applies migrations, checks for missing migrations and runs pytest. The frontend job installs from `frontend/package-lock.json`, then runs the test suite, ESLint, and a production build. Team members can view workflow runs in the repository's **Actions** tab or check results on a pull request.

The local integration additionally configures real browser–Django–PostGIS validation in the backend job, using a new disposable container and retaining test evidence. This updated workflow has not executed remotely until the branch is pushed.
