# Usage:
#   docker build -t lunchmoney-assets .
#   docker run --env-file .env -it lunchmoney-assets
#   docker run --env-file .env -it lunchmoney-assets bash

FROM node:22.5.1

LABEL maintainer="Michael Bianco <mike@mikebian.co>"
LABEL org.opencontainers.image.authors="Michael Bianco <mike@mikebian.co>" \
      org.opencontainers.image.source=https://github.com/iloveitaly/lunchmoney-assets \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.title="Track asset values in lunchmoney" \
      org.opencontainers.image.description="Track asset value (car, home) in lunch money automatically"

# clean eliminates the need to manually `rm -rf` the cache
# trunk-ignore(hadolint/DL3008)
RUN set -eux; \
  \
  apt-get update; \
  apt-get install -y --no-install-recommends \
    bash \
    nano less \
    chromium chromium-driver \
    cron; \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# run every hour by default, use `SCHEDULE=NONE` to run directly
ENV SCHEDULE "0 * * * *"

WORKDIR /app
COPY . ./

# this is the cleanest way to conditionally copy a file
# https://stackoverflow.com/a/46801962/129415
COPY *assets.json ./

# run after copying source to chache the earlier steps
RUN npm install --no-optional

CMD ["bash", "cron.sh"]