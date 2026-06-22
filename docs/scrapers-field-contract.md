# RawListing Per-Source Field Contract

Documents which `RawListing` fields are reliably populated at **search-results level**
for each scraper, and the semantics of ambiguous fields.

---

## 1. Otodom (`source_id = "otodom"`)

Parses `__NEXT_DATA__` JSON embedded in the page HTML.

| Field | Populated? | Notes |
|---|---|---|
| `source_id` | Always | `"otodom"` |
| `external_id` | Always | Numeric listing `id` from JSON |
| `url` | Always | Built from `slug` or `href`; absolute |
| `title` | Always | `item.title` |
| `price` | Usually | `None` when `hidePrice=true`; Decimal |
| `area_m2` | Usually | `areaInSquareMeters`; float |
| `rooms` | Usually | Mapped from string enum (ONE/TWO/…) or int |
| `floor` | Sometimes | Mapped from string enum or int; may be absent |
| `city` | Usually | `location.address.city.name` |
| `district` | Sometimes | From `reverseGeocoding.locations` (level=district) |
| `market` | Best-effort | See heuristic below; **NOT authoritative** |
| `posted_at` | Usually | Parsed from `dateCreated` (ISO-like string); 1 listing/page may lack it |
| `images` | Usually | From `images[].large/medium/url` |
| `raw` | Always | Full item dict |

### `market` heuristic (best-effort)
- `source` URN contains `"obido"` → `"primary"` (developer listings via Obido platform)
- `source` is any other non-empty string → `"secondary"` (agency/partner feed)
- `source` is `None`/absent → `None` (cannot determine)

The `source` field is an internal Otodom URN (e.g. `urn:partner:esticrm`,
`urn:site:local`). This mapping is an inference — the scraper does NOT receive an
explicit market flag at search-results level.

### Other notes
- `price` is `None` whenever `hidePrice` is `true` in the JSON item.
- `posted_at` is parsed defensively with `datetime.fromisoformat`; malformed values
  silently yield `None`.

---

## 2. Nieruchomości-online (`source_id = "nieruchomosci-online"`)

Parses DOM tiles via `selectolax` (CSS selectors).

| Field | Populated? | Notes |
|---|---|---|
| `source_id` | Always | `"nieruchomosci-online"` |
| `external_id` | Always | Numeric ID extracted from `/(\d+)\.html` URL pattern |
| `url` | Always | Absolute; resolved from tile `<a>` href |
| `title` | Always | Text of `h2 a` |
| `price` | Usually | Parsed from `.primary-display span[0]`; Polish formatting (NBSP, comma decimal) |
| `area_m2` | Usually | Parsed from `.primary-display span[1]`; Polish `m²` format |
| `rooms` | Sometimes | From `.attributes__box--item` containing `"pokoi"` |
| `floor` | Sometimes | From `.attributes__box--item` containing `"piętro"` |
| `city` | Sometimes | Last word of `.province` text |
| `district` | Sometimes | First word of `.province` text when >1 part |
| `market` | Reliable | Read directly from `data-market-type` attribute (`"primary"` / `"secondary"`) |
| `posted_at` | Never | Not available at search-results level |
| `images` | Never | Not scraped at search level |
| `raw` | Never | Not stored (DOM-based scraper) |

### `market` semantics
`data-market-type` is a reliable attribute set by the site itself — no inference needed.
Values are exactly `"primary"` or `"secondary"`; anything else → `None`.

### Other notes
- Price and area parsing strips Polish non-breaking spaces (`\xa0`) and handles comma
  as decimal separator. Invalid values yield `None`.
- `build_search_url` encodes city name but does NOT translate `min_price`, `max_price`,
  `min_area`, `max_area`, or `min_rooms` into query parameters — **filtering is
  best-effort** and must be enforced downstream.

---

## 3. Hossa (`source_id = "hossa"`)

Parses rendered Hossa cards and then expands each investment through the public
`/api/apartments/` endpoint. With `fetch_details=True`, output rows are **individual
flats**, not investment placeholders.

| Field | Populated? | Notes |
|---|---|---|
| `source_id` | Always | `"hossa"` |
| `external_id` | Always | Detail rows use `apartment-{id}` from API |
| `url` | Always | Flat URL with `#id={id}&inv={investment}` |
| `title` | Always | Investment slug/name + flat number |
| `price` | Usually | From API `price` |
| `area_m2` | Usually | From API `area_usable` / `area` |
| `rooms` | Usually | From API `rooms` |
| `floor` | Usually | From API `floor` |
| `city` | Usually | From search-card context or API fields |
| `district` | Sometimes | From search-card place when available |
| `street` | Usually | From API `building`, e.g. `Leśmiana 4`, `Przytulna 33` |
| `market` | Always | Hardcoded `"primary"` — Hossa is a developer-only site |
| `posted_at` | Never | `None` |
| `images` | Usually | From API media + search-card image context |
| `raw` | Always for API detail rows | Original API item |

### Hossa address rules

The exact postal street must come from the flat API (`building`) when available.
Search-card address is only context and must not override a more precise flat address.
Examples:

- `street = "Leśmiana 4"`, `city = "Gdańsk"`
- `street = "Przytulna 33"`, `city = "Gdańsk"`

Investment/marketing names may be kept in `attributes.investment_name` or
`attributes.address` for display, but geocoding uses only country/city/street.

---

## General Notes

### `build_search_url` is best-effort
Not all `SearchCriteria` fields are translated into query parameters:

| Criterion | Otodom | Nieruchomości-online | Hossa |
|---|---|---|---|
| `city` | Yes | Yes | Ignored (single market) |
| `min_price` / `max_price` | Yes | **No** | **No** |
| `min_area` / `max_area` | Yes | **No** | **No** |
| `min_rooms` | Yes (roomsNumber) | **No** | **No** |
| `market` | **No** | **No** | N/A (always primary) |

**Hard filtering must be enforced downstream** (DB query layer / API search layer),
not by relying on the scraper URL.

### `external_id` stability
`external_id` is designed to be stable per source across re-scrapes:
- otodom: numeric listing `id` from JSON
- nieruchomosci-online: numeric ID from URL path
- hossa: API apartment ID prefixed with `apartment-`

Use `(source_id, external_id)` as the deduplication key.

### Developer scraper guardrails

Developer scrapers must not emit investment cards as listings when detail expansion
does not produce actual flats. If a detail page yields no flat with at least one
unit-level signal (`price`, `area_m2`, `rooms`, `floor`, or a stable flat ID), return
an empty list instead of an investment placeholder.

Do not hardcode investment metadata such as streets, districts, or coordinates in
scraper modules. These values must come from the site DOM/API for the current run.

### Geocoding address query

When a listing has an exact street/building, the geocoding query is:

`Polska, {city}, {street}`

District is intentionally omitted in that case because developer sites often put
marketing names there (for example `Welocity Wiczlino`). If street is missing, the
fallback is:

`Polska, {city}, {district}`
