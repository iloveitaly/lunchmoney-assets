from main import _get_kbb_zipcode
from scrapers.utils import (
    extract_kbb_price_advisor_svg_url,
    parse_currency,
    replace_query_param,
)


def test_parse_currency():
    assert parse_currency("$1,234.56") == 1234.56
    assert parse_currency("1234") == 1234.0
    assert parse_currency("") == 0.0
    assert parse_currency(None) == 0.0

def test_extract_kbb_price_advisor_svg_url():
    raw_html = 'some stuff "href" : "upa.syndication.kbb.com/usedcar/test?param=1" more stuff'
    assert extract_kbb_price_advisor_svg_url(raw_html) == "https://upa.syndication.kbb.com/usedcar/test?param=1"
    
    raw_html_with_http = 'some stuff upa.syndication.kbb.com/usedcar/test?param=1 more stuff'
    assert extract_kbb_price_advisor_svg_url(raw_html_with_http) == "https://upa.syndication.kbb.com/usedcar/test?param=1"
    
    assert extract_kbb_price_advisor_svg_url("") is None

def test_replace_query_param():
    url = "https://example.com/test?a=1&b=2"
    assert replace_query_param(url, "a", "3") == "https://example.com/test?a=3&b=2"
    assert replace_query_param(url, "c", "4") == "https://example.com/test?a=1&b=2&c=4"
    assert replace_query_param("https://example.com/test", "a", "1") == "https://example.com/test?a=1"


def test_get_kbb_zipcode(monkeypatch):
    assert _get_kbb_zipcode({"zipcode": "12345"}) == "12345"
    assert _get_kbb_zipcode({"zipcode": " 12345 "}) == "12345"


def test_parse_private_party_value_from_kbb_svg():
    from scrapers.utils import parse_private_party_value_from_kbb_svg

    sample_svg = """
    <svg>
      <text>Private Party Value</text>
      <text>$22,350</text>
    </svg>
    """
    assert parse_private_party_value_from_kbb_svg(sample_svg) == 22350.0
    assert parse_private_party_value_from_kbb_svg("") is None
    assert parse_private_party_value_from_kbb_svg("<svg><text>No match</text></svg>") is None


def test_url_hash():
    from scrapers.utils import url_hash

    h = url_hash("https://example.com/test")
    assert isinstance(h, str)
    assert len(h) == 12

