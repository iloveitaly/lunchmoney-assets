import html
from pathlib import Path
from typing import Any

import httpx
from decouple import config
from structlog_config import configure_logger

from .base import VehiclePrice
from .utils import (
    extract_kbb_price_advisor_svg_url,
    extract_property_price_from_html,
    parse_currency,
    parse_private_party_value_from_kbb_svg,
    replace_query_param,
    url_hash,
)

log = configure_logger()

SPIDER_API_BASE = "https://api.spider.cloud"


class SpiderScraper:
    """Scraper implementation powered by Spider.cloud."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or config("SPIDER_API_KEY", default=None)
        self._headers = {"Content-Type": "application/json"}
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"

    def _post(self, endpoint: str, payload: dict[str, Any], timeout: float = 60.0) -> list[dict]:
        url = f"{SPIDER_API_BASE}{endpoint}"
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=self._headers, json=payload)
            if resp.status_code == 402:
                error_info = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                raise RuntimeError(f"Spider.cloud credit balance empty or payment required: {error_info}")
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return [data]

    def fetch_vehicle_price(self, url: str, zipcode: str | None = None) -> VehiclePrice:
        log.info("scraping kbb with spider.cloud", url=url)

        payload = {
            "url": url,
            "return_format": "raw_html",
            "request": "smart",
        }
        results = self._post("/scrape", payload, timeout=45.0)
        item = results[0] if results else {}

        raw_html = item.get("content", "")
        raw_html = html.unescape(raw_html)

        price_advisor_url = extract_kbb_price_advisor_svg_url(raw_html)
        if price_advisor_url and zipcode:
            price_advisor_url = replace_query_param(price_advisor_url, "zipcode", zipcode)

        private_party_value = None
        trade_in_value = None
        typical_listing_price = None

        if price_advisor_url:
            log.info("found kbb price advisor svg", url=price_advisor_url)
            advisor_svg = httpx.get(price_advisor_url, follow_redirects=True).text
            svg_price = parse_private_party_value_from_kbb_svg(advisor_svg)
            if svg_price:
                log.info("extracted kbb private party price from advisor svg", price=svg_price)
                private_party_value = svg_price

        debug_hash = url_hash(url)
        if raw_html:
            debug_path = Path("/tmp") / f"kbb_spider_{debug_hash}.html"
            debug_path.write_text(raw_html)

        return VehiclePrice(
            private_party_value=private_party_value,
            trade_in_value=trade_in_value,
            typical_listing_price=typical_listing_price,
        )

    def fetch_property_price(self, url: str) -> float | None:
        log.info("scraping property with spider.cloud", url=url)

        payload: dict[str, Any] = {
            "url": url,
            "return_format": "raw",
        }

        if self.api_key:
            payload.update({
                "request": "smart",
                "stealth": True,
                "proxy": "residential",
                "country_code": "us",
            })

        try:
            results = self._post("/scrape", payload, timeout=60.0)
            item = results[0] if results else {}
            content = item.get("content", "")
            status = item.get("status")

            if status in (403, 202) and not self.api_key:
                log.error(
                    "property scrape blocked by anti-bot on free tier. Spider API key with credits required for stealth/residential proxy.",
                    url=url,
                    status=status,
                )
                return None

            price = extract_property_price_from_html(content, url=url)
            if price is not None:
                log.info("extracted property price", url=url, price=price)
                return price

            # Fallback to /ai/scrape if selector extraction didn't find price and API key is configured
            if self.api_key:
                log.info("falling back to /ai/scrape for property", url=url)
                ai_payload = {
                    "url": url,
                    "prompt": "Extract the property valuation, estimate, or price as a JSON object with key 'price' as a float number.",
                    "return_format": "json",
                    "country_code": "us",
                }
                ai_results = self._post("/ai/scrape", ai_payload, timeout=60.0)
                ai_item = ai_results[0] if ai_results else {}
                ai_content = ai_item.get("content", "")
                if ai_price := extract_property_price_from_html(ai_content, url=url):
                    log.info("extracted property price from /ai/scrape content", url=url, price=ai_price)
                    return ai_price
                extracted_data = ai_item.get("metadata", {}).get("extracted_data")
                if isinstance(extracted_data, dict) and (p := extracted_data.get("price")):
                    return parse_currency(str(p))

            log.error("could not extract price from spider response", url=url)
            return None
        except (httpx.HTTPError, RuntimeError, KeyError, ValueError, TypeError) as e:
            log.error("spider property scrape error", url=url, error=str(e))
            return None


# Backward-compatibility alias
_extract_property_price_from_html = extract_property_price_from_html

