"""Scraper orchestration — run_search paginates and deduplicates listings.

``run_search`` contract:
- Iterates pages 1..max_pages, calling ``scraper.build_search_url(criteria, page)``
  and ``await fetcher.fetch(url)`` for each page.
- Stops early on the first page that returns zero listings (empty page).
- Deduplicates by ``(source_id, external_id)`` across all pages.
- Propagates ``ScraperBlocked`` to the caller without catching it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from realestate.scrapers.base import RawListing, Scraper, SearchCriteria


def _merge_detail(search: RawListing, detail: RawListing) -> RawListing:
    data = search.model_dump()
    detail_data = detail.model_dump()
    for key, value in detail_data.items():
        if key in {"source_id", "external_id", "url"}:
            continue
        if key == "images":
            data[key] = list(dict.fromkeys([*search.images, *detail.images]))
            continue
        if key == "raw":
            data[key] = search.raw or detail.raw
            continue
        if key == "description" and value:
            current = data.get(key)
            if (
                not current
                or str(current).rstrip().endswith("...")
                or len(str(value)) > len(str(current))
            ):
                data[key] = value
            continue
        if data.get(key) in (None, "", []):
            data[key] = value
    return RawListing(**data)


def _with_search_context(search: RawListing, detail: RawListing) -> RawListing:
    data = detail.model_dump()
    for key in ("city", "district", "street", "market", "lat", "lon"):
        if data.get(key) in (None, ""):
            data[key] = getattr(search, key)
    data["images"] = list(dict.fromkeys([*detail.images, *search.images]))
    data["attributes"] = {**search.attributes, **detail.attributes}
    investment_name = data["attributes"].get("investment_name")
    if investment_name and data.get("city") and data.get("street"):
        data["attributes"]["address"] = ", ".join([investment_name, data["city"], data["street"]])
    return RawListing(**data)


async def run_search(
    scraper: Scraper,
    fetcher,
    criteria: SearchCriteria,
    *,
    max_pages: int = 1,
    fetch_details: bool = False,
    on_log: Callable[[str], Awaitable[None]] | None = None,
) -> list[RawListing]:
    seen: set[tuple[str, str]] = set()
    seen_urls: set[str] = set()
    results: list[RawListing] = []
    for page in range(1, max_pages + 1):
        url = scraper.build_search_url(criteria, page)
        if url in seen_urls:
            break
        seen_urls.add(url)
        if on_log is not None:
            await on_log(f"Pobieram stronę {page}: {url}")
        html = await fetcher.fetch(url)
        page_listings = scraper.parse_search(html)
        if on_log is not None:
            await on_log(f"Strona {page}: znaleziono {len(page_listings)} ofert w {criteria.city}")
        if not page_listings:
            break
        for listing in page_listings:
            key = (listing.source_id, listing.external_id)
            if key in seen:
                continue
            seen.add(key)
            if fetch_details:
                if on_log is not None:
                    await on_log(f"Pobieram szczegóły: {listing.url}")
                detail_html = await fetcher.fetch(listing.url)
                detail = scraper.parse_detail(detail_html, listing.url)
                if isinstance(detail, list):
                    results.extend(_with_search_context(listing, item) for item in detail)
                    continue
                listing = _merge_detail(listing, detail)
            results.append(listing)
    return results
