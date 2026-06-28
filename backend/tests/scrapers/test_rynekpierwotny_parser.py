from realestate.scrapers.rynekpierwotny import _district_from_address


def test_district_from_address_rejects_street_like_part():
    assert _district_from_address("Gdańsk, ul. Dywizjonu 303 3", "Gdańsk") is None


def test_district_from_address_keeps_real_district():
    assert _district_from_address("Gdańsk, Wrzeszcz", "Gdańsk") == "Wrzeszcz"


def test_district_from_address_rejects_voivodeship():
    assert _district_from_address("Gdańsk, pomorskie", "Gdańsk") is None
