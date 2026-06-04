from core.company_match import find_all_mentioned, fuzzy_match_one


COMPANIES = ["Asian Paints", "Infosys", "Reliance Industries Ltd", "Tata Consultancy Services"]


def test_fuzzy_match_aliases():
    assert fuzzy_match_one("tcs", COMPANIES) == "Tata Consultancy Services"
    assert fuzzy_match_one("infy", COMPANIES) == "Infosys"
    assert fuzzy_match_one("reliance", COMPANIES) == "Reliance Industries Ltd"


def test_find_all_mentioned_keeps_multiple_companies():
    found = find_all_mentioned("Compare TCS with Infosys and Reliance", COMPANIES)
    assert found == ["Tata Consultancy Services", "Infosys", "Reliance Industries Ltd"]

