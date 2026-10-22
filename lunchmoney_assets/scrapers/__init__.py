from decouple import config

from .base import Scraper, VehiclePrice
from .firecrawl import FirecrawlScraper
from .spider import SpiderScraper

BACKEND_SPIDER = "spider"
BACKEND_FIRECRAWL = "firecrawl"


def build_scraper() -> Scraper:
    "Construct the configured scraper backend from environment settings"

    spider_key = config("SPIDER_API_KEY", default=None)
    firecrawl_key = config("FIRECRAWL_KEY", default=None)

    if not spider_key and not firecrawl_key:
        raise ValueError(
            "Neither SPIDER_API_KEY nor FIRECRAWL_KEY is set. At least one scraper API key is required."
        )

    backend = config("SCRAPER_BACKEND", default=None)
    if backend:
        backend_name = backend.lower()

        if backend_name == BACKEND_SPIDER:
            return SpiderScraper()

        if backend_name == BACKEND_FIRECRAWL:
            return FirecrawlScraper()

        raise ValueError(f"Unknown scraper backend: {backend}")

    if spider_key:
        return SpiderScraper()

    return FirecrawlScraper()


__all__ = [
    "FirecrawlScraper",
    "Scraper",
    "SpiderScraper",
    "VehiclePrice",
    "build_scraper",
]
