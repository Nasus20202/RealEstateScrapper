from realestate.scrapers.districts import district_from_investment, district_from_text


def test_district_from_text_uses_canonical_districts_before_investment_overrides():
    assert district_from_text("Nowa inwestycja w Gdańsku Jasień") == "Jasień"
    assert district_from_text("Apartamenty, Orunia Św. Wojciech Lipce") == (
        "Orunia-Św. Wojciech-Lipce"
    )


def test_district_from_investment_does_not_guess_from_known_slug():
    assert district_from_investment("lawendowe-wzgorza") is None
    assert district_from_investment("atal-przystan-sobieszewo") is None
    assert district_from_investment("skycity-gdynia") is None


def test_district_from_investment_reads_district_present_in_text():
    assert district_from_investment("Apartamenty Jasień") == "Jasień"
    assert district_from_investment("Mieszkania Gdańsk Brzeźno") == "Brzeźno"


def test_district_from_text_fuzzy_matches_nearby_district_names():
    assert district_from_text("Mieszkania Gdańsk Jasien") == "Jasień"
    assert district_from_text("Apartamenty Gdańsk Przymoze") == "Przymorze"
    assert district_from_text("Mieszkania Gdynia Redlowo") == "Redłowo"


def test_district_from_text_fuzzy_matches_multiword_district_names():
    assert district_from_text("Gdańsk Orunia Sw Wojciech Lipce") == ("Orunia-Św. Wojciech-Lipce")
    assert district_from_text("Gdynia Pustki Cisowskie Demptowo") == ("Pustki Cisowskie-Demptowo")


def test_district_from_investment_does_not_use_legacy_slug_override():
    assert district_from_investment("greenline") is None
    assert district_from_investment("brabank") is None
