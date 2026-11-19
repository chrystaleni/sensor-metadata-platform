"""Graph/state checks without connecting to any database."""
from django.db.migrations.loader import MigrationLoader
from metadata.tests.test_identifier_upgrade import (
    OriginalMigrationLoader, BASELINE, ORGANISATION_UPGRADES, SECURITY_UPGRADES,
)


def test_historical_downgrade_has_exact_security_descendants():
    for loader in (MigrationLoader(None), OriginalMigrationLoader(None, replace_migrations=False)):
        loader.graph.validate_consistency()
        descendants = set(loader.graph.backwards_plan(BASELINE))
        assert {key for key in descendants if key[0] == 'platform_security'} == set(SECURITY_UPGRADES)
        assert {key for key in descendants if key[0] == 'local_departments'} == set(ORGANISATION_UPGRADES)
        assert ('api_keys','0001_initial') not in descendants


def test_original_and_replacement_graphs_produce_identical_combined_model_state():
    normal = MigrationLoader(None)
    original = OriginalMigrationLoader(None, replace_migrations=False)
    assert normal.project_state().models == original.project_state().models
