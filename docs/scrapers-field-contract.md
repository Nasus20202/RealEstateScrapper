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

Parses hossa.gda.pl which is a **Vue SPA**. Static HTML contains only navigation links;
investment/flat cards are rendered client-side and are NOT available in raw HTML.

| Field | Populated? | Notes |
|---|---|---|
| `source_id` | Always | `"hossa"` |
| `external_id` | Always | URL slug (e.g. `"nowe-mieszkania-gdansk"`) |
| `url` | Always | Absolute category/landing page URL |
| `title` | Always | Link text from anchor |
| `price` | Never | `None` — developer site; prices not in static HTML |
| `area_m2` | Never | `None` — not available at this level |
| `rooms` | Never | `None` — not available at this level |
| `floor` | Never | `None` — not available at this level |
| `city` | Sometimes | Inferred from slug (e.g. `gdansk` → `"Gdańsk"`) |
| `district` | Never | `None` |
| `market` | Always | Hardcoded `"primary"` — Hossa is a developer-only site |
| `posted_at` | Never | `None` |
| `images` | Never | Not scraped at search level |
| `raw` | Never | Not stored |

### Critical: Hossa rows are OFFER-CATEGORY links, NOT individual flats

`parse_search` returns **landing/investment-category pages** (e.g.
`https://www.hossa.gda.pl/nowe-mieszkania-gdansk/`), NOT individual flat listings.
The fixture typically yields 2–5 rows, each representing a city or investment category.

**Implications for Plan 3 normalizer:**
- Hossa rows MUST be treated distinctly from flat-level listings (otodom, nieruchomosci-online).
- They MUST NOT be cross-deduplicated against flat listings by price/area/rooms
  (all of those are `None`).
- The normalizer or search layer MUST either filter them out or route them through
  a separate pipeline that fetches the investment landing page and extracts individual flats.
- `external_id` is a slug, not a numeric offer ID — do not compare with otodom/n-o IDs.

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
- hossa: URL slug (category page slug)

Use `(source_id, external_id)` as the deduplication key.
