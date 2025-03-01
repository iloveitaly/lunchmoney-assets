import logging
import os
# Configure logging
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format='%(levelname)s - %(name)s - %(message)s',
)


from datetime import datetime
import json
import os
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import camoufox
from camoufox.sync_api import Camoufox
import requests
from decouple import config
from proxies import get_random_proxy

log = logging.getLogger(__name__)

# Utility Functions
def parse_currency_string_to_float(currency_string):
    """Convert a currency string (e.g., '$12,345.67') to a float."""
    return float(re.sub(r"[^0-9.]", "", currency_string))

def wait_for_page_load(page, url, timeout=45000):
    """Helper to wait for a page to fully load."""
    log.debug(f"Navigating to {url} and waiting for load")
    page.goto(url, wait_until='networkidle', timeout=timeout)
    log.debug(f"Page loaded: {url}")

def extract_text_from_xpath(page, xpath: str, timeout=60000) -> str:
    """Extract text or attribute value from a webpage using XPath."""
    try:
        page.wait_for_selector(f"xpath={xpath}", timeout=timeout)
    except PlaywrightTimeoutError:
        log.warning(f"Timeout waiting for XPath: {xpath} on {page.url}")
        return None

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
        log.error(f"Error pulling XPath ({xpath}) from page ({page.url})")
        timestamp = int(datetime.now().timestamp())
        page.screenshot(path=f"/tmp/xpath-error-{timestamp}.png", full_page=True)
    else:
        log.debug(f"Extracted text from XPath {xpath}: {text_value}")
    return text_value

def update_asset_price(asset_id, price):
    """Update an asset's balance in Lunch Money via API."""
    log.info(f"Updating asset {asset_id} to price: {price}")
    url = f"https://dev.lunchmoney.app/v1/assets/{asset_id}"
    headers = {
        "Authorization": f"Bearer {os.environ['LUNCH_MONEY_API_KEY']}",
        "Content-Type": "application/json",
    }
    data = {"balance": str(price)}
    response = requests.put(url, headers=headers, json=data)
    if response.status_code != 200:
        log.error(f"Error updating asset {asset_id}: {response.json().get('error')}")
    else:
        log.info(f"Successfully updated asset {asset_id}")

# Valuation Methods
def get_kbb_valuation(browser, asset_metadata):
    """Get car valuation from KBB."""
    page = browser.new_page()
    try:
        if "mileageStart" in asset_metadata and "mileageDate" in asset_metadata:
            yearly_mileage = asset_metadata.get("yearlyMileage", 12000)
            mileage_start = asset_metadata["mileageStart"]
            mileage_date = datetime.strptime(asset_metadata["mileageDate"], "%Y-%m-%d")
            current_date = datetime.now()
            days_passed = (current_date - mileage_date).days
            fractional_year = days_passed / 365.25
            log.debug(f"Fractional year: {fractional_year}")
            mileage = round(mileage_start + fractional_year * yearly_mileage)
            log.debug(f"Adjusting mileage: {mileage}")
            asset_metadata["url"] = re.sub(
                r"mileage=\d+", f"mileage={mileage}", asset_metadata["url"]
            )

        base_url = re.match(r'(https?://[^/]+)', asset_metadata["url"]).group(1)
        wait_for_page_load(page, base_url)
        wait_for_page_load(page, asset_metadata["url"])

        svg_path = extract_text_from_xpath(page, "//object/@data")
        if not svg_path:
            log.warning(f"Could not find SVG path for {asset_metadata['url']}")
            return None

        wait_for_page_load(page, svg_path)
        kbb_price_with_currency = extract_text_from_xpath(
            page, "//*[@id='RangeBox']/*[name()='text'][4]"
        )
        if not kbb_price_with_currency:
            log.warning(f"Could not find KBB price on SVG {svg_path}")
            return None

        log.debug(f"KBB price: {kbb_price_with_currency}")
        kbb_price = parse_currency_string_to_float(kbb_price_with_currency)
        if "adjustment" in asset_metadata:
            log.debug(f"Applying adjustment of {asset_metadata['adjustment']}")
            kbb_price += asset_metadata["adjustment"]
        return kbb_price
    finally:
        page.close()

