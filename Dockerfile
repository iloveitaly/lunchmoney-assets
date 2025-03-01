FROM oven/bun:latest

LABEL maintainer="Michael Bianco <mike@mikebian.co>"
LABEL org.opencontainers.image.authors="Michael Bianco <mike@mikebian.co>" \
  org.opencontainers.image.source=https://github.com/iloveitaly/lunchmoney-assets \
  org.opencontainers.image.licenses="MIT" \
  org.opencontainers.image.title="Track asset values in lunchmoney" \
  org.opencontainers.image.description="Track asset value (car, home) in lunch money automatically"


# absolutely insane, but puppeteer is broken on ARM builds
# https://github.com/puppeteer/puppeteer/issues/7740
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# clean eliminates the need to manually `rm -rf` the cache
# trunk-ignore(hadolint/DL3008)
RUN set -eux; \
  \
  apt update; \
  apt install -y --no-install-recommends \
  bash \
  nano less \
  chromium chromium-driver; \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# run every hour by default, use `SCHEDULE=NONE` to run directly
ENV SCHEDULE="0 * * * *"

WORKDIR /app
COPY . ./

# this is the cleanest way to conditionally copy a file
# https://stackoverflow.com/a/46801962/129415
COPY *assets.json ./

# run after copying source to chache the earlier steps
RUN bun install --no-optional

CMD ["bun", "cron.ts"]