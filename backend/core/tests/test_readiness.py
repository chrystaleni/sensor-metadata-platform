from unittest.mock import Mock, patch
import pytest
from django.db import OperationalError
from django.test import RequestFactory
from core.views import ready


@pytest.mark.parametrize("pending,expected", [([], 200), ([object()], 503)])
def test_readiness_checks_the_plan_without_applying_it(pending, expected):
    executor = Mock()
    executor.migration_plan.return_value = pending
    with patch("django.db.connection.ensure_connection"), patch("django.db.migrations.executor.MigrationExecutor", return_value=executor):
        response = ready(RequestFactory().get("/ready/"))
    assert response.status_code == expected
    executor.migrate.assert_not_called()


def test_readiness_does_not_disclose_database_errors():
    with patch("django.db.connection.ensure_connection", side_effect=OperationalError("private detail")):
        response = ready(RequestFactory().get("/ready/"))
    assert response.status_code == 503
    assert b"private" not in response.content


def test_disposable_readiness_marker_is_explicit_and_not_a_credential(monkeypatch):
    monkeypatch.setenv("SENSOR_DISPOSABLE_VALIDATION", "1")
    monkeypatch.setenv("SENSOR_VALIDATION_INSTANCE", "test-run-id")
    executor = Mock();executor.migration_plan.return_value = []
    with patch("django.db.connection.ensure_connection"), patch("django.db.migrations.executor.MigrationExecutor", return_value=executor):
        response = ready(RequestFactory().get("/ready/"))
    assert response["X-Sensor-Validation-Instance"] == "test-run-id"
