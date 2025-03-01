import json
import os
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from camoufox.sync_api import Camoufox

# Utility Functions

def parse_currency_string_to_float(currency_string):
    """Convert a currency string (e.g., '$12,345.67') to a float."""
    return float(re.sub(r'[^0-9.]', '', currency_string))

def extract_text_from_xpath(browser, url, xpath):
    """Extract text or attribute value from a webpage using XPath."""
    page = browser.new_page()
    page.goto(url, timeout=0)  # No timeout for initial navigation
    try:
        page.wait_for_selector(f'xpath={xpath}', timeout=60000)  # Wait up to 60 seconds
    except PlaywrightTimeoutError:
        print(f"Wait for XPath was not successful: {xpath}")
    
    # Evaluate XPath and return text content or attribute value
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
        "Content-Type": "application/json"
    }
    data = {"balance": str(price)}
    response = requests.put(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Error updating asset: {response.json().get('error')}")

# Main Logic

# Check for API key
if 'LUNCH_MONEY_API_KEY' not in os.environ:
    print("Lunch Money API key not set")
    exit(1)

print(f"Updating price data {datetime.now()}")

# Load assets from JSON file
assets_path = os.environ.get('ASSET_PATH', 'assets.json')
with open(assets_path, 'r') as f:
    assets = json.load(f)

# Launch Playwright browser
with Camoufox() as browser:
    for lunch_money_asset_id, asset_metadata in assets.items():
        if 'kbb.com' in asset_metadata['url']:
            # Handle KBB (car valuation)
            # Adjust mileage if provided
            if 'mileageStart' in asset_metadata and 'mileageDate' in asset_metadata:
                yearly_mileage = asset_metadata.get('yearlyMileage', 12000)
                mileage_start = asset_metadata['mileageStart']
                mileage_date = datetime.strptime(asset_metadata['mileageDate'], '%Y-%m-%d')
                current_date = datetime.now()
                days_passed = (current_date - mileage_date).days
                fractional_year = days_passed / 365.25
                print(f"Fractional year: {fractional_year}")
                mileage = round(mileage_start + fractional_year * yearly_mileage)
                print(f"Adjusting mileage: {mileage}")
                asset_metadata['url'] = re.sub(r'mileage=\d+', f'mileage={mileage}', asset_metadata['url'])
            
            # Extract SVG path and price
            svg_path = extract_text_from_xpath(browser, asset_metadata['url'], "//object/@data")
            if svg_path:
                kbb_price_with_currency = extract_text_from_xpath(
                    browser, svg_path, "//*[@id='RangeBox']/*[name()='text'][4]"
                )
                if kbb_price_with_currency:
                    print(f"kbb price: {kbb_price_with_currency}")
                    kbb_price = parse_currency_string_to_float(kbb_price_with_currency)
                    if 'adjustment' in asset_metadata:
                        print(f"applying adjustment of {asset_metadata['adjustment']}")
                        kbb_price += asset_metadata['adjustment']
                    update_asset_price(int(lunch_money_asset_id), kbb_price)
                else:
                    print(f"Could not find KBB price on SVG {svg_path}")
            else:
                print(f"Could not find SVG path for {asset_metadata['url']}")
        
        elif 'zillow.com' in asset_metadata['url']:
            # Handle Zillow (real estate valuation)
            zillow_xpath = '//*[@id="home-details-home-values"]/div/div[1]/div/div/div[1]/div/p/h3'
            zillow_price = extract_text_from_xpath(browser, asset_metadata['url'], zillow_xpath)
            if not zillow_price:
                print(f"Could not find Zillow home value for {asset_metadata['url']}")
                continue
            print(f"zillow home value: {zillow_price}")
            zillow_value = parse_currency_string_to_float(zillow_price)
            
            # Check for Redfin and average if available
            if 'redfin' in asset_metadata:
                redfin_xpath = '//*[@data-rf-test-id="abp-price"]/div[@class="statsValue"]'
                redfin_price = extract_text_from_xpath(browser, asset_metadata['redfin'], redfin_xpath)
                if redfin_price:
                    print(f"redfin: {redfin_price}, zillow: {zillow_price}")
                    redfin_value = parse_currency_string_to_float(redfin_price)
                    home_value = round((zillow_value + redfin_value) / 2)
                    print(f"redfin home value: {home_value}")
                else:
                    print(f"Could not find Redfin home value for {asset_metadata['redfin']}")
                    home_value = zillow_value
            else:
                home_value = zillow_value
            
            update_asset_price(int(lunch_money_asset_id), home_value)
        
        else:
            print("Unsupported asset type")
    
    browser.close()

print("Assets updated")