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

Initial setup. The Django backend provides a health endpoint, and the React frontend is initialized. Metadata management functionality is not yet implemented.

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

Run these commands from the `backend/` directory.

Create and activate a virtual environment, then install the backend dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start the Django development server:

```sh
python manage.py runserver
```

Run the backend tests with pytest:

```sh
pytest
```

The unauthenticated `GET /health/` endpoint returns HTTP 200 with `{"status": "ok"}`.

### PostgreSQL/PostGIS development database

The database runs as a separate Docker Compose service. The example credentials and Django settings below are for local development only.

From the repository root, copy the example environment file and start the database:

```sh
cp .env.example .env
docker compose up -d db
docker compose ps
```

Wait until the `db` service reports `healthy`. You can check it directly with:

```sh
docker compose exec db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT PostGIS_Full_Version();"'
```

To connect Django, set `DJANGO_DATABASE_ENGINE=postgis` in `.env`, then load the variables into your shell from the repository root:

```sh
set -a
source .env
set +a
```

When running Django in PostGIS mode directly on your computer, GeoDjango also needs GDAL, GEOS, and PROJ installed on the host. On macOS, install them with `brew install gdal geos proj`; on Debian/Ubuntu, use `sudo apt-get install binutils libproj-dev gdal-bin libgdal-dev libgeos-dev`. SQLite mode and its tests do not need these system libraries.

Run migrations from `backend/` after activating the backend virtual environment:

```sh
cd backend
python manage.py check
python manage.py migrate
```

Stop the database while keeping its data with `docker compose stop db` or `docker compose down`. To intentionally delete its stored data, run `docker compose down --volumes` from the repository root.

The backend defaults to SQLite, so existing tests need no Docker service. To explicitly select SQLite and run them from `backend/`:

```sh
DJANGO_DATABASE_ENGINE=sqlite python -m pytest -v
```

## Continuous integration

GitHub Actions runs automated checks on every branch push, on pull requests targeting `main`, and when manually started with `workflow_dispatch`. The backend job installs `backend/requirements.txt`, runs Django's system check, and runs pytest. The frontend job installs from `frontend/package-lock.json`, then runs the test suite, ESLint, and a production build. Team members can view workflow runs in the repository's **Actions** tab or check results on a pull request.
