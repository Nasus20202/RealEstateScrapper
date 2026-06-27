from realestate.scrapers.districts import district_from_investment


def test_district_from_known_developer_investment_slug():
    assert district_from_investment("lawendowe-wzgorza") == "Jasień"
    assert district_from_investment("atal-przystan-sobieszewo") == "Wyspa Sobieszewska"
    assert district_from_investment("skycity-gdynia") == "Działki Leśne"


def test_district_from_known_developer_investment_name():
    assert district_from_investment("Nowe Południe") == "Orunia Górna-Gdańsk Południe"
    assert district_from_investment("Nadmorski Dwór") == "Brzeźno"
    assert district_from_investment("Legionów121") == "Redłowo"
