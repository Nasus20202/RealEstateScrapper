from urllib.parse import urlparse

_UI_MARKERS = (
    "logo",
    "icon",
    "sprite",
    "placeholder",
    "facebook",
    "instagram",
    "youtube",
    "linkedin",
    "cookie",
)


def looks_like_listing_image(url: str) -> bool:
    if not url or url.startswith("data:"):
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    path = parsed.path.lower()
    if path.endswith((".svg", ".ico")):
        return False
    if any(marker in path for marker in _UI_MARKERS):
        return False
    return True


def unique_listing_images(urls: list[str]) -> list[str]:
    result: list[str] = []
    seen_full_size: set[str] = set()
    for url in urls:
        if not looks_like_listing_image(url):
            continue
        normalized = url.replace("-mini.", ".")
        if "-mini." not in url:
            seen_full_size.add(normalized)
        if normalized in seen_full_size and "-mini." in url:
            continue
        if url not in result:
            result.append(url)
    return result
