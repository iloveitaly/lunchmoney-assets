import click
from structlog_config import configure_logger
import os
import json
import re
from datetime import datetime
from firecrawl import Firecrawl
from lunchable import LunchMoney

from decouple import config

# Configure structlog
log = configure_logger()


def load_assets(path):
    with open(path, "r") as f:
        return json.load(f)


from pydantic import BaseModel, Field


class PriceSchema(BaseModel):
    price: float = Field(..., description="The price or value of the asset/home/car.")


def parse_currency(value_str):
    if not value_str:
        return 0.0

    return float(re.sub(r"[^0-9.]", "", value_str))


class KBBExtraction(BaseModel):
    private_party_value: float = Field(
        ...,
        description="The Private Party Value or Fair Market Value for a private sale.",
    )

    trade_in_value: float | None = Field(
        None, description="The Trade-in Value of the vehicle."
    )

    typical_listing_price: float | None = Field(
        None, description="The Typical Listing Price or Retail Value."
    )


def _extract_kbb_price_advisor_svg_url(raw_html: str) -> str | None:
    if not raw_html:
        return None

    match = re.search(
        r'"href"\s*:\s*"(upa\.syndication\.kbb\.com/usedcar/[^"]+)"',
        raw_html,
    )
    if not match:
        match = re.search(r'upa\.syndication\.kbb\.com/usedcar/[^"]+', raw_html)
        if not match:
            return None

    href = match.group(1) if match.lastindex else match.group(0)
    href = href.replace("\\u0026", "&").replace("\u0026", "&")

    if href.startswith("http"):
        return href

    return f"https://{href}"


