from decouple import config

from .base import Scraper, VehiclePrice
from .firecrawl import FirecrawlScraper
from .spider import SpiderScraper


def build_scraper() -> Scraper:
    backend = config("SCRAPER_BACKEND", default=None)
    if backend:
        backend = backend.lower()
        if backend == "spider":
            return SpiderScraper()
        if backend == "firecrawl":
            return FirecrawlScraper()
        raise ValueError(f"Unknown scraper backend: {backend}")

    if config("SPIDER_API_KEY", default=None):
        return SpiderScraper()
    return FirecrawlScraper()


__all__ = ["FirecrawlScraper", "Scraper", "SpiderScraper", "VehiclePrice", "build_scraper"]

