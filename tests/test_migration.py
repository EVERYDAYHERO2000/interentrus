"""Upgrades remove only explicitly retired sensors belonging to this integration."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "isp_migration",
    Path(__file__).resolve().parents[1] / "custom_components/isp_balance/migration.py",
)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_registry_cleanup_preserves_retained_and_unrelated_entities():
    def entity(key, platform="isp_balance", domain="sensor", account="account"):
        return SimpleNamespace(
            unique_id=f"{account}_{key}",
            entity_id=f"{domain}.{account}_{key}",
            platform=platform,
            domain=domain,
        )

    removed = [entity(key) for key in migration.REMOVED_SENSOR_KEYS]
    kept = [
        entity("balance"),
        entity("monthly_fee"),
        entity("daily_cost"),
        entity("needs_top_up", domain="binary_sensor"),
        entity("tariff", platform="other"),
        entity("tariff", account="other"),
    ]
    assert set(migration.obsolete_entity_ids(removed + kept, "account", "isp_balance")) == {
        e.entity_id for e in removed
    }
