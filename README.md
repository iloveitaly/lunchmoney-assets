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

### `assets.json` File Path

The program first checks for the environment variable `ASSET_PATH` which should be a string path to the assets.json file to use. For example: `/home/assets.json`. If the environment variable doesn't exist, it then checks inside the current working directory of the node process. For docker deployments, this is inside the `/app` folder.

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
    "url": "https://www.kbb.com/your/car/year/model/?condition=good&intent=trade-in-sell&mileage=100000&modalview=false&options=6763005%7ctrue&pricetype=private-party",
    "mileageStart": 132800,
    "mileageDate": "11/29/23",
    "yearlyMileage": 8000
  },
  "23759": {
    "__comment": "a car that is more damaged than it looks",
    "url": "https://www.kbb.com/your/car/year/model/?condition=good&intent=trade-in-sell&mileage=100000&modalview=false&options=6763005%7ctrue&pricetype=private-party",
    "adjustment": -500
  }
}
```

Note that mileage can be optionally specified. If it is, the tool will calculate the depreciation based on the mileage and the date of the last update.

## Docker Deployment

https://hub.docker.com/r/iloveitaly/lunchmoney-assets

Here's the docker-compose file I use:

```yaml
lunchmoney_assets:
  container_name: lunchmoney-assets
  image: iloveitaly/lunchmoney-assets:latest
  restart: unless-stopped
  environment:
    - SCHEDULE=@monthly
    - LUNCH_MONEY_API_KEY=THE_KEY
```

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
docker run -d --name lunchmoney-assets -e SCHEDULE="0 0 * * *" -e LUNCH_MONEY_API_KEY=thekey -v ./assets.json:/app/assets.json iloveitaly/lunchmoney-assets
```

## Development

Setup your env (I use [direnv](https://direnv.net)):

```shell
cp .envrc-example .envrc
```

Compile typescript:

```shell
npm run dev
```

Get a list of all accounts in your lunchmoney account:

```shell
http GET https://dev.lunchmoney.app/v1/assets -A bearer -a $LUNCH_MONEY_API_KEY | jqp

# or match against a specific account
http GET https://dev.lunchmoney.app/v1/assets -A bearer -a $LUNCH_MONEY_API_KEY | jq '.assets | map(select(.name == "Camry"))'
```

## TODO

- [ ] throw a user-friendly error if `assets.json` is not defined
- [ ] It seems as though the KBB logic only works for private party priced URLs. Not sure why.
- [ ] Automatically calculate additional mileage based on time passed
