from .base import Scraper, VehiclePrice
from .firecrawl import FirecrawlScraper


def build_scraper() -> Scraper:
    return FirecrawlScraper()


__all__ = ["Scraper", "VehiclePrice", "build_scraper"]
