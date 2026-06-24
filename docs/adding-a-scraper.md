# Adding a New Scraper Plugin

Scrapers are plugins implementing the `Scraper` protocol from `backend/src/realestate/scrapers/base.py`. Registration is done by calling `register(scraper)` at the module level — the framework detects and loads registered plugins automatically.

---

## 1. Implement the `Scraper` Protocol

Create a new file in `backend/src/realestate/scrapers/`, e.g. `backend/src/realestate/scrapers/my_portal.py`.

```python
from realestate.scrapers.base import RawListing, Scraper, SearchCriteria, register


class MyPortalScraper:
    source_id = "my-portal"
    display_name = "My Portal"

    def build_search_url(self, criteria: SearchCriteria, page: int) -> str:
        """Return the URL of the search results page for the given criteria and page number."""
        base = "https://www.my-portal.pl/mieszkania"
        return f"{base}?city={criteria.city}&page={page}"

    def parse_search(self, html: str) -> list[RawListing]:
        """Parse the search results page HTML and return a list of RawListing."""
        results: list[RawListing] = []
        # ... HTML parsing ...
        return results

    def parse_detail(self, html: str, url: str) -> RawListing:
        """Parse the listing detail page HTML."""
        # ... HTML parsing ...
        return RawListing(
            source_id=self.source_id,
            external_id="123",
            url=url,
            title="Example listing",
        )


# Registration — must be at module level
register(MyPortalScraper())
```

---

## 2. Required Attributes and Methods

| Element | Type | Description |
|---|---|---|
| `source_id` | `str` | Unique source identifier (e.g. `"otodom"`, `"my-portal"`). Used as a key in the registry and database. |
| `display_name` | `str` | Display name of the source (e.g. `"Otodom"`, `"My Portal"`). |
| `build_search_url(criteria, page)` | `str` | Returns the URL to fetch the results page. `page` starts at 1. |
| `parse_search(html)` | `list[RawListing]` | Parses the search results page HTML. Returns a list of listings. May return an empty list (end of pagination). |
| `parse_detail(html, url)` | `RawListing` | Parses the listing detail page HTML. |

---

## 3. `RawListing` Object

`RawListing` is a pydantic DTO with the following fields (all except `source_id`, `external_id`, `url`, `title` are optional):

```python
class RawListing(BaseModel):
    source_id: str          # Source ID
    external_id: str        # Unique listing ID within the source (stable across re-scrapes)
    url: str                # Absolute listing URL
    title: str              # Listing title
    price: Decimal | None = None
    area_m2: float | None = None
    rooms: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    city: str | None = None
    district: str | None = None
    street: str | None = None
    market: str | None = None    # "primary" or "secondary"
    description: str | None = None
    images: list[str] = []
    posted_at: datetime | None = None
    raw: dict = {}               # Raw source data (optional)
```

The pair `(source_id, external_id)` must be unique and stable — it is used for deduplication during incremental syncing.

---

## 4. Plugin Registration

Call `register(scraper)` at the module level (outside the class, after its definition):

```python
register(MyPortalScraper())
```

The framework imports scraper modules automatically — ensure the file is in `backend/src/realestate/scrapers/` and import it in `backend/src/realestate/scrapers/__init__.py` (or check the auto-discovery mechanism).

---

## 5. Offline Tests

Add HTML fixtures in `tests/fixtures/data/`:

```
tests/fixtures/data/my_portal_search.html.gz    # gzipped search results page
tests/fixtures/data/my_portal_detail.html.gz    # gzipped detail page
```

Write offline tests (no network):

```python
import gzip
from pathlib import Path
from realestate.scrapers.my_portal import MyPortalScraper

FIXTURES = Path(__file__).parent / "fixtures" / "data"


def test_parse_search():
    html = gzip.decompress((FIXTURES / "my_portal_search.html.gz").read_bytes()).decode()
    scraper = MyPortalScraper()
    results = scraper.parse_search(html)
    assert len(results) > 0
    assert results[0].source_id == "my-portal"
    assert results[0].external_id


def test_parse_detail():
    html = gzip.decompress((FIXTURES / "my_portal_detail.html.gz").read_bytes()).decode()
    scraper = MyPortalScraper()
    listing = scraper.parse_detail(html, "https://www.my-portal.pl/offer/123")
    assert listing.title
    assert listing.url
```

---

## 6. Field Contract

Each scraper has different field availability in search results vs. detail page. Document which fields are always/usually/sometimes/never available, analogous to the existing contract: [`docs/scrapers-field-contract.md`](scrapers-field-contract.md).

Example: `nieruchomosci-online` does not populate `images` or `posted_at` when parsing results — only the detail page may contain them. Price/area filtering is not encoded in the URL by this scraper — it happens downstream in the SQL layer.
