from __future__ import annotations

import re
import unicodedata

_INVESTMENT_DISTRICTS: dict[str, str] = {
    "atal-jasieny": "Jasień",
    "atal-przystan-sobieszewo": "Wyspa Sobieszewska",
    "atal-symbioza": "Wielki Kack",
    "atal-zawislanska": "Orunia-Św. Wojciech-Lipce",
    "brabank": "Śródmieście",
    "botanica": "Jelitkowo",
    "dobre-miejsce": "Jasień",
    "foresteria": "Jasień",
    "galaktyczna": "Osowa",
    "greenline": "Jasień",
    "kobieli": "Jasień",
    "lawendowe-wzgorza": "Jasień",
    "legionow121": "Redłowo",
    "leszczynskich": "Jasień",
    "malokacka": "Mały Kack",
    "miasto-gdy": "Działki Leśne",
    "nadmorski-dwor": "Brzeźno",
    "nadmotlawie": "Śródmieście",
    "nowa-dabrowa": "Dąbrowa",
    "nowa-walowa": "Młode Miasto",
    "nowe-kolibki": "Orłowo",
    "nowe-poludnie": "Orunia Górna-Gdańsk Południe",
    "off-miasto": "Dolne Miasto",
    "osiedle-przyjemne": "Łostowice",
    "pas-startowy": "Zaspa",
    "przystan-letnica": "Letnica",
    "puenta-morena": "Morena",
    "rosa": "Jasień",
    "rosa-residence": "Jasień",
    "skycity-gdynia": "Działki Leśne",
    "smolna-sopot": "Karlikowo",
    "szumilas": "Jasień",
    "ukryte": "Śródmieście",
    "wita77": "Wrzeszcz",
    "wendy": "Młode Miasto",
}


def district_from_investment(value: str | None) -> str | None:
    key = _slugify(value)
    if not key:
        return None
    for prefix, district in _INVESTMENT_DISTRICTS.items():
        if key == prefix or key.startswith(f"{prefix}-") or prefix in key:
            return district
    return None


def _slugify(value: str | None) -> str:
    if not value:
        return ""
    folded = unicodedata.normalize("NFKD", value.strip().lower().replace("ł", "l"))
    ascii_value = folded.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
