\set ON_ERROR_STOP on

-- Run from the repository root against a local development database.
-- psql --dbname=sensor_metadata_dev --file=docs/testing/role-screenshots/schema.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS documentation;

CREATE TABLE IF NOT EXISTS documentation.role_screenshots (
    role text PRIMARY KEY,
    filename text NOT NULL,
    content_type text NOT NULL,
    image bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
