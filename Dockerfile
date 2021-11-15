# TODO this was meant for the pi installation, but I wasn't able to get it working

# Usage:
#   docker build -t lunchmoney-assets .
#   docker run --env-file .env -it lunchmoney-assets
#   docker run --env-file .env -it lunchmoney-assets bash

FROM node:17.1.0

# clean eliminates the need to manually `rm -rf` the cache
RUN set -eux; \
  \
  apt-get update; \
  apt-get install -y --no-install-recommends \
    bash \
    nano less \
    chromium chromium-driver \
    cron; \
  apt-get clean;

# run every hour by default, use `SCHEDULE=NONE` to run directly
ENV SCHEDULE "0 * * * *"

WORKDIR /app
COPY . ./

# run after copying source to chache the earlier steps
RUN npm install --no-optional

CMD ["bash", "cron.sh"]