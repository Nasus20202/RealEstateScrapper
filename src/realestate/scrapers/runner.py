from __future__ import annotations

from realestate.scrapers.base import RawListing, Scraper, SearchCriteria


async def run_search(
    scraper: Scraper,
    fetcher,
    criteria: SearchCriteria,
    *,
    max_pages: int = 1,
) -> list[RawListing]:
    seen: set[tuple[str, str]] = set()
    results: list[RawListing] = []
    for page in range(1, max_pages + 1):
        url = scraper.build_search_url(criteria, page)
        html = await fetcher.fetch(url)
        page_listings = scraper.parse_search(html)
        if not page_listings:
            break
        for listing in page_listings:
            key = (listing.source_id, listing.external_id)
            if key in seen:
                continue
            seen.add(key)
            results.append(listing)
    return results
