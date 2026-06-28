from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class District:
    name: str
    city: str
    aliases: tuple[str, ...] = ()


CANONICAL_CITIES = ("Gdańsk", "Gdynia", "Sopot")

CANONICAL_DISTRICTS = (
    District("Aniołki", "Gdańsk"),
    District("Brzeźno", "Gdańsk"),
    District("Brętowo", "Gdańsk"),
    District("Chełm", "Gdańsk"),
    District("Jasień", "Gdańsk"),
    District("Letnica", "Gdańsk"),
    District("Morena", "Gdańsk"),
    District("Oliwa", "Gdańsk"),
    District("Orunia", "Gdańsk"),
    District("Orunia-Św. Wojciech-Lipce", "Gdańsk", ("Orunia Sw Wojciech Lipce",)),
    District("Piecki-Migowo", "Gdańsk"),
    District("Przymorze", "Gdańsk"),
    District("Śródmieście", "Gdańsk"),
    District("Ujeścisko", "Gdańsk"),
    District("Ujeścisko-Łostowice", "Gdańsk"),
    District("Wrzeszcz", "Gdańsk"),
    District("Zaspa", "Gdańsk"),
    District("Żabianka", "Gdańsk"),
    District("Działki Leśne", "Gdynia"),
    District("Karwiny", "Gdynia"),
    District("Mały Kack", "Gdynia"),
    District("Orłowo", "Gdynia"),
    District("Pustki Cisowskie-Demptowo", "Gdynia"),
    District("Redłowo", "Gdynia"),
    District("Witomino", "Gdynia"),
    District("Dolny Sopot", "Sopot"),
    District("Górny Sopot", "Sopot"),
)


def location_key(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip().casefold().replace("ł", "l")
    folded = unicodedata.normalize("NFKD", value)
    ascii_value = folded.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_value)).strip()


def _lookup_cities() -> dict[str, str]:
    return {location_key(city): city for city in CANONICAL_CITIES}


def _lookup_districts() -> dict[str, District]:
    lookup: dict[str, District] = {}
    for district in CANONICAL_DISTRICTS:
        for value in (district.name, *district.aliases):
            lookup[location_key(value)] = district
    return lookup


CITY_BY_KEY = _lookup_cities()
DISTRICT_BY_KEY = _lookup_districts()
