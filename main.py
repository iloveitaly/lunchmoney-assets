import json
import re
from datetime import UTC, datetime
from pathlib import Path

import click
from decouple import config
from lunchable import LunchMoney
from structlog_config import configure_logger

from scrapers import build_scraper

# Configure structlog
log = configure_logger()


def load_assets(path: Path):
    return json.loads(path.read_text())


def _get_kbb_zipcode(metadata: dict) -> str | None:
    zipcode = metadata.get("zipcode") or config("KBB_ZIPCODE", default="80110")
    zipcode = str(zipcode).strip()

    if not re.fullmatch(r"\d{5}", zipcode):
        return None

    return zipcode


def get_kbb_price(scraper, asset_id, metadata, dry_run):
    url = metadata["url"]

    log.info("starting kbb price fetch", asset_id=asset_id)

    # Mileage Logic

    if metadata.get("mileageStart") and metadata.get("mileageDate"):
        yearly_mileage = metadata.get("yearlyMileage", 12000)

        mileage_start = metadata["mileageStart"]

        mileage_date = datetime.strptime(metadata["mileageDate"], "%Y-%m-%d").replace(
            tzinfo=UTC
        )

        current_date = datetime.now(UTC)

        days_passed = (current_date - mileage_date).days

        fractional_year = days_passed / 365.25

        mileage = round(mileage_start + (fractional_year * yearly_mileage))

        log.info(
            "calculated mileage", asset_id=asset_id, mileage=mileage, original_url=url
        )

        url = re.sub(r"mileage=\d+", f"mileage={mileage}", url)

        metadata["url"] = url

    zipcode = _get_kbb_zipcode(metadata)

    vehicle_price = scraper.fetch_vehicle_price(url, zipcode=zipcode)

    price = vehicle_price.private_party_value

    if price is None:
        log.error("could not find private_party_value", asset_id=asset_id)

        return None

    log.info("extracted kbb private party price", price=price)

    # Adjustment

    if metadata.get("adjustment"):
        log.info("applying adjustment", adjustment=metadata["adjustment"])

        price += metadata["adjustment"]

    return price


@click.command()
@click.option(
    "--dry-run", is_flag=True, help="Do not update LunchMoney, just log results."
)
@click.option("--assets-path", default="assets.json", help="Path to assets JSON file.")
def main(dry_run, assets_path):
    """Scrape asset prices and update LunchMoney."""

    lunch_money_api_key = config("LUNCH_MONEY_API_KEY")

    # Initialize Clients
    scraper = build_scraper()
    lunch = LunchMoney(access_token=lunch_money_api_key)

    # Load Assets
    assets_file = Path(assets_path)

    if not assets_file.exists():
        log.error("assets file not found", path=assets_file)

        return

    assets = load_assets(assets_file)

    for asset_id, metadata in assets.items():
        url = metadata.get("url")

        if not url:
            continue

        log.info("processing asset", asset_id=asset_id, url=url)

        price = None

        if "kbb.com" in url:
            price = get_kbb_price(scraper, asset_id, metadata, dry_run)
        elif "zillow.com" in url:
            zillow_price = scraper.fetch_property_price(url)
            redfin_url = metadata.get("redfin")

            if redfin_url:
                redfin_price = scraper.fetch_property_price(redfin_url)

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
            log.warning("unsupported asset url", url=url)

            continue

        if price is not None:
            log.info("final price", asset_id=asset_id, price=price)

            if not dry_run:
                lunch.update_asset(int(asset_id), balance=price)

                log.info("updated lunchmoney asset", asset_id=asset_id)
            else:
                log.info("dry run: skipping update")


if __name__ == "__main__":
    main()