def get_zillow_valuation(browser, asset_metadata):
    """Get property valuation from Zillow by searching the address."""
    page = browser.new_page()
    try:
        log.debug(f"Navigating to Zillow homepage for {asset_metadata['url']}")
        wait_for_page_load(page, "https://www.zillow.com/")

        # Extract address from URL using regex
        import re
        import random
        match = re.search(r'/homedetails/([^/]+)/\d+_zpid/', asset_metadata["url"])
        if match:
            address_part = match.group(1)
            address = address_part.replace('-', ' ')
            log.debug(f"Extracted address: {address}")
        else:
            log.error(f"Could not extract address from URL: {asset_metadata['url']}")
            return None

        log.debug(f"filling out: {address}")

        # Find and fill search box
        search_xpath = '//input[@enterkeyhint="search"]'

        try:
            log.debug("Waiting for Zillow search box")
            page.wait_for_selector(f"xpath={search_xpath}", timeout=10000)

            log.debug(f"Filling search box with address: {address}")
            # Type address character by character
            for char in address:
                page.type(f"xpath={search_xpath}", char)
                jitter = random.uniform(0.75, 1.25)  # 25% jitter
                # page.wait_for_timeout(int(750 * jitter))  # Random delay between ~560ms and ~940ms
                page.wait_for_timeout(750)  # Random delay between ~560ms and ~940ms
            page.press(f"xpath={search_xpath}", "Enter")
            log.debug("Submitted search")
        except PlaywrightTimeoutError:
            log.error("Could not find Zillow search box")
            return None

        # Wait for valuation
        zillow_xpath = '//*[@id="home-details-home-values"]/div/div[1]/div/div/div[1]/div/p/h3'
        log.debug("Waiting for Zillow valuation element")
        zillow_price = extract_text_from_xpath(page, zillow_xpath, timeout=30000)
        if not zillow_price:
            log.warning(f"Could not find Zillow home value for {address}")
            return None

        log.debug(f"Zillow home value: {zillow_price}")
        return parse_currency_string_to_float(zillow_price)
    finally:
        page.close()

def get_redfin_valuation(browser, asset_metadata):
    """Get property valuation from Redfin."""
    page = browser.new_page()
    try:
        base_url = re.match(r'(https?://[^/]+)', asset_metadata["redfin"]).group(1)
        wait_for_page_load(page, base_url)
        wait_for_page_load(page, asset_metadata["redfin"])

        redfin_xpath = '//*[@data-rf-test-id="abp-price"]/div[@class="statsValue"]'
        redfin_price = extract_text_from_xpath(page, redfin_xpath)
        if not redfin_price:
            log.warning(f"Could not find Redfin home value for {asset_metadata['redfin']}")
            return None

        log.debug(f"Redfin home value: {redfin_price}")
        return parse_currency_string_to_float(redfin_price)
    finally:
        page.close()

# Main Logic
if "LUNCH_MONEY_API_KEY" not in os.environ:
    log.error("Lunch Money API key not set")
    exit(1)

log.info(f"Updating price data {datetime.now()}")

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
        log.info(f"Processing asset {lunch_money_asset_id}")
        if "kbb.com" in asset_metadata["url"]:
            price = get_kbb_valuation(browser, asset_metadata)
            if price is not None:
                update_asset_price(int(lunch_money_asset_id), price)
            else:
                log.warning(f"Could not retrieve price for asset {lunch_money_asset_id}")

        elif "zillow.com" in asset_metadata["url"]:
            zillow_value = get_zillow_valuation(browser, asset_metadata)
            if zillow_value is None:
                log.warning(f"Could not retrieve Zillow price for asset {lunch_money_asset_id}")
                continue

            # Check for Redfin and average if available
            if "redfin" in asset_metadata:
                redfin_value = get_redfin_valuation(browser, asset_metadata)
                if redfin_value is not None:
                    home_value = round((zillow_value + redfin_value) / 2)
                    log.info(f"Combined home value: {home_value}")
                else:
                    home_value = zillow_value
            else:
                home_value = zillow_value

            update_asset_price(int(lunch_money_asset_id), home_value)

        else:
            log.warning(f"Unsupported asset type for asset {lunch_money_asset_id}")

log.info("All assets processed")