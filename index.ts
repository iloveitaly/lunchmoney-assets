import fs from "fs";
import puppeteer from "puppeteer-extra";

import StealthPlugin from "puppeteer-extra-plugin-stealth";
import PluginREPL from "puppeteer-extra-plugin-repl";
import { LunchMoney, Asset } from "lunch-money";
import dotenv from "dotenv";
import repl from "repl";
import { convertToObject, updateTypeAssertion } from "typescript";

puppeteer.use(StealthPlugin());
puppeteer.use(PluginREPL());

async function getBrowser() {
  return await puppeteer.launch({
    headless: true,

    // dumpio: false,
    // executablePath: '/usr/bin/chromium',
    // ignoreHTTPSErrors: true,

    args: [
      // '--no-sandbox',
      // '--disable-setuid-sandbox',
      // "--disable-dev-shm-usage",
    ],
  });
}

async function getXPathFromPage(browserReference, pageURL, xpath) {
  const page = await browserReference.newPage();
  // await page.setDefaultNavigationTimeout(60000);
  await page.goto(pageURL, { timeout: 0 });
  // await page.repl();
  // await p.evaluate((e) => e.textContent, (await p.$x("//object/@data"))[0])
  return await page.$x(xpath);
}

async function extractTextContent(page, element) {
  return await page.evaluate((e) => e.textContent, element[0]);
}

// NOTE cannot use `string(//object/@data)`, puppeteer does not support a non-element return
//      this function works around this limitation
async function extractTextFromXPath(browser, pageURL, xpath) {
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
      (xpath) =>
        document.evaluate(
          xpath,
          document,
          null,
          XPathResult.FIRST_ORDERED_NODE_TYPE
        ).singleNodeValue.textContent,
      xpath
    );
  } catch (error) {
    console.log(`Error pulling xpath: ${error}`);

    await page.screenshot({
      path: `/tmp/xpath-error-${Date.now()}.png`,
      fullPage: true,
    });
  }

  await page.close();
  return textValue;
}

async function updateAssetPrice(assetId, price) {
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

const assets: { [key: string]: { url: string; redfin?: string } } =
  readJSON("./assets.json");

const browser = await getBrowser();
for (const [lunchMoneyAssetId, assetMetadata] of Object.entries(assets)) {
  if (assetMetadata.url.includes("kbb.com")) {
    // the price data is hidden within a text element of a loaded SVG image
    // first extract the SVG path, then pull the text from it

    const svgPath = await extractTextFromXPath(
      browser,
      assetMetadata.url,
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

    await updateAssetPrice(
      lunchMoneyAssetId,
      parseCurrencyStringToFloat(kbbPrice)
    );
  } else if (assetMetadata.url.includes("zillow.com")) {
    let homeValue;
    const zillowHomeValue = await extractTextFromXPath(
      browser,
      assetMetadata.url,
      '//*[@id="home-details-home-values"]/div/div[1]/div/div/div[1]/div/p/h3'
    );

    // if redfin link provided, average out the two of them
    if (assetMetadata.redfin) {
      const redfinHomeValue = await extractTextFromXPath(
        browser,
        assetMetadata.redfin,
        // NOTE if this changes, just load up a browser, identify the price, and copy the new xpath
        '//*[@id="content"]/div[12]/div[2]/div[1]/div/div[1]/div/div/div/div[1]/div/div[1]/div/span'
      );

      console.log(`redfin: ${redfinHomeValue}, zillow: ${zillowHomeValue}`);

      homeValue = Math.round(
        (parseCurrencyStringToFloat(redfinHomeValue) +
          parseCurrencyStringToFloat(zillowHomeValue)) /
          2
      );
    } else {
      homeValue = parseCurrencyStringToFloat(zillowHomeValue);
    }

    await updateAssetPrice(lunchMoneyAssetId, homeValue);
  } else {
    console.error("unsupported asset type");
  }
}

await browser.close();
console.log("assets updated");
