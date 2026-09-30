#!/bin/sh
# One chrome-devtools-mcp process (and one isolated headless Chrome profile)
# per MCP session. Sessions idle for SESSION_TIMEOUT_MS are closed.
#
# --no-sandbox: Chrome's own sandbox needs kernel features Cloud Run does not
# grant to non-root users. The container itself is the isolation boundary: it
# holds no credentials (its service account has no roles) and is ephemeral.
#
# supergateway exits when its stdin reaches EOF, and Cloud Run starts the
# container with stdin at EOF. Opening a FIFO read-write (`<>`) gives it a stdin
# that never ends; `exec` keeps supergateway as PID 1 so it gets SIGTERM directly.
set -eu

CHROME_DEVTOOLS_FLAGS="${CHROME_DEVTOOLS_FLAGS:---headless --isolated --no-usage-statistics --chrome-arg=--no-sandbox --viewport=1366x768 --screenshot-format=jpeg --screenshot-max-width=1366}"

STDIN_FIFO="$(mktemp -u)"
mkfifo "$STDIN_FIFO"

exec supergateway \
  --stdio "chrome-devtools-mcp ${CHROME_DEVTOOLS_FLAGS} ${CHROME_DEVTOOLS_EXTRA_FLAGS:-}" \
  --outputTransport streamableHttp \
  --streamableHttpPath /mcp \
  --stateful \
  --sessionTimeout "${SESSION_TIMEOUT_MS:-900000}" \
  --port "${PORT:-8080}" \
  --logLevel info \
  <>"$STDIN_FIFO"
