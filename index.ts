import fs from "fs";
import puppeteer from "puppeteer-extra";

import StealthPlugin from "puppeteer-extra-plugin-stealth";
import PluginREPL from "puppeteer-extra-plugin-repl";
import { LunchMoney } from "lunch-money";
import dotenv from "dotenv";
import { isPrivateIdentifier } from "typescript";
import { PuppeteerLaunchOptions } from "puppeteer";
const isPi = require("detect-rpi");

puppeteer.use(StealthPlugin());
puppeteer.use(PluginREPL());

async function getBrowser() {
  const puppeteerOpts: PuppeteerLaunchOptions = {
    headless: true,
    // TODO this was for trying to debug puppeteer on raspberry pi
    // dumpio: false,
    // ignoreHTTPSErrors: true,
    args: [
      // '--disable-setuid-sandbox',
      // "--disable-dev-shm-usage",
    ],
  };

  if (isPi()) {
    puppeteerOpts.executablePath = "/usr/bin/chromium";
    puppeteerOpts.args!.push("--no-sandbox");
  }

  return await puppeteer.launch(puppeteerOpts);
}

// NOTE cannot use `string(//object/@data)`, puppeteer does not support a non-element return
//      this function works around this limitation and extracts the string value from a xpath
async function extractTextFromXPath(
  browser: any,
  pageURL: string,
  xpath: string
) {
  const page = await browser.newPage();
  await page.goto(pageURL, { timeout: 0 });

  try {
    await page.waitForXPath(xpath);
  } catch (TimeoutError) {
    console.log("wait for xpath was not successful");
  }

  // https://github.com/puppeteer/puppeteer/issues/1838
  let textValue;

  try {
    textValue = await page.evaluate(
      (xpath: string) =>
        document.evaluate(
          xpath,
          document,
          null,
          XPathResult.FIRST_ORDERED_NODE_TYPE
        ).singleNodeValue?.textContent,
      xpath
    );
  } catch (error) {
    console.log(
      `Error pulling xpath (${xpath}) from page (${pageURL}) with error: ${error}`
    );

    await page.screenshot({
      path: `/tmp/xpath-error-${Date.now()}.png`,
      fullPage: true,
    });

    textValue = null;
  }

  await page.close();
  return textValue;
}

async function updateAssetPrice(assetId: number, price: number) {
  console.log(`updating ${assetId} to price: ${price}`);

  const result = await lunchMoney.updateAsset({
    id: assetId,
    balance: price.toString(),
  });

  if (result.error) {
    console.log(`Error updating asset: ${result.error}`);
  }
}

function readJSON(path: string) {
  return JSON.parse(fs.readFileSync(path, "utf8"));
}

function parseCurrencyStringToFloat(currencyString: string) {
  return parseFloat(currencyString.replace(/[^0-9.]/g, ""));
}

dotenv.config();

if (!process.env.LUNCH_MONEY_API_KEY) {
  console.error("Lunch Money API key not set");
  process.exit(1);
}

const lunchMoney = new LunchMoney({ token: process.env.LUNCH_MONEY_API_KEY });
const browser = await getBrowser();

const assets: { [key: string]: { url: string; redfin?: string } } =
  readJSON("./assets.json");

for (const [lunchMoneyAssetId, assetMetadata] of Object.entries(assets)) {
  if (assetMetadata.url.includes("kbb.com")) {
    // the price data is hidden within a text element of a loaded SVG image
    // first extract the SVG path, then pull the text from it

    const svgPath = await extractTextFromXPath(
      browser,
      assetMetadata.url,
      // TODO there's a priceAdvisorWrapper div, but the `object` is not always nested within it
      // "//*[@id='priceAdvisorWrapper']/*/object/@data"

      // NOTE cannot use `string(//object/@data)`, puppeteer does not support a non-element return
      "//object/@data"
    );

    if (!svgPath) {
      console.log(`could not find svg path for ${assetMetadata.url}`);
      continue;
    }

    const kbbPrice = await extractTextFromXPath(
      browser,
      svgPath,
      "//*[@id='RangeBox']/*[name()='text'][4]"
    );

    if (!kbbPrice) {
      console.log(`could not find kbb price on svg ${svgPath}`);
      continue;
    }

    await updateAssetPrice(
      parseInt(lunchMoneyAssetId),
      parseCurrencyStringToFloat(kbbPrice)
    );
  } else if (assetMetadata.url.includes("zillow.com")) {
    let homeValue;
    const zillowHomeValue = await extractTextFromXPath(
      browser,
      assetMetadata.url,
      '//*[@id="home-details-home-values"]/div/div[1]/div/div/div[1]/div/p/h3'
    );

    if (!zillowHomeValue) {
      console.log(`could not find zillow home value for ${assetMetadata.url}`);
      continue;
    }

    // if redfin link provided, average out the two of them
    if (assetMetadata.redfin) {
      const redfinHomeValue = await extractTextFromXPath(
        browser,
        assetMetadata.redfin,
        // NOTE if this changes, just load up a browser, identify the price, and copy the new xpath
        '//*[@data-rf-test-id="abp-price"]/div[@class="statsValue"]'
      );

      if (redfinHomeValue) {
        console.log(`redfin: ${redfinHomeValue}, zillow: ${zillowHomeValue}`);

        homeValue = Math.round(
          (parseCurrencyStringToFloat(redfinHomeValue) +
            parseCurrencyStringToFloat(zillowHomeValue)) /
            2
        );
      } else {
        console.log(
          `could not find redfin home value for ${assetMetadata.redfin}`
        );
        homeValue = parseCurrencyStringToFloat(zillowHomeValue);
      }
    } else {
      homeValue = parseCurrencyStringToFloat(zillowHomeValue);
    }

    await updateAssetPrice(parseInt(lunchMoneyAssetId), homeValue);
  } else {
    console.error("unsupported asset type");
  }
}

await browser.close();
console.log("assets updated");
