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

The system follows a three-tier modular monolith architecture: a React/Vite frontend, a Django backend organized around the three problem domains, and a PostgreSQL/PostGIS data tier. GeoDjango will support spatial functionality. The tiers are developed and run together as one application system.

## Team responsibilities

- **Chrystaleni Argyrou** — architecture, infrastructure, security, and integration
- **Antri Kelli** — frontend and UI/UX
- **Argyris Fellas** — backend metadata management

## Development status

The Django backend implements metadata management for Measurements, Physical Devices and Network Elements. Argyris's contribution includes shared controlled lists, PostGIS geometry, search and filtering, atomic Excel import and audited logical deletion. See the [backend handover](docs/development/argyris-backend.md) for setup, API examples, validation results and the shared security integration boundary. The React frontend is initialized; authentication, production authorization and the final frontend integration are separate team work.

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

## Continuous integration

GitHub Actions runs automated checks on every branch push, on pull requests targeting `main`, and when manually started with `workflow_dispatch`. The backend job installs `backend/requirements.txt`, runs Django's system check, applies migrations, checks for missing migrations and runs pytest. The frontend job installs from `frontend/package-lock.json`, then runs the test suite, ESLint, and a production build. Team members can view workflow runs in the repository's **Actions** tab or check results on a pull request.
