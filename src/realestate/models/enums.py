from enum import StrEnum


class MarketType(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class ListingStatus(StrEnum):
    ACTIVE = "active"
    GONE = "gone"
