import logging
from time import sleep
import json
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import camoufox
from camoufox.sync_api import Camoufox
import requests
from decouple import config
from proxies import get_random_proxy

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s',
)

# Utility Functions
def parse_currency_string_to_float(currency_string):
    """Convert a currency string (e.g., '$12,345.67') to a float."""
    return float(re.sub(r"[^0-9.]", "", currency_string))

def extract_text_from_xpath(browser, url: str, xpath: str) -> str:
    """Extract text or attribute value from a webpage using XPath."""
    page = browser.new_page()
    base_url = re.match(r'(https?://[^/]+)', url).group(1)
    page.goto(base_url, timeout=0)
    sleep(5)
    page.goto(url, timeout=0)
    try:
        page.wait_for_selector(f"xpath={xpath}", timeout=60000)
    except PlaywrightTimeoutError:
        print(f"Wait for XPath was not successful: {xpath}")

    text_value = page.evaluate(f'''() => {{
        const result = document.evaluate("{xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
        const node = result.singleNodeValue;
        if (node) {{
            if (node.nodeType === Node.TEXT_NODE) {{
                return node.textContent;
            }} else if (node.nodeType === Node.ELEMENT_NODE) {{
                return node.textContent;
            }} else if (node.nodeType === Node.ATTRIBUTE_NODE) {{
                return node.value;
            }}
        }}
        return null;
    }}''')

    if not text_value:
        print(f"Error pulling xpath ({xpath}) from page ({url})")
        timestamp = int(datetime.now().timestamp())
        page.screenshot(path=f"/tmp/xpath-error-{timestamp}.png", full_page=True)

    page.close()
    return text_value

def update_asset_price(asset_id, price):
    """Update an asset's balance in Lunch Money via API."""
    print(f"updating {asset_id} to price: {price}")
    url = f"https://dev.lunchmoney.app/v1/assets/{asset_id}"
    headers = {
        "Authorization": f"Bearer {os.environ['LUNCH_MONEY_API_KEY']}",
        "Content-Type": "application/json",
    }
    data = {"balance": str(price)}
    response = requests.put(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Error updating asset: {response.json().get('error')}")

# Valuation Methods
def get_kbb_valuation(browser, asset_metadata):
    """Get car valuation from KBB."""
    # Adjust mileage if provided
    if "mileageStart" in asset_metadata and "mileageDate" in asset_metadata:
        yearly_mileage = asset_metadata.get("yearlyMileage", 12000)
        mileage_start = asset_metadata["mileageStart"]
        mileage_date = datetime.strptime(asset_metadata["mileageDate"], "%Y-%m-%d")
        current_date = datetime.now()
        days_passed = (current_date - mileage_date).days
        fractional_year = days_passed / 365.25
        print(f"Fractional year: {fractional_year}")
        mileage = round(mileage_start + fractional_year * yearly_mileage)
        print(f"Adjusting mileage: {mileage}")
        asset_metadata["url"] = re.sub(
            r"mileage=\d+", f"mileage={mileage}", asset_metadata["url"]
        )

    svg_path = extract_text_from_xpath(browser, asset_metadata["url"], "//object/@data")
    if not svg_path:
        print(f"Could not find SVG path for {asset_metadata['url']}")
        return None

    kbb_price_with_currency = extract_text_from_xpath(
        browser, svg_path, "//*[@id='RangeBox']/*[name()='text'][4]"
    )
    if not kbb_price_with_currency:
        print(f"Could not find KBB price on SVG {svg_path}")
        return None

    print(f"kbb price: {kbb_price_with_currency}")
    kbb_price = parse_currency_string_to_float(kbb_price_with_currency)
    if "adjustment" in asset_metadata:
        print(f"applying adjustment of {asset_metadata['adjustment']}")
        kbb_price += asset_metadata["adjustment"]

    return kbb_price

def get_zillow_valuation(browser, asset_metadata):
    """Get property valuation from Zillow."""
    zillow_xpath = '//*[@id="home-details-home-values"]/div/div[1]/div/div/div[1]/div/p/h3'
    zillow_price = extract_text_from_xpath(browser, asset_metadata["url"], zillow_xpath)
    if not zillow_price:
        print(f"Could not find Zillow home value for {asset_metadata['url']}")
        return None

    print(f"zillow home value: {zillow_price}")
    return parse_currency_string_to_float(zillow_price)

def get_redfin_valuation(browser, asset_metadata):
    """Get property valuation from Redfin."""
    redfin_xpath = '//*[@data-rf-test-id="abp-price"]/div[@class="statsValue"]'
    redfin_price = extract_text_from_xpath(browser, asset_metadata["redfin"], redfin_xpath)
    if not redfin_price:
        print(f"Could not find Redfin home value for {asset_metadata['redfin']}")
        return None

    print(f"redfin home value: {redfin_price}")
    return parse_currency_string_to_float(redfin_price)

# Main Logic
if "LUNCH_MONEY_API_KEY" not in os.environ:
    print("Lunch Money API key not set")
    exit(1)

print(f"Updating price data {datetime.now()}")

assets_path = os.environ.get("ASSET_PATH", "assets.json")
with open(assets_path, "r") as f:
    assets = json.load(f)

PROXY = config("PROXY", cast=bool, default=True)
camoufox_options = {}
if PROXY:
    camoufox_options["proxy"] = get_random_proxy()
    camoufox_options["geoip"] = True

with Camoufox(**camoufox_options) as browser:
    for lunch_money_asset_id, asset_metadata in assets.items():
        if "kbb.com" in asset_metadata["url"]:
            price = get_kbb_valuation(browser, asset_metadata)
            if price is not None:
                update_asset_price(int(lunch_money_asset_id), price)

        elif "zillow.com" in asset_metadata["url"]:
            zillow_value = get_zillow_valuation(browser, asset_metadata)
            if zillow_value is None:
                continue

            # Check for Redfin and average if available
            if "redfin" in asset_metadata:
                redfin_value = get_redfin_valuation(browser, asset_metadata)
                if redfin_value is not None:
                    home_value = round((zillow_value + redfin_value) / 2)
                    print(f"Combined home value: {home_value}")
                else:
                    home_value = zillow_value
            else:
                home_value = zillow_value

            update_asset_price(int(lunch_money_asset_id), home_value)

        else:
            print("Unsupported asset type")

    browser.close()

print("Assets updated")