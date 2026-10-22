import base64
from pathlib import Path

import httpx2
from decouple import config
from firecrawl import Firecrawl
from firecrawl.v2.types import WaitAction
from pydantic import BaseModel, Field
from structlog_config import configure_logger

from .base import VehiclePrice
from .utils import (
    extract_kbb_price_advisor_svg_url,
    parse_private_party_value_from_kbb_svg,
    replace_query_param,
    url_hash,
)

log = configure_logger()

WAIT_TIME_MS = 5_000
DEBUG_OUTPUT_DIR = Path("/tmp")

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
    "Scraper implementation using firecrawl api"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or config("FIRECRAWL_KEY", default=None)
        if not self.api_key:
            raise ValueError("FIRECRAWL_KEY is required when using FirecrawlScraper.")

        self._client = Firecrawl(api_key=self.api_key)

    def fetch_vehicle_price(self, url: str, zipcode: str | None = None) -> VehiclePrice:
        "Fetch vehicle valuation from kbb via firecrawl and price advisor svg"

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
            actions=[WaitAction(type="wait", milliseconds=WAIT_TIME_MS)],
            only_main_content=False,
        )

        extracted: dict[str, object] = getattr(result, "json", None) or {}
        if not extracted:
            log.warning("no json returned from firecrawl", url=url)

        raw_html: str = getattr(result, "raw_html", None) or ""
        price_advisor_url = extract_kbb_price_advisor_svg_url(raw_html)

        if price_advisor_url and zipcode:
            price_advisor_url = replace_query_param(
                price_advisor_url, "zipcode", zipcode
            )

        if price_advisor_url:
            # fetch svg directly because firecrawl cannot process image/svg+xml responses
            advisor_svg = httpx2.get(price_advisor_url, follow_redirects=True).text
            svg_price = parse_private_party_value_from_kbb_svg(advisor_svg)

            if svg_price:
                log.info(
                    "extracted kbb private party price from advisor svg",
                    price=svg_price,
                )
                extracted["private_party_value"] = svg_price

        debug_hash = url_hash(url)

        if html := getattr(result, "html", None):
            debug_path = DEBUG_OUTPUT_DIR / f"kbb_html_{debug_hash}.html"
            debug_path.write_text(html)
            log.info("kbb html saved", path=debug_path)

        if screenshot := getattr(result, "screenshot", None):
            debug_path = DEBUG_OUTPUT_DIR / f"kbb_screenshot_{debug_hash}.png"
            screenshot_data = base64.b64decode(
                screenshot.split(",")[1] if "," in screenshot else screenshot
            )
            debug_path.write_bytes(screenshot_data)
            log.info("kbb screenshot saved", path=debug_path)

        log.info("kbb raw extraction", data=extracted)

        party_val = extracted.get("private_party_value")
        trade_val = extracted.get("trade_in_value")
        listing_val = extracted.get("typical_listing_price")

        return VehiclePrice(
            private_party_value=float(party_val)
            if isinstance(party_val, (int, float))
            else None,
            trade_in_value=float(trade_val)
            if isinstance(trade_val, (int, float))
            else None,
            typical_listing_price=float(listing_val)
            if isinstance(listing_val, (int, float))
            else None,
        )

    def fetch_property_price(self, url: str) -> float | None:
        "Fetch property valuation from url via firecrawl structured extraction"

        log.info("scraping property", url=url)

        result = self._client.scrape(
            url,
            formats=[{"type": "json", "schema": _PriceSchema.model_json_schema()}],
        )

        extracted: dict[str, object] | None = getattr(result, "json", None)
        if not extracted:
            log.error("no json returned from firecrawl", url=url)
            return None

        price = extracted.get("price")
        if price is None or not isinstance(price, (int, float)):
            log.error("could not find price in json", url=url)
            return None

        return float(price)
