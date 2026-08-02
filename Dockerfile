FROM node:20-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    XACTIONS_AUTH_TOKEN="" \
    XACTIONS_CONFIG_DIR=/data/.xactions \
    XACTIONS_HEADLESS=true \
    PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    CHROME_BIN=/usr/bin/chromium \
    PATH="/root/.local/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    curl \
    ca-certificates \
    tini \
    nano \
    chromium \
    fonts-liberation \
    libnss3 \
    libgtk-3-0 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libgbm1 \
    libx11-xcb1 \
    libxtst6 \
    libdrm2 \
    libu2f-udev \
    libvulkan1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxkbcommon0 \
    libxshmfence1 \
    libcups2 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    xdg-utils \
 && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml uv.lock /app/
RUN uv sync --locked --no-dev

RUN npm install -g xactions \
 && npm cache clean --force

COPY src /app/src

RUN mkdir -p /data/.xactions

EXPOSE 9096

ENTRYPOINT ["tini", "--"]
CMD ["uv", "run", "python", "-m", "src"]