# Sensor Metadata Management Platform

The Sensor Metadata Management Platform is a modular monolith for managing sensor and infrastructure metadata for HMY317 at the University of Cyprus, in collaboration with KIOS CoE.

## Problem domains

- **Measurements** — metadata about sensor measurements.
- **Physical Devices** — metadata about physical sensing devices.
- **Network Elements** — metadata about the network infrastructure connecting devices.

## Technology stack

- Frontend: React and Vite
- Backend: FastAPI
- Database: PostgreSQL with PostGIS
- Development environment: Docker Compose
- Automated testing: GitHub Actions

## Architecture

The system follows a three-tier modular monolith architecture: a React/Vite frontend, a FastAPI backend organized around the three problem domains, and a PostgreSQL/PostGIS data tier. The tiers are developed and run together as one application system.

## Team responsibilities

- **Chrystaleni Argyrou** — architecture, infrastructure, security, and integration
- **Antri Kelli** — frontend and UI/UX
- **Argyris Fellas** — backend metadata management

## Development status

Initial setup. Frameworks and application functionality have not yet been initialized.
