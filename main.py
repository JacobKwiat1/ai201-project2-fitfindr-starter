from tests import test_tools
from tools import search_listings, suggest_outfit, create_fit_card

if __name__ == '__main__':
    test_tools.test_search_returns_results(search_listings)
    test_tools.test_search_price_filter(search_listings)
    test_tools.test_search_empty_results(search_listings)

    test_tools.test_suggest_returns_string(suggest_outfit)
    test_tools.test_suggest_empty_wardrobe(suggest_outfit)

    test_tools.test_fitcard_returns_string(create_fit_card)
    test_tools.test_fitcard_empty_outfit(create_fit_card)
    test_tools.test_fitcard_whitespace_outfit(create_fit_card)

    print("All tests passed.")
