// puppeteer-extra is a drop-in replacement for puppeteer,
// it augments the installed puppeteer with plugin functionality
const puppeteer = require('puppeteer-extra')

// add stealth plugin and use defaults (all evasion techniques)
const StealthPlugin = require('puppeteer-extra-plugin-stealth')
puppeteer.use(StealthPlugin())
// puppeteer.use(require('puppeteer-extra-plugin-anonymize-ua')())

// https://sc-consulting.medium.com/puppeteer-on-raspbian-nodejs-3425ccea470e/
let browser = await puppeteer.launch({
  headless: false,
  dumpio: true,
  // userDataDir: './tmp/puppeteer',
  // ignoreDefaultArgs: ["--disable-extensions"],
  // executablePath: '/usr/bin/chromium',
  // executablePath: '/usr/bin/chromium-browser',
  // executablePath: '/usr/lib/chromium-browser/chromium-browser-v7',
  ignoreHTTPSErrors: true,
  args: [
    // '--no-sandbox',
    // '--disable-setuid-sandbox',
    // '--enable-features=NetworkService',
    // "--disable-dev-shm-usage",
    // "--disable-web-security",
    // "--disable-extensions",
    // "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.0 Safari/537.36"
    // "--disable-gpu"
  ]
});

// TODO might be this?
// https://github.com/berstend/puppeteer-extra/issues/451

// puppeteer usage as normal
  console.log('Running tests..')
  let page = await browser.newPage()
  await page.setBypassCSP(true)
  // page._client.send('Network.setBypassServiceWorker', {bypass: true})
  // https://github.com/berstend/puppeteer-extra/issues/588
  await page.goto('https://www.kbb.com/honda/odyssey/2016/ex-l-minivan-4d/?condition=good&intent=trade-in-sell&mileage=31000&modalview=false&options=6763005%7ctrue&pricetype=trade-in&vehicleid=411855', {timeout:0})
  debugger

  // https://stackoverflow.com/questions/52163547/node-js-puppeteer-how-to-set-navigation-timeout
  await page.setDefaultNavigationTimeout(60000);
  // await page.goto('https://www.kbb.com/bmw/5-series/2018/540i-xdrive-sedan-4d/?vehicleid=431625&intent=trade-in-sell&mileage=100&pricetype=private-party&condition=verygood&options=8121036|true')
  // await page.waitForTimeout(10000)
  debugger;

  // car_value_svg_url = browser.find_element_by_tag_name("object").get_attribute("data")
  // find a html element by tag name object
  // get the attribute data

  await page.$x("//object")
  await page.$x("//*[@id='RangeBox']/svg:text[4]/text()")
  await page.screenshot({ path: '/tmp/headless-test-result.png', fullPage: true })
  // await browser.close()