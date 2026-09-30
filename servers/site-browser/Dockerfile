# Headless Chrome + Chrome DevTools MCP (official, github.com/ChromeDevTools/chrome-devtools-mcp)
# bridged from stdio to Streamable HTTP by supergateway.
FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg fonts-liberation fonts-noto-color-emoji \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Pinned on purpose; bump deliberately and re-run scripts/smoke_test.py.
RUN npm install -g --no-audit --no-fund chrome-devtools-mcp@1.10.1 supergateway@4.0.0

COPY start.sh /usr/local/bin/start.sh
RUN chmod +x /usr/local/bin/start.sh

USER node
ENV PORT=8080 CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS=1
EXPOSE 8080
CMD ["start.sh"]
