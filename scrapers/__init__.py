from decouple import config

from .base import Scraper, VehiclePrice
from .firecrawl import FirecrawlScraper
from .spider import SpiderScraper


def build_scraper() -> Scraper:
    backend = config("SCRAPER_BACKEND", default="firecrawl").lower()
    if backend == "spider":
        return SpiderScraper()
    return FirecrawlScraper()


__all__ = ["Scraper", "VehiclePrice", "FirecrawlScraper", "SpiderScraper", "build_scraper"]

