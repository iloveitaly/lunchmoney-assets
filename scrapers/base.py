from typing import Protocol

from pydantic import BaseModel


class VehiclePrice(BaseModel):
    private_party_value: float | None
    trade_in_value: float | None
    typical_listing_price: float | None


class Scraper(Protocol):
    def fetch_vehicle_price(self, url: str, zipcode: str | None = None) -> VehiclePrice: ...
    def fetch_property_price(self, url: str) -> float | None: ...
