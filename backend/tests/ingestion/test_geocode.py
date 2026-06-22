import httpx
import pytest

from realestate.ingestion.geocode import NominatimGeocoder, build_address_query


def test_build_address_query_requires_city():
    assert build_address_query(street="al. X", district="Wrzeszcz", city=None) is None
    assert build_address_query(street=None, district=None, city=None) is None


def test_build_address_query_uses_country_city_street():
    q = build_address_query(street="al. Grunwaldzka 1", district="Wrzeszcz", city="Gdańsk")
    assert q == "Polska, Gdańsk, al. Grunwaldzka 1"


def test_build_address_query_uses_precise_street_without_investment_name():
    q = build_address_query(
        street="Przytulna 33",
        district="Wiszące Ogrody",
        city="Gdańsk",
    )
    assert q == "Polska, Gdańsk, Przytulna 33"


def test_build_address_query_avoids_investment_name_when_street_is_available():
    q = build_address_query(
        street="Jana Kazimierza 12",
        district="Welocity Wiczlino",
        city="Gdynia",
    )
    assert q == "Polska, Gdynia, Jana Kazimierza 12"


def _geocoder(handler) -> NominatimGeocoder:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return NominatimGeocoder(
        base_url="https://nominatim.example",
        user_agent="test/1.0",
        min_delay_seconds=0.0,
        timeout_seconds=5.0,
        client=client,
    )


async def test_geocode_parses_first_result():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "test/1.0"
        assert request.url.params["q"] == "Gdańsk, Polska"
        return httpx.Response(200, json=[{"lat": "54.352", "lon": "18.6466"}])

    geo = _geocoder(handler)
    assert await geo.geocode("Gdańsk, Polska") == (54.352, 18.6466)


async def test_geocode_returns_none_on_empty_and_caches():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=[])

    geo = _geocoder(handler)
    assert await geo.geocode("Nowhere, Polska") is None
    assert await geo.geocode("Nowhere, Polska") is None  # cached
    assert calls["n"] == 1


async def test_geocode_swallows_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    geo = _geocoder(handler)
    assert await geo.geocode("X, Polska") is None


@pytest.mark.parametrize("payload", [[{"lat": "bad"}], [{}], "notalist"])
async def test_geocode_tolerates_malformed_payload(payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    geo = _geocoder(handler)
    assert await geo.geocode("X, Polska") is None
