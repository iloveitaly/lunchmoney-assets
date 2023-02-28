# Update Real Estate & Car Values in LunchMoney

Tool to update real estate and car values in [LunchMoney](https://mikebian.co/lunchmoney). Supports scraping values from Zillow, Redfin, and Kelly Bluebook.

Why build this tool rather than the existing scripts out there?

- The Kelly Bluebook page structure changed and the existing logic wasn't working for me
- I wanted a single tool to manage both real estate and cars
- Wanted a good excuse to play around with puppeteer

## Usage

I wrote this using node 17, but I imagine it will work with much older versions. Use `asdf install` to setup node if you haven't already.

```shell
cp .env-example .env
# generate a API key and add it to .env

touch assets.json
# add your assets to assets.json

npm install
node dist/index.js
```

Or, if you have a docker container setup, you can run it directly:

```shell
docker exec -i ca32c16fa00e node dist/index.js
```

### `assets.json` Structure

Specify the assets to be updated in the `assets.json` file. The key of the hash is the LunchMoney asset ID.

```json
{
  "23760": {
    "__comment": "you can specify a zillow and redfin link to set the balance as the average of the two",
    "url": "https://www.zillow.com/homes/your-home/123/",
    "redfin": "https://www.redfin.com/STATE/CITY/yourhome/home/123"
  },
  "23759": {
    "__comment": "kelly blue book link",
    "url": "https://www.kbb.com/your/car/year/model/?condition=good&intent=trade-in-sell&mileage=100000&modalview=false&options=6763005%7ctrue&pricetype=private-party"
  }
}
```

## Docker Deployment

https://hub.docker.com/r/iloveitaly/lunchmoney-assets

Copy your assets config into the container:

```shell
docker compose cp ./lunch-money-assets.json lunchmoney_assets:./app/assets.json
```

Or, if you are using docker without compose:

```shell
docker cp ./lunch-money-assets.json lunchmoney_assets:./app/assets.json
```

Set a `SCHEDULE` environment variable when starting the container to update the assets at a regular interval. The value should be a [cron expression](https://crontab.guru/).

```shell
docker run -d --name lunchmoney-assets -e SCHEDULE="0 0 * * *" iloveitaly/lunchmoney-assets
```

## Development

```shell
npx tsc --watch
```

## TODO

- [ ] throw a user-friendly error if `assets.json` is not defined
- [ ] It seems as though the KBB logic only works for private party priced URLs. Not sure why.
- [ ] Automatically calculate additional mileage based on time passed
