# Dodawanie nowej wtyczki scrapera

Scrapery są wtyczkami implementującymi protokół `Scraper` z `src/realestate/scrapers/base.py`. Rejestracja odbywa się przez wywołanie `register(scraper)` na poziomie modułu — framework wykrywa i ładuje zarejestrowane wtyczki automatycznie.

---

## 1. Zaimplementuj protokół `Scraper`

Utwórz nowy plik w `src/realestate/scrapers/`, np. `src/realestate/scrapers/moj_portal.py`.

```python
from realestate.scrapers.base import RawListing, Scraper, SearchCriteria, register


class MojPortalScraper:
    source_id = "moj-portal"
    display_name = "Mój Portal"

    def build_search_url(self, criteria: SearchCriteria, page: int) -> str:
        """Zwróć URL strony z wynikami wyszukiwania dla podanych kryteriów i numeru strony."""
        base = "https://www.moj-portal.pl/mieszkania"
        return f"{base}?city={criteria.city}&page={page}"

    def parse_search(self, html: str) -> list[RawListing]:
        """Parsuj HTML strony wyników i zwróć listę RawListing."""
        results: list[RawListing] = []
        # ... parsowanie HTML ...
        return results

    def parse_detail(self, html: str, url: str) -> RawListing:
        """Parsuj HTML strony szczegółów oferty."""
        # ... parsowanie HTML ...
        return RawListing(
            source_id=self.source_id,
            external_id="123",
            url=url,
            title="Przykładowe mieszkanie",
        )


# Rejestracja — musi być na poziomie modułu
register(MojPortalScraper())
```

---

## 2. Wymagane atrybuty i metody

| Element | Typ | Opis |
|---|---|---|
| `source_id` | `str` | Unikalny identyfikator źródła (np. `"otodom"`, `"moj-portal"`). Używany jako klucz w rejestrze i bazie danych. |
| `display_name` | `str` | Wyświetlana nazwa źródła (np. `"Otodom"`, `"Mój Portal"`). |
| `build_search_url(criteria, page)` | `str` | Zwraca URL do pobrania strony wyników. `page` zaczyna się od 1. |
| `parse_search(html)` | `list[RawListing]` | Parsuje HTML strony wyników. Zwraca listę ofert. Może zwrócić pustą listę (koniec paginacji). |
| `parse_detail(html, url)` | `RawListing` | Parsuje HTML strony szczegółów oferty. |

---

## 3. Obiekt `RawListing`

`RawListing` to pydantic DTO z następującymi polami (wszystkie oprócz `source_id`, `external_id`, `url`, `title` są opcjonalne):

```python
class RawListing(BaseModel):
    source_id: str          # ID źródła
    external_id: str        # Unikalny ID oferty w tym źródle (stabilny przy re-scrapowaniu)
    url: str                # Absolutny URL oferty
    title: str              # Tytuł ogłoszenia
    price: Decimal | None = None
    area_m2: float | None = None
    rooms: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    city: str | None = None
    district: str | None = None
    street: str | None = None
    market: str | None = None    # "primary" lub "secondary"
    description: str | None = None
    images: list[str] = []
    posted_at: datetime | None = None
    raw: dict = {}               # Surowe dane źródłowe (opcjonalnie)
```

Para `(source_id, external_id)` musi być unikalna i stabilna — służy do deduplikacji przy inkrementalnym synchronizowaniu.

---

## 4. Rejestracja wtyczki

Wywołaj `register(scraper)` na poziomie modułu (poza klasą, po jej definicji):

```python
register(MojPortalScraper())
```

Framework importuje moduły scrapera automatycznie — upewnij się, że plik jest w `src/realestate/scrapers/` i zaimportuj go w `src/realestate/scrapers/__init__.py` (lub sprawdź mechanizm auto-discovery).

---

## 5. Testy offline

Dodaj fixture HTML w `tests/fixtures/data/`:

```
tests/fixtures/data/moj_portal_search.html.gz    # spakowana strona wyników
tests/fixtures/data/moj_portal_detail.html.gz    # spakowana strona szczegółów
```

Napisz testy offline (bez sieci):

```python
import gzip
from pathlib import Path
from realestate.scrapers.moj_portal import MojPortalScraper

FIXTURES = Path(__file__).parent / "fixtures" / "data"


def test_parse_search():
    html = gzip.decompress((FIXTURES / "moj_portal_search.html.gz").read_bytes()).decode()
    scraper = MojPortalScraper()
    results = scraper.parse_search(html)
    assert len(results) > 0
    assert results[0].source_id == "moj-portal"
    assert results[0].external_id


def test_parse_detail():
    html = gzip.decompress((FIXTURES / "moj_portal_detail.html.gz").read_bytes()).decode()
    scraper = MojPortalScraper()
    listing = scraper.parse_detail(html, "https://www.moj-portal.pl/oferta/123")
    assert listing.title
    assert listing.url
```

---

## 6. Kontrakt pól

Każdy scraper ma różną dostępność pól w wynikach wyszukiwania vs. na stronie szczegółów. Udokumentuj, które pola są zawsze/zwykle/czasami/nigdy dostępne, analogicznie do istniejącego kontraktu: [`docs/scrapers-field-contract.md`](scrapers-field-contract.md).

Przykład: `nieruchomosci-online` nie wypełnia `images` ani `posted_at` przy parsowaniu wyników — dopiero strona szczegółów może je zawierać. Filtrowanie po cenie/powierzchni nie jest encodowane w URL przez ten scraper — odbywa się downstream w warstwie SQL.
