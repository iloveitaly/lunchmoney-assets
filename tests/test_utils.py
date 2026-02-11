import pytest
from main import parse_currency, _extract_kbb_price_advisor_svg_url, _replace_query_param, _get_kbb_zipcode

def test_parse_currency():
    assert parse_currency("$1,234.56") == 1234.56
    assert parse_currency("1234") == 1234.0
    assert parse_currency("") == 0.0
    assert parse_currency(None) == 0.0

def test_extract_kbb_price_advisor_svg_url():
    raw_html = 'some stuff "href" : "upa.syndication.kbb.com/usedcar/test?param=1" more stuff'
    assert _extract_kbb_price_advisor_svg_url(raw_html) == "https://upa.syndication.kbb.com/usedcar/test?param=1"
    
    raw_html_with_http = 'some stuff upa.syndication.kbb.com/usedcar/test?param=1 more stuff'
    assert _extract_kbb_price_advisor_svg_url(raw_html_with_http) == "https://upa.syndication.kbb.com/usedcar/test?param=1"
    
    assert _extract_kbb_price_advisor_svg_url("") is None

def test_replace_query_param():
    url = "https://example.com/test?a=1&b=2"
    assert _replace_query_param(url, "a", "3") == "https://example.com/test?a=3&b=2"
    assert _replace_query_param(url, "c", "4") == "https://example.com/test?a=1&b=2&c=4"
    assert _replace_query_param("https://example.com/test", "a", "1") == "https://example.com/test?a=1"

def test_get_kbb_zipcode(monkeypatch):
    assert _get_kbb_zipcode({"zipcode": "12345"}) == "12345"
    assert _get_kbb_zipcode({"zipcode": " 12345 "}) == "12345"
    
    # Test default from config if missing in metadata
    # We'd need to mock config or environment variables
    pass
