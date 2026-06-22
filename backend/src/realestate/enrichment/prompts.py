from __future__ import annotations

from realestate.llm.base import ChatMessage
from realestate.models.listing import Listing

_SYSTEM = (
    "Jesteś asystentem analizującym oferty nieruchomości. "
    "Zwracasz wyłącznie obiekt JSON o kluczach: "
    '"summary" (zwięzłe polskie streszczenie, max 2 zdania) oraz '
    '"features" (obiekt cech wywnioskowanych z tekstu, np. balkon, stan, winda).'
)


def build_enrichment_messages(listing: Listing) -> list[ChatMessage]:
    parts = [
        f"Tytuł: {listing.title}",
        f"Miasto: {listing.city or '-'}",
        f"Dzielnica: {listing.district or '-'}",
        f"Pokoje: {listing.rooms if listing.rooms is not None else '-'}",
        f"Metraż (m2): {listing.area_m2 if listing.area_m2 is not None else '-'}",
        f"Cena: {listing.price if listing.price is not None else '-'}",
        f"Opis: {listing.description or '-'}",
    ]
    return [
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(role="user", content="\n".join(parts)),
    ]
