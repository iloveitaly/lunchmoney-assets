import fs from "fs";
import process from "process";
import { executablePath } from "puppeteer";
import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";
import PluginREPL from "puppeteer-extra-plugin-repl";
import { LunchMoney } from "lunch-money";
import isPi from "detect-rpi";
puppeteer.use(StealthPlugin());
puppeteer.use(PluginREPL());
async function getBrowser() {
    const puppeteerOpts = {
        headless: true,
        // Increase the protocol timeout to 60 seconds
        // this fixes timeouts on slow machines (like a raspberry pi)
        protocolTimeout: 60000,
        // TODO this was for trying to debug puppeteer on raspberry pi
        // dumpio: false,
        // ignoreHTTPSErrors: true,
        args: [
        // '--disable-setuid-sandbox',
        // "--disable-dev-shm-usage",
        ],
    };
    // always use no sandbox
    // should be safe since only 3 known domains are accessed
    // required for docker and pi deployments and anyone that wants to use as root
    puppeteerOpts.args.push("--no-sandbox");
    if (isPi()) {
        puppeteerOpts.executablePath = "/usr/bin/chromium";
    }
    else {
        // https://stackoverflow.com/questions/74251875/puppeteer-error-an-executablepath-or-channel-must-be-specified-for-puppete
        puppeteerOpts.executablePath = executablePath();
    }
    return await puppeteer.launch(puppeteerOpts);
}
// NOTE cannot use `string(//object/@data)`, puppeteer does not support a non-element return
//      this function works around this limitation and extracts the string value from a xpath
async function extractTextFromXPath(browser, pageURL, xpath) {
    const page = await browser.newPage();
    await page.goto(pageURL, { timeout: 0 });
    // https://stackoverflow.com/questions/48165646/how-can-i-get-an-element-by-xpath/78054219#78054219
    const xpathSelector = `xpath/${xpath}`;
    try {
        // TODO I don't understand why, but this p-xpath thing isn't working
        await page.waitForSelector(xpathSelector);
    }
    catch (error) {
        if (error.constructor.name == "TimeoutError") {
            console.log("wait for xpath was not successful: ", xpathSelector);
        }
        else {
            throw error;
        }
    }
    // even if waiting fails, lets try to grab the content
    // https://github.com/puppeteer/puppeteer/issues/1838
    let textValue;
    try {
        textValue = await page.evaluate((xpath) => document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE).singleNodeValue?.textContent, xpath);
    }
    catch (error) {
        console.log(`Error pulling xpath (${xpath}) from page (${pageURL}) with error: ${error}`);
        await page.screenshot({
            path: `/tmp/xpath-error-${Date.now()}.png`,
            fullPage: true,
        });
        textValue = null;
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
function readJSON(path) {
    return JSON.parse(fs.readFileSync(path, "utf8"));
}
function parseCurrencyStringToFloat(currencyString) {
    return parseFloat(currencyString.replace(/[^0-9.]/g, ""));
}
async function extractKBBPrice(lunchMoneyAssetId, assetMetadata) {
    // the price data is hidden within a text element of a loaded SVG image
    // first extract the SVG path, then pull the text from it
    if (assetMetadata.mileageStart && assetMetadata.mileageDate) {
        const yearlyMileage = assetMetadata.yearlyMileage ?? 12000;
        const mileageStart = assetMetadata.mileageStart;
        const mileageDate = new Date(assetMetadata.mileageDate);
        // calculate the current mileage estimate
        const currentDate = new Date();
        const timeDiff = currentDate.getTime() - mileageDate.getTime();
        const daysPassed = timeDiff / (1000 * 60 * 60 * 24);
        const fractionalYear = daysPassed / 365.25; // accounting for leap years
        console.log(`Fractional year: ${fractionalYear}`);
        const mileage = Math.round(mileageStart + fractionalYear * yearlyMileage);
        console.log(`Adjusting mileage: ${mileage}`);
        // now update the `mileage` query string param on the url
        assetMetadata.url = assetMetadata.url.replace(/mileage=\d+/, `mileage=${mileage}`);
    }
    const svgPath = await extractTextFromXPath(browser, assetMetadata.url, 
    // TODO there's a priceAdvisorWrapper div, but the `object` is not always nested within it
    // "//*[@id='priceAdvisorWrapper']/*/object/@data"
    // NOTE cannot use `string(//object/@data)`, puppeteer does not support a non-element return
    "//object/@data");
    if (!svgPath) {
        console.log(`could not find svg path for ${assetMetadata.url}`);
        return;
    }
    const kbbPriceWithCurrency = await extractTextFromXPath(browser, svgPath, "//*[@id='RangeBox']/*[name()='text'][4]");
    if (!kbbPriceWithCurrency) {
        console.warn(`could not find kbb price on svg ${svgPath}`);
        return;
    }
    else {
        console.log(`kbb price: ${kbbPriceWithCurrency}`);
    }
    let kbbPrice = parseCurrencyStringToFloat(kbbPriceWithCurrency);
    if (assetMetadata.adjustment) {
        console.log(`applying adjustment of ${assetMetadata.adjustment}`);
        kbbPrice = kbbPrice + assetMetadata.adjustment;
    }
    await updateAssetPrice(parseInt(lunchMoneyAssetId), kbbPrice);
}
if (!process.env.LUNCH_MONEY_API_KEY) {
    console.error("Lunch Money API key not set");
    process.exit(1);
}
console.log(`Updating price data ${new Date()}`);
const lunchMoney = new LunchMoney({ token: process.env.LUNCH_MONEY_API_KEY });
const browser = await getBrowser();
const { ASSET_PATH } = process.env;
let assetsPath = ASSET_PATH;
if (!assetsPath) {
    assetsPath = `${process.cwd()}/assets.json`;
}
const assets = readJSON(assetsPath);
for (const [lunchMoneyAssetId, assetMetadata] of Object.entries(assets)) {
    if (assetMetadata.url.includes("kbb.com")) {
        await extractKBBPrice(lunchMoneyAssetId, assetMetadata);
    }
    else if (assetMetadata.url.includes("zillow.com")) {
        let homeValue;
        const zillowHomeValue = await extractTextFromXPath(browser, assetMetadata.url, 
        // if this breaks, load up a browser, identify the price, and copy the new xpath
        // https://www.zillow.com/homedetails/2090-Bedminster-Rd-Perkasie-PA-18944/8943331_zpid/
        '//*[@id="home-details-home-values"]/div/div[1]/div/div/div[1]/div/p/h3');
        if (!zillowHomeValue) {
            console.log(`could not find zillow home value for ${assetMetadata.url}`);
            continue;
        }
        console.log(`zillow home value: ${zillowHomeValue}`);
        // if redfin link provided, average out the two of them
        if (assetMetadata.redfin) {
            const redfinHomeValue = await extractTextFromXPath(browser, assetMetadata.redfin, 
            // NOTE if this changes, just load up a browser, identify the price, and copy the new xpath
            '//*[@data-rf-test-id="abp-price"]/div[@class="statsValue"]');
            if (redfinHomeValue) {
                console.log(`redfin: ${redfinHomeValue}, zillow: ${zillowHomeValue}`);
                homeValue = Math.round((parseCurrencyStringToFloat(redfinHomeValue) +
                    parseCurrencyStringToFloat(zillowHomeValue)) /
                    2);
                console.log(`refind home value: ${homeValue}`);
            }
            else {
                console.log(`could not find redfin home value for ${assetMetadata.redfin}`);
                homeValue = parseCurrencyStringToFloat(zillowHomeValue);
            }
        }
        else {
            homeValue = parseCurrencyStringToFloat(zillowHomeValue);
        }
        await updateAssetPrice(parseInt(lunchMoneyAssetId), homeValue);
    }
    else {
        console.error("unsupported asset type");
    }
}
await browser.close();
console.log("assets updated");
//# sourceMappingURL=index.js.map