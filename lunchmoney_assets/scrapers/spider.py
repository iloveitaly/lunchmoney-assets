import html
from pathlib import Path

import httpx2
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
DEFAULT_TIMEOUT_SECONDS = 60.0
KBB_TIMEOUT_SECONDS = 45.0
HTTP_STATUS_ACCEPTED = 202
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_PAYMENT_REQUIRED = 402
DEBUG_OUTPUT_DIR = Path("/tmp")


class SpiderScraper:
    "Scraper implementation powered by spider.cloud"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or config("SPIDER_API_KEY", default=None)
        if not self.api_key:
            raise ValueError("SPIDER_API_KEY is required when using SpiderScraper.")

        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(
        self,
        endpoint: str,
        payload: dict[str, object],
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> list[dict[str, object]]:
        "Submit json post request to spider.cloud api endpoint"

        url = f"{SPIDER_API_BASE}{endpoint}"
        with httpx2.Client(timeout=timeout) as client:
            resp = client.post(url, headers=self._headers, json=payload)

            if resp.status_code == HTTP_STATUS_PAYMENT_REQUIRED:
                error_info = (
                    resp.json()
                    if resp.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else resp.text
                )
                raise RuntimeError(
                    f"Spider.cloud credit balance empty or payment required: {error_info}"
                )

            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                return data

            return [data]

    def fetch_vehicle_price(self, url: str, zipcode: str | None = None) -> VehiclePrice:
        "Fetch vehicle valuation from kbb using spider.cloud"

        log.info("scraping kbb with spider.cloud", url=url)

        payload: dict[str, object] = {
            "url": url,
            "return_format": "raw_html",
            "request": "smart",
        }
        results = self._post("/scrape", payload, timeout=KBB_TIMEOUT_SECONDS)
        item = results[0] if results else {}

        raw_content = item.get("content", "")
        raw_html = html.unescape(str(raw_content))

        price_advisor_url = extract_kbb_price_advisor_svg_url(raw_html)
        if price_advisor_url and zipcode:
            price_advisor_url = replace_query_param(
                price_advisor_url, "zipcode", zipcode
            )

        private_party_value = None
        trade_in_value = None
        typical_listing_price = None

        if price_advisor_url:
            log.info("found kbb price advisor svg", url=price_advisor_url)
            advisor_svg = httpx2.get(price_advisor_url, follow_redirects=True).text
            svg_price = parse_private_party_value_from_kbb_svg(advisor_svg)

            if svg_price:
                log.info(
                    "extracted kbb private party price from advisor svg",
                    price=svg_price,
                )
                private_party_value = svg_price

        debug_hash = url_hash(url)
        if raw_html:
            debug_path = DEBUG_OUTPUT_DIR / f"kbb_spider_{debug_hash}.html"
            debug_path.write_text(raw_html)

        return VehiclePrice(
            private_party_value=private_party_value,
            trade_in_value=trade_in_value,
            typical_listing_price=typical_listing_price,
        )

    def fetch_property_price(self, url: str) -> float | None:
        "Fetch property valuation using spider.cloud"

        log.info("scraping property with spider.cloud", url=url)

        payload: dict[str, object] = {
            "url": url,
            "return_format": "raw",
        }

        if self.api_key:
            payload.update(
                {
                    "request": "smart",
                    "stealth": True,
                    "proxy": "residential",
                    "country_code": "us",
                }
            )

        try:
            results = self._post("/scrape", payload, timeout=DEFAULT_TIMEOUT_SECONDS)
            item = results[0] if results else {}
            content = str(item.get("content", ""))
            status = item.get("status")

            if (
                status in (HTTP_STATUS_FORBIDDEN, HTTP_STATUS_ACCEPTED)
                and not self.api_key
            ):
                log.error(
                    "property scrape blocked by anti-bot on free tier",
                    url=url,
                    status=status,
                )
                return None

            price = extract_property_price_from_html(content, url=url)
            if price is not None:
                log.info("extracted property price", url=url, price=price)
                return price

            # fallback to /ai/scrape if selector extraction did not find price and api key is configured
            if self.api_key:
                log.info("falling back to /ai/scrape for property", url=url)
                ai_payload: dict[str, object] = {
                    "url": url,
                    "prompt": "Extract the property valuation, estimate, or price as a JSON object with key 'price' as a float number.",
                    "return_format": "json",
                    "country_code": "us",
                }
                ai_results = self._post(
                    "/ai/scrape", ai_payload, timeout=DEFAULT_TIMEOUT_SECONDS
                )
                ai_item = ai_results[0] if ai_results else {}
                ai_content = str(ai_item.get("content", ""))

                if ai_price := extract_property_price_from_html(ai_content, url=url):
                    log.info(
                        "extracted property price from /ai/scrape content",
                        url=url,
                        price=ai_price,
                    )
                    return ai_price

                meta = ai_item.get("metadata")
                extracted_data = (
                    meta.get("extracted_data") if isinstance(meta, dict) else None
                )
                if isinstance(extracted_data, dict) and (
                    p := extracted_data.get("price")
                ):
                    return parse_currency(str(p))

            log.error("could not extract price from spider response", url=url)
            return None
        except (httpx2.HTTPError, RuntimeError, KeyError, ValueError, TypeError) as e:
            log.error("spider property scrape error", url=url, error=e)
            return None
