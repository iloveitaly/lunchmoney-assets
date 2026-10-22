[![Release Notes](https://img.shields.io/github/release/iloveitaly/lunchmoney-assets)](https://github.com/iloveitaly/lunchmoney-assets/releases)
[![Downloads](https://static.pepy.tech/badge/lunchmoney-assets/month)](https://pepy.tech/project/lunchmoney-assets)
![GitHub CI Status](https://github.com/iloveitaly/lunchmoney-assets/actions/workflows/build_and_publish.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Synchronize LunchMoney Asset Balances with Real Estate and Vehicle Valuations

I'm a big fan of LunchMoney for tracking my finances, but manually updating home and car values is a chore. I wrote this tool to automate that process by scraping Zillow, Redfin, and Kelley Blue Book. It calculates current vehicle mileage and even averages real estate estimates to keep my net worth tracking as accurate as possible without the manual overhead.

## Installation

```bash
uv add lunchmoney-assets
```

## Usage

I usually run this monthly to keep my balances fresh. You'll need an `assets.json` file to define what you want to track. The key for each entry is the LunchMoney asset ID.

Run the tool:

```bash
uv run lunchmoney-assets
```

If you want to check the values without pushing them to LunchMoney, use the dry-run flag:

```bash
uv run lunchmoney-assets --dry-run
```

### `assets.json` Structure

Specify the assets to be updated in the `assets.json` file. The key of the hash is the LunchMoney asset ID.

```json
{
  "23760": {
    "url": "https://www.zillow.com/homes/your-home/123/",
    "redfin": "https://www.redfin.com/STATE/CITY/yourhome/home/123"
  },
  "23759": {
    "url": "https://www.kbb.com/your/car/year/model/?condition=good&intent=trade-in-sell&mileage=100000&modalview=false&options=6763005%7ctrue&pricetype=private-party",
    "mileageStart": 132800,
    "mileageDate": "2023-11-29",
    "yearlyMileage": 8000
  },
  "23758": {
    "url": "https://www.kbb.com/your/car/year/model/...",
    "adjustment": -500
  }
}
```

Note that mileage can be optionally specified. If it is, the tool will calculate the current mileage based on the `mileageStart`, `mileageDate`, and `yearlyMileage`.

## Features

* **Real Estate Averaging**: Scrapes both Zillow and Redfin, using the average of both for a more balanced valuation.
* **Vehicle Valuations**: Pulls private party values from KBB using Firecrawl's LLM extraction.
* **Dynamic Mileage**: Automatically estimates your car's current mileage based on a starting date and yearly average so you don't have to update it manually.
* **Manual Adjustments**: Support for adding or subtracting fixed amounts from the scraped value to account for specific property or vehicle conditions.
* **Robust Scraping**: Built on Firecrawl, which handles the heavy lifting of navigating complex page structures.

## Local CLI development

Run `just install_editable` to install this checkout globally in editable mode. Source changes are reflected without reinstalling.

This requires `uv`, `just`, `zsh`, and `jq`. If mise is available, the recipe also updates every installed `pipx:lunchmoney-assets` environment so mise can use the local checkout. Re-run after mise upgrades, which replace those editable installations.

## [MIT License](LICENSE.md)

---

*This project was created from [iloveitaly/python-package-template](https://github.com/iloveitaly/python-package-template)*
