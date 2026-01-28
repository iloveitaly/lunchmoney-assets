# for devcontainer development
setup:
	apt-get update
	apt-get install chromium chromium-driver

	npm install

build:
	docker build -t lunchmoney-assets .

build_run: build
	docker run --env-file .env -it lunchmoney-assets

build_shell: build
	docker run -v ./assets.json:/app/assets.json  --env LUNCH_MONEY_API_KEY=$$LUNCH_MONEY_API_KEY -it lunchmoney-assets bash -l