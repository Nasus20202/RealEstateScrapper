from realestate.scrapers.morizon import _fix_street_from_url, _split_location


def test_split_location_keeps_street_out_of_district():
    city, district, street = _split_location("23 Marca, Sopot, pomorskie")

    assert city == "Sopot"
    assert district is None
    assert street == "23 Marca"


def test_split_location_moves_street_like_district_to_street():
    city, district, street = _split_location("Aleja Grunwaldzka, Gdańsk, pomorskie")

    assert city == "Gdańsk"
    assert district is None
    assert street == "Aleja Grunwaldzka"


def test_fix_street_from_url_moves_morizon_slug_street_out_of_district():
    district, street = _fix_street_from_url(
        "https://www.morizon.pl/oferta/sprzedaz-mieszkanie-gdynia-bieszczadzka-26m2-mzn2046710447",
        "Bieszczadzka",
        None,
    )

    assert district is None
    assert street == "Bieszczadzka"
