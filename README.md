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
