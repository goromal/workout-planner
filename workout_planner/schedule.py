"""Rest-day helpers. Weekdays are indexed like datetime.weekday() (Monday = 0)."""

WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def parse_rest_days(config):
    """
    Read preferences.rest_days from the config as a set of weekday indices.

    Returns an empty set when the config, preferences, or rest_days is missing
    or empty. Raises ValueError for anything that isn't a list of weekday names.
    """
    preferences = (config or {}).get("preferences") or {}
    rest_days = preferences.get("rest_days")
    if rest_days is None:
        return frozenset()
    if not isinstance(rest_days, list):
        raise ValueError(
            f"preferences.rest_days must be a list of weekday names, got: {rest_days!r}"
        )

    indices = set()
    for name in rest_days:
        normalized = name.strip().lower() if isinstance(name, str) else None
        if normalized not in WEEKDAYS:
            raise ValueError(
                f"Unknown rest day {name!r} in preferences.rest_days. "
                f"Valid names: {', '.join(WEEKDAYS)}"
            )
        indices.add(WEEKDAYS.index(normalized))
    return frozenset(indices)


def is_rest_day(date, rest_days):
    return date.weekday() in rest_days


def training_days_remaining(today, rest_days):
    """Count non-rest days from today through Sunday, including today."""
    return sum(1 for day in range(today.weekday(), 7) if day not in rest_days)
