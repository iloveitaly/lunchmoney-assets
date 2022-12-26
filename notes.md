# Raspberry Pi Notes

I wanted this to run in a docker container on my raspberry pi, but I couldn't get it to work.

// https://sc-consulting.medium.com/puppeteer-on-raspbian-nodejs-3425ccea470e/
https://github.com/berstend/puppeteer-extra/issues/451
https://github.com/berstend/puppeteer-extra/issues/588
https://github.com/testimio/root-cause interesting debugging tool

Can't get this running on the Pi:

```
[1112/141310.565073:INFO:CONSOLE(4)] "Uncaught (in promise) TypeError: Failed to register a ServiceWorker for scope ('https://www.kbb.com/') with script ('https://www.kbb.com/akam-sw.js'): A bad HTTP response code (403) was received when fetching the script.", source: kbburl (4)
```

Locally, with the same code, it works fine:
'HeadlessChrome/93.0.4577.0'

The pi version is:

'HeadlessChrome/90.0.4430.212'

The pi version of head chrome is: Version 88.0.4324.187 (Official Build) Built on Raspbian , running on Raspbian 10 (32-bit)

- If I open up chromium, I can load the page on a PI
- Running chromium on a pi via node works, but it causes weird errors
- The chromium desktop version if older (88)
- Puppeteer doesn't have a version out to support 88 officially

Even upgrading to chromium 92 didn't fix the issue. There is something specific to chromium being controlled by puppeteer on raspberrypi that it can detect.
