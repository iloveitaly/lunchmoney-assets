import json
import re
from pathlib import Path

import click
from decouple import config
from lunchable import LunchMoney
from structlog_config import configure_logger
from whenever import SYSTEM_TZ, Date

from .scrapers import Scraper, build_scraper
from .version import __version__

log = configure_logger()

DEFAULT_YEARLY_MILEAGE = 12_000
DAYS_PER_YEAR = 365.25
DEFAULT_KBB_ZIPCODE = "80110"
DEFAULT_ASSETS_PATH = "assets.json"

ZIPCODE_PATTERN = re.compile(
    r"""
    ^
    \d{5}  # 5-digit US postal code
    $
    """,
    re.VERBOSE,
)

MILEAGE_PARAM_PATTERN = re.compile(
    r"""
    mileage=  # query parameter key
    \d+       # numeric mileage value
    """,
    re.VERBOSE,
)


def load_assets(path: Path) -> dict[str, dict[str, object]]:
    "Load asset configurations from json file"

    return json.loads(path.read_text())


def get_kbb_zipcode(metadata: dict[str, object]) -> str | None:
    "Resolve kbb zipcode from metadata or environment fallback"

    zipcode_val = metadata.get("zipcode") or config(
        "KBB_ZIPCODE", default=DEFAULT_KBB_ZIPCODE
    )
    zipcode = str(zipcode_val).strip()

    if not ZIPCODE_PATTERN.fullmatch(zipcode):
        return None

    return zipcode


def calculate_estimated_mileage(
    mileage_start: int,
    mileage_date_str: str,
    yearly_mileage: int = DEFAULT_YEARLY_MILEAGE,
) -> int:
    "Calculate current estimated vehicle mileage based on start date and yearly average"

    start_date = Date.parse_iso(mileage_date_str)
    current_date = Date.today(SYSTEM_TZ)

    days_passed = current_date.since(start_date, total="days")
    fractional_year = days_passed / DAYS_PER_YEAR

    return round(mileage_start + (fractional_year * yearly_mileage))


def inject_mileage_into_url(url: str, mileage: int) -> str:
    "Replace existing mileage parameter in url with calculated mileage"

    return MILEAGE_PARAM_PATTERN.sub(f"mileage={mileage}", url)


def get_kbb_price(
    scraper: Scraper,
    asset_id: str,
    metadata: dict[str, object],
    dry_run: bool = False,
) -> float | None:
    "Fetch kbb private party valuation with optional mileage adjustment"

    asset_data = metadata.copy()
    url = str(asset_data["url"])

    log.info("starting kbb price fetch", asset_id=asset_id)

    mileage_start = asset_data.get("mileageStart")
    mileage_date = asset_data.get("mileageDate")

    if isinstance(mileage_start, (int, float)) and isinstance(mileage_date, str):
        yearly_mileage_val = asset_data.get("yearlyMileage", DEFAULT_YEARLY_MILEAGE)
        yearly_mileage = (
            int(yearly_mileage_val)
            if isinstance(yearly_mileage_val, (int, float, str))
            else DEFAULT_YEARLY_MILEAGE
        )
        mileage = calculate_estimated_mileage(
            int(mileage_start),
            mileage_date,
            yearly_mileage,
        )

        log.info(
            "calculated mileage",
            asset_id=asset_id,
            mileage=mileage,
            original_url=url,
        )

        url = inject_mileage_into_url(url, mileage)

    zipcode = get_kbb_zipcode(asset_data)
    vehicle_price = scraper.fetch_vehicle_price(url, zipcode=zipcode)

    price = vehicle_price.private_party_value
    if price is None:
        log.error("could not find private_party_value", asset_id=asset_id)
        return None

    log.info("extracted kbb private party price", price=price)

    adjustment = asset_data.get("adjustment")
    if isinstance(adjustment, (int, float)):
        log.info("applying adjustment", adjustment=adjustment)
        price += float(adjustment)

    return price


def fetch_property_valuation(
    scraper: Scraper,
    zillow_url: str,
    redfin_url: str | None = None,
) -> float | None:
    "Fetch property valuation from zillow and optionally average with redfin"

    zillow_price = scraper.fetch_property_price(zillow_url)
    if not redfin_url:
        return zillow_price

    redfin_price = scraper.fetch_property_price(redfin_url)
    if zillow_price and redfin_price:
        average_price = round((zillow_price + redfin_price) / 2)
        log.info(
            "averaged price",
            zillow=zillow_price,
            redfin=redfin_price,
            average=average_price,
        )
        return average_price

    return zillow_price or redfin_price


@click.command()
@click.version_option(__version__, "-v", "--version")
@click.option(
    "--dry-run", is_flag=True, help="Do not update LunchMoney, just log results."
)
@click.option(
    "--assets-path",
    default=DEFAULT_ASSETS_PATH,
    help="Path to assets JSON file.",
)
def main(dry_run: bool, assets_path: str):
    "Scrape asset prices and update LunchMoney"

    lunch_money_api_key = config("LUNCH_MONEY_API_KEY")

    scraper = build_scraper()
    lunch = LunchMoney(access_token=lunch_money_api_key)

    assets_file = Path(assets_path)
    if not assets_file.exists():
        log.error("assets file not found", path=assets_file)
        return

    assets = load_assets(assets_file)

    for asset_id, metadata in assets.items():
        url = metadata.get("url")
        if not url or not isinstance(url, str):
            continue

        log.info("processing asset", asset_id=asset_id, url=url)

        price = None

        if "kbb.com" in url:
            price = get_kbb_price(scraper, asset_id, metadata, dry_run)
        elif "zillow.com" in url:
            redfin_val = metadata.get("redfin")
            redfin_url = str(redfin_val) if redfin_val else None
            price = fetch_property_valuation(scraper, url, redfin_url)
        else:
            log.warning("unsupported asset url", url=url)
            continue

        if price is None:
            continue

        log.info("final price", asset_id=asset_id, price=price)

        if dry_run:
            log.info("dry run: skipping update")
            continue

        lunch.update_asset(int(asset_id), balance=price)
        log.info("updated lunchmoney asset", asset_id=asset_id)


if __name__ == "__main__":
    main()
