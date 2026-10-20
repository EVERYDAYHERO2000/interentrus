"""Identify obsolete entities from previous integration versions."""

REMOVED_SENSOR_KEYS = {
    "sufficient_until",
    "minimum_payment",
    "month_expenses",
    "tariff",
    "remaining_days",
}


def obsolete_entity_ids(entries, account_unique_id, platform):
    obsolete = {f"{account_unique_id}_{key}" for key in REMOVED_SENSOR_KEYS}
    return [
        entity.entity_id
        for entity in entries
        if entity.platform == platform
        and entity.domain == "sensor"
        and entity.unique_id in obsolete
    ]
