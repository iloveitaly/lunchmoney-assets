import pytest

from scrapers import FirecrawlScraper, SpiderScraper, build_scraper
from scrapers.base import Scraper
from scrapers.spider import _extract_property_price_from_html


def test_spider_implements_protocol():
    scraper = SpiderScraper(api_key="test-key")
    assert isinstance(scraper, Scraper)


def test_build_scraper_selection(monkeypatch):
    monkeypatch.setenv("SPIDER_API_KEY", "test-spider-key")
    monkeypatch.setenv("SCRAPER_BACKEND", "spider")
    assert isinstance(build_scraper(), SpiderScraper)

    monkeypatch.setenv("FIRECRAWL_KEY", "test-firecrawl-key")
    monkeypatch.setenv("SCRAPER_BACKEND", "firecrawl")
    assert isinstance(build_scraper(), FirecrawlScraper)


def test_build_scraper_auto_detect(monkeypatch):
    monkeypatch.delenv("SCRAPER_BACKEND", raising=False)
    monkeypatch.setenv("SPIDER_API_KEY", "test-spider-key")
    assert isinstance(build_scraper(), SpiderScraper)


def test_build_scraper_missing_both_keys(monkeypatch):
    monkeypatch.delenv("SCRAPER_BACKEND", raising=False)
    monkeypatch.delenv("SPIDER_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_KEY", raising=False)

    with pytest.raises(
        ValueError, match="Neither SPIDER_API_KEY nor FIRECRAWL_KEY is set"
    ):
        build_scraper()


def test_spider_scraper_missing_key(monkeypatch):
    monkeypatch.delenv("SPIDER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="SPIDER_API_KEY is required"):
        SpiderScraper()


def test_firecrawl_scraper_missing_key(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_KEY", raising=False)
    with pytest.raises(ValueError, match="FIRECRAWL_KEY is required"):
        FirecrawlScraper()


def test_extract_property_price_json_ld():
    sample_html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "SingleFamilyResidence",
          "offers": {
            "@type": "Offer",
            "price": "625000"
          }
        }
        </script>
      </head>
      <body></body>
    </html>
    """
    assert _extract_property_price_from_html(sample_html) == 625000.0


def test_extract_property_price_meta():
    sample_html = """
    <html>
      <head>
        <meta property="og:description" content="3171 W Radcliff Ave is a single family home valued at $645,000 with 3 beds and 2 baths." />
      </head>
      <body></body>
    </html>
    """
    assert _extract_property_price_from_html(sample_html) == 645000.0


def test_extract_property_price_empty():
    assert _extract_property_price_from_html("") is None
    assert _extract_property_price_from_html("<html><body>No price here</body></html>") is None


def test_extract_property_price_zillow():
    sample_next_data = """
    <html>
      <body>
        <script id="__NEXT_DATA__">{"props":{"pageProps":{"initialData":{"zestimate":561800}}}}</script>
      </body>
    </html>
    """
    assert _extract_property_price_from_html(sample_next_data) == 561800.0


def test_extract_property_price_redfin():
    sample_redfin = """
    <div class="stat-block price-section" data-rf-test-id="abp-price">
      <div class="statsValue price"><span class="">$575,063</span></div>
    </div>
    """
    assert _extract_property_price_from_html(sample_redfin) == 575063.0

    sample_redfin_text = """
    <div>Based on Redfin's Englewood data, we estimate the home's value is $575,063</div>
    """
    assert _extract_property_price_from_html(sample_redfin_text) == 575063.0

