import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("configured_id", "expected"),
    [
        (None, None),
        ("", None),
        ("invalid", None),
        ("0", None),
        ("-1", None),
        (str(2**63), None),
        ("1", 1),
        ("42", 42),
    ],
)
def test_platform_department_id_requires_valid_explicit_configuration(monkeypatch, configured_id, expected):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("DJANGO_DATABASE_ENGINE", "sqlite")
    if configured_id is None:
        monkeypatch.delenv("METADATA_PLATFORM_DEPARTMENT_ID", raising=False)
    else:
        monkeypatch.setenv("METADATA_PLATFORM_DEPARTMENT_ID", configured_id)

    settings_file = Path(__file__).resolve().parents[2] / "config" / "settings.py"
    assert runpy.run_path(str(settings_file))["METADATA_PLATFORM_DEPARTMENT_ID"] == expected