def _parse_private_party_value_from_kbb_svg(svg: str) -> float | None:
    if not svg:
        return None

    match = re.search(
        r"Private Party Value</text>\s*<text[^>]*>\s*(\$[0-9,]+)",
        svg,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    return parse_currency(match.group(1))


def _replace_query_param(url: str, key: str, value: str) -> str:
    if not url:
        return url

    if not key:
        return url

    pattern = rf"([?&]){re.escape(key)}=[^&]*"
    if re.search(pattern, url):
        return re.sub(pattern, rf"\g<1>{key}={value}", url)

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{key}={value}"


def _get_kbb_zipcode(metadata: dict) -> str | None:
    zipcode = metadata.get("zipcode") or config("KBB_ZIPCODE", default="80110")
    zipcode = str(zipcode).strip()

    if not re.fullmatch(r"\d{5}", zipcode):
        return None

    return zipcode


def get_kbb_price(app, asset_id, metadata, dry_run):
    url = metadata["url"]

    log.info("starting kbb price fetch", asset_id=asset_id)

    # Mileage Logic

    if metadata.get("mileageStart") and metadata.get("mileageDate"):
        yearly_mileage = metadata.get("yearlyMileage", 12000)

        mileage_start = metadata["mileageStart"]

        mileage_date = datetime.strptime(metadata["mileageDate"], "%Y-%m-%d")

        current_date = datetime.now()

        days_passed = (current_date - mileage_date).days

        fractional_year = days_passed / 365.25

        mileage = round(mileage_start + (fractional_year * yearly_mileage))

        log.info(
            "calculated mileage", asset_id=asset_id, mileage=mileage, original_url=url
        )

        # Replace mileage in URL

        url = re.sub(r"mileage=\d+", f"mileage={mileage}", url)

        metadata["url"] = url

    log.info("scraping kbb with detailed json extraction", asset_id=asset_id, url=url)

    try:
        scrape_result = app.scrape(
            url,
            formats=[
                "html",
                "rawHtml",
                "screenshot",
                {
                    "type": "json",
                    "schema": KBBExtraction.model_json_schema(),
                    "prompt": "Extract the different valuation prices for this vehicle. Look for the 'Private Party Value' which is the main highlighted price value in the pricing section. This value is typically displayed prominently in the center of a price gauge or chart. Also extract 'Trade-in Value' and 'Typical Listing Price' if available.",
                },
            ],
            actions=[{"type": "wait", "milliseconds": 5000}],
            only_main_content=False,
        )

    except Exception as e:
        log.error("firecrawl scrape failed", asset_id=asset_id, url=url, error=str(e))

        return None

    if not hasattr(scrape_result, "json") or not scrape_result.json:
        log.error("no json returned from firecrawl", asset_id=asset_id, url=url)

        return None

    extracted_data = scrape_result.json

    raw_html = getattr(scrape_result, "raw_html", None) or ""
    price_advisor_url = _extract_kbb_price_advisor_svg_url(raw_html)
    if price_advisor_url:
        zipcode = _get_kbb_zipcode(metadata)
        if zipcode:
            price_advisor_url = _replace_query_param(
                price_advisor_url, "zipcode", zipcode
            )

    if price_advisor_url:
        try:
            advisor_result = app.scrape(
                price_advisor_url,
                formats=["rawHtml"],
                only_main_content=False,
            )

        except Exception as e:
            log.error(
                "firecrawl scrape failed",
                asset_id=asset_id,
                url=price_advisor_url,
                error=str(e),
            )
        else:
            advisor_svg = getattr(advisor_result, "raw_html", None) or ""
            svg_price = _parse_private_party_value_from_kbb_svg(advisor_svg)
            if svg_price:
                log.info(
                    "extracted kbb private party price from advisor svg",
                    price=svg_price,
                )
                extracted_data["private_party_value"] = svg_price

    from pathlib import Path

    if hasattr(scrape_result, "html") and scrape_result.html:
        debug_path = Path("/tmp") / f"kbb_html_{asset_id}.html"
        debug_path.write_text(scrape_result.html)
        log.info("kbb html saved", path=str(debug_path))

    if hasattr(scrape_result, "screenshot") and scrape_result.screenshot:
        import base64

        debug_path = Path("/tmp") / f"kbb_screenshot_{asset_id}.png"
        screenshot_data = base64.b64decode(
            scrape_result.screenshot.split(",")[1]
            if "," in scrape_result.screenshot
            else scrape_result.screenshot
        )
        debug_path.write_bytes(screenshot_data)
        log.info("kbb screenshot saved", path=str(debug_path))

    log.info("kbb raw extraction", data=extracted_data)

    price = extracted_data.get("private_party_value")

    if price is None:
        log.error("could not find private_party_value in json", asset_id=asset_id)

        return None

    log.info("extracted kbb private party price", price=price)

    # Adjustment

    if metadata.get("adjustment"):
        log.info("applying adjustment", adjustment=metadata["adjustment"])

        price += metadata["adjustment"]

    return price


def get_zillow_price(app, asset_id, url):
    log.info("scraping zillow", asset_id=asset_id, url=url)

    try:
        scrape_result = app.scrape(
            url, formats=[{"type": "json", "schema": PriceSchema.model_json_schema()}]
        )

    except Exception as e:
        log.error("firecrawl scrape failed", asset_id=asset_id, url=url, error=str(e))

        return None

    if not hasattr(scrape_result, "json") or not scrape_result.json:
        log.error("no json returned from firecrawl", asset_id=asset_id, url=url)

        return None

    extracted_data = scrape_result.json

    price = extracted_data.get("price")

    if price is None:
        log.error("could not find price in json", asset_id=asset_id)

        return None

    log.info("extracted zillow price", price=price)

    return price


def get_redfin_price(app, asset_id, url):
    log.info("scraping redfin", asset_id=asset_id, url=url)

    try:
        scrape_result = app.scrape(
            url, formats=[{"type": "json", "schema": PriceSchema.model_json_schema()}]
        )

    except Exception as e:
        log.error("firecrawl scrape failed", asset_id=asset_id, url=url, error=str(e))

        return None

    if not hasattr(scrape_result, "json") or not scrape_result.json:
        log.error("no json returned from firecrawl", asset_id=asset_id, url=url)

        return None

    extracted_data = scrape_result.json

    price = extracted_data.get("price")

    if price is None:
        log.error("could not find price in json", asset_id=asset_id)

        return None

    log.info("extracted redfin price", price=price)

    return price


@click.command()
@click.option(
    "--dry-run", is_flag=True, help="Do not update LunchMoney, just log results."
)
@click.option("--assets-path", default="assets.json", help="Path to assets JSON file.")
def main(dry_run, assets_path):
    """Scrape asset prices and update LunchMoney."""

    try:
        lunch_money_api_key = config("LUNCH_MONEY_API_KEY")

        firecrawl_api_key = config("FIRECRAWL_KEY")

    except Exception as e:
        log.error("Environment variable missing", error=str(e))

        return

    # Initialize Clients
    firecrawl = Firecrawl(api_key=firecrawl_api_key)
    lunch = LunchMoney(access_token=lunch_money_api_key)

    # Load Assets
    if not os.path.exists(assets_path):
        log.error("assets file not found", path=assets_path)
        return

    assets = load_assets(assets_path)

    for asset_id, metadata in assets.items():
        url = metadata.get("url")
        if not url:
            continue

        log.info("processing asset", asset_id=asset_id, url=url)
        price = None

        if "kbb.com" in url:
            price = get_kbb_price(firecrawl, asset_id, metadata, dry_run)
        elif "zillow.com" in url:
            zillow_price = get_zillow_price(firecrawl, asset_id, url)
            redfin_url = metadata.get("redfin")

            if redfin_url:
                redfin_price = get_redfin_price(firecrawl, asset_id, redfin_url)
                if zillow_price and redfin_price:
                    price = round((zillow_price + redfin_price) / 2)
                    log.info(
                        "averaged price",
                        zillow=zillow_price,
                        redfin=redfin_price,
                        average=price,
                    )
                elif zillow_price:
                    price = zillow_price
                elif redfin_price:
                    price = redfin_price
            else:
                price = zillow_price
        else:
            log.warn("unsupported asset url", url=url)
            continue

        if price is not None:
            log.info("final price", asset_id=asset_id, price=price)
            if not dry_run:
                try:
                    lunch.update_asset(int(asset_id), balance=price)
                    log.info("updated lunchmoney asset", asset_id=asset_id)
                except Exception as e:
                    log.error("failed to update lunchmoney", error=str(e))
            else:
                log.info("dry run: skipping update")


if __name__ == "__main__":
    main()
