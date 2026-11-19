# Local integration validation status — 19 November 2026

**Verdict: NOT READY for publication or delivery until PostGIS/E2E validation passes.**

Branch: `integration/phase3-platform`. Base: `65d35dee3d4d9370b52a1c47122b419bf57b8955`.
This report describes the independent clone, not published main.

| Check | Result | Evidence / scope |
|---|---|---|
| Python syntax | PASS | 91 backend/runner Python files parsed |
| Django system checks | PASS | No issues |
| Migration graph and model state | PASS | Normal and original-only states equal; exact security descendants checked |
| Migration drift | PASS | `makemigrations --check --dry-run`: no changes |
| Database-free backend tests | PASS | 36 passed, zero failures/errors/skips in selected run |
| Backend suite discovery | COLLECTED | 574 tests; not executed as a complete suite |
| Frontend unit/component tests | PASS | 70 passed in 13 test files |
| ESLint | PASS | No reported errors/warnings; npm prints an existing proxy configuration warning |
| Production frontend build | PASS | Vite build, including bundled Leaflet |
| Compose configuration | PASS | `docker compose config --quiet`; YAML syntax valid |
| Disposable runner syntax | PASS | `bash -n scripts/validate_disposable.sh` |
| Playwright scenarios | COLLECTED | Three real-browser workflow definitions; no browser–Django execution |
| Docker image builds / service startup | BLOCKED | Docker socket permission denied |
| Fresh/upgrade/reverse PostGIS migrations | BLOCKED | No accessible disposable PostGIS runtime |
| Full backend permission/key/ORM tests | BLOCKED | Require disposable PostGIS |
| Complete React–Django–PostGIS E2E | BLOCKED | Same runtime dependency; mocked tests are not substituted |
| Updated GitHub Actions | NOT RUN | Local changes have not been pushed |
| Existing migration files | PASS | Metadata/Organisation files match PR #33; security files match b83db60 |
| Original repository | PASS | Clean `preview-antri-frontend` at `2f1a3e2`; no changes made |

Agent test logs: `/tmp/sensor-phase3-agent-validation-d2fo2z9e`.
The XML records the selected database-free run only. Historical 436-test results
are not reused as evidence for this revision. PostGIS rollback, concurrency,
expiry and ownership behavior remain unverified at runtime on the combined code.

## Next action

From the Mac Terminal with Docker Desktop available:

```sh
cd "$(cat /tmp/sensor-active-integration-path)"
npm --prefix frontend exec -- playwright install chromium
PYTHON=/Users/chrysta/Desktop/Sensor-Platform-New/sensor-metadata-platform/backend/.venv/bin/python bash scripts/validate_disposable.sh
```

The runner uses only a new random database/container on tmpfs. It pins requests
to its test instance using an ephemeral readiness marker and overrides deployment
URLs/cookie settings. It keeps logs/XML/tracebacks and removes only its own container.
Review every failure before enabling real access in a non-disposable deployment.
Existing installations still require backups and an approved Organisation mapping.

No push, GitHub PR/review changes, or remote merge has been performed. Browser
Organisation/user administration beyond the existing scope remains an operator
workflow; no such frontend feature is claimed. This is not a complete Phase 1–3
requirements certification or a production hardening assessment.
