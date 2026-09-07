import base64
import hashlib
import re
from pathlib import Path

import httpx
from decouple import config
from firecrawl import Firecrawl
from pydantic import BaseModel, Field
from structlog_config import configure_logger

from .base import VehiclePrice
from .utils import (
    _extract_kbb_price_advisor_svg_url,
    _parse_currency,
    _parse_private_party_value_from_kbb_svg,
    _replace_query_param,
    _url_hash,
    extract_kbb_price_advisor_svg_url,
    parse_currency,
    parse_private_party_value_from_kbb_svg,
    replace_query_param,
    url_hash,
)

log = configure_logger()

KBB_PROMPT = (
    "Extract the different valuation prices for this vehicle. Look for the 'Private Party Value' "
    "which is the main highlighted price value in the pricing section. This value is typically "
    "displayed prominently in the center of a price gauge or chart. Also extract 'Trade-in Value' "
    "and 'Typical Listing Price' if available."
)


class _PriceSchema(BaseModel):
    price: float = Field(..., description="The price or value of the asset/home/car.")


class _KBBExtraction(BaseModel):
    private_party_value: float | None = Field(
        None,
        description="The Private Party Value or Fair Market Value for a private sale.",
    )

    trade_in_value: float | None = Field(
        None, description="The Trade-in Value of the vehicle."
    )

    typical_listing_price: float | None = Field(
        None, description="The Typical Listing Price or Retail Value."
    )



class FirecrawlScraper:
    def __init__(self) -> None:
        api_key = config("FIRECRAWL_KEY")
        self._client = Firecrawl(api_key=api_key)

    def fetch_vehicle_price(self, url: str, zipcode: str | None = None) -> VehiclePrice:
        log.info("scraping kbb with detailed json extraction", url=url)

        result = self._client.scrape(
            url,
            formats=[
                "html",
                "rawHtml",
                "screenshot",
                {
                    "type": "json",
                    "schema": _KBBExtraction.model_json_schema(),
                    "prompt": KBB_PROMPT,
                },
            ],
            actions=[{"type": "wait", "milliseconds": 5000}],
            only_main_content=False,
        )

        extracted: dict = getattr(result, "json", None) or {}

        if not extracted:
            log.warning("no json returned from firecrawl", url=url)

        raw_html: str = getattr(result, "raw_html", None) or ""
        price_advisor_url = _extract_kbb_price_advisor_svg_url(raw_html)

        if price_advisor_url and zipcode:
            price_advisor_url = _replace_query_param(price_advisor_url, "zipcode", zipcode)

        if price_advisor_url:
            # Fetch the SVG directly — Firecrawl cannot process image/svg+xml responses
            advisor_svg = httpx.get(price_advisor_url, follow_redirects=True).text
            svg_price = _parse_private_party_value_from_kbb_svg(advisor_svg)

            if svg_price:
                log.info("extracted kbb private party price from advisor svg", price=svg_price)

                extracted["private_party_value"] = svg_price

        url_hash = _url_hash(url)

        if html := getattr(result, "html", None):
            debug_path = Path("/tmp") / f"kbb_html_{url_hash}.html"
            debug_path.write_text(html)
            log.info("kbb html saved", path=debug_path)

        if screenshot := getattr(result, "screenshot", None):
            debug_path = Path("/tmp") / f"kbb_screenshot_{url_hash}.png"
            screenshot_data = base64.b64decode(
                screenshot.split(",")[1] if "," in screenshot else screenshot
            )
            debug_path.write_bytes(screenshot_data)
            log.info("kbb screenshot saved", path=debug_path)

        log.info("kbb raw extraction", data=extracted)

        return VehiclePrice(
            private_party_value=extracted.get("private_party_value"),
            trade_in_value=extracted.get("trade_in_value"),
            typical_listing_price=extracted.get("typical_listing_price"),
        )

    def fetch_property_price(self, url: str) -> float | None:
        log.info("scraping property", url=url)

        result = self._client.scrape(
            url,
            formats=[{"type": "json", "schema": _PriceSchema.model_json_schema()}],
        )

        extracted: dict | None = getattr(result, "json", None)

        if not extracted:
            log.error("no json returned from firecrawl", url=url)
            return None

        price = extracted.get("price")

        if price is None:
            log.error("could not find price in json", url=url)

        return price
