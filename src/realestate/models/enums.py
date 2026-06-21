from enum import StrEnum


class MarketType(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class ListingStatus(StrEnum):
    ACTIVE = "active"
    GONE = "gone"


class ScrapeRunStatus(StrEnum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    FAILED = "failed"


def enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """``values_callable`` for SQLAlchemy ``Enum``: bind the StrEnum ``.value``.

    Without this, SQLAlchemy binds the enum member NAME (e.g. ``"ACTIVE"``), which
    does NOT match the lowercase labels the Alembic migrations create for the
    Postgres enum (e.g. ``"active"``). ``create_all`` stays self-consistent (names on
    both sides), so the mismatch only surfaces when the schema is built via migrations
    (production / docker). Binding ``.value`` keeps the ORM aligned with the migrations.
    """
    return [member.value for member in enum_cls]
