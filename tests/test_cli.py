import json
from unittest.mock import MagicMock

from lunchmoney_assets.cli import get_kbb_price, get_kbb_zipcode, load_assets
from lunchmoney_assets.scrapers.base import VehiclePrice


def test_load_assets(tmp_path):
    p = tmp_path / "assets.json"
    data = {"123": {"url": "https://example.com"}}
    p.write_text(json.dumps(data))

    assert load_assets(p) == data


def test_get_kbb_zipcode():
    assert get_kbb_zipcode({"zipcode": "90210"}) == "90210"
    assert get_kbb_zipcode({"zipcode": "invalid"}) is None
    assert get_kbb_zipcode({}) == "80110"


def test_get_kbb_price_basic():
    scraper = MagicMock()
    scraper.fetch_vehicle_price.return_value = VehiclePrice(
        private_party_value=20_000.0,
        trade_in_value=18_000.0,
        typical_listing_price=22_000.0,
    )
    metadata: dict[str, object] = {
        "url": "https://www.kbb.com/car/?mileage=50000",
        "zipcode": "90210",
        "adjustment": 500,
    }

    price = get_kbb_price(scraper, "123", metadata)

    assert price == 20_500.0
    scraper.fetch_vehicle_price.assert_called_once()


def test_get_kbb_price_mileage_calculation():
    scraper = MagicMock()
    scraper.fetch_vehicle_price.return_value = VehiclePrice(
        private_party_value=15_000.0,
        trade_in_value=None,
        typical_listing_price=None,
    )
    metadata: dict[str, object] = {
        "url": "https://www.kbb.com/car/?mileage=50000",
        "mileageStart": 50_000,
        "mileageDate": "2020-01-01",
        "yearlyMileage": 10_000,
    }

    price = get_kbb_price(scraper, "123", metadata)

    assert price == 15_000.0

    # url mileage should have been replaced with a calculated value > 50000
    called_url = scraper.fetch_vehicle_price.call_args[0][0]
    assert "mileage=" in called_url
    assert called_url != "https://www.kbb.com/car/?mileage=50000"


def test_get_kbb_price_missing_price():
    scraper = MagicMock()
    scraper.fetch_vehicle_price.return_value = VehiclePrice(
        private_party_value=None,
        trade_in_value=None,
        typical_listing_price=None,
    )
    metadata: dict[str, object] = {"url": "https://www.kbb.com/car/"}

    assert get_kbb_price(scraper, "123", metadata) is None
