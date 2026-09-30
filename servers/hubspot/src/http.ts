// Stateless Streamable HTTP host for an MCP server factory.
// Kept identical in servers/gtm and servers/hubspot (each image builds on its own).
//
// Every POST /mcp gets a fresh server + transport: no session state, so Cloud Run
// can scale horizontally. Access control is Cloud Run IAM (roles/run.invoker);
// this process never sees unauthenticated traffic when deployed as documented.
import { createServer, IncomingMessage, ServerResponse } from "node:http";
import type { Server } from "@modelcontextprotocol/sdk/server/index.js";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

const MAX_BODY_BYTES = 4 * 1024 * 1024;

function sendJson(res: ServerResponse, status: number, payload: unknown): void {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(payload));
}

async function readJson(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    size += (chunk as Buffer).length;
    if (size > MAX_BODY_BYTES) throw new Error("request body too large");
    chunks.push(chunk as Buffer);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export function serveStateless(
  name: string,
  factory: () => McpServer | Server,
): void {
  const port = Number(process.env.PORT ?? 8080);

  const httpServer = createServer(async (req, res) => {
    const { pathname } = new URL(req.url ?? "/", "http://localhost");

    if (pathname === "/healthz") return sendJson(res, 200, { status: "ok" });
    if (pathname !== "/mcp") return sendJson(res, 404, { error: "not found" });
    if (req.method !== "POST") {
      // Stateless server: no standalone SSE stream (GET) and no sessions (DELETE).
      return sendJson(res, 405, {
        jsonrpc: "2.0",
        error: { code: -32000, message: "Method not allowed." },
        id: null,
      });
    }

    let body: unknown;
    try {
      body = await readJson(req);
    } catch (error) {
      return sendJson(res, 400, {
        jsonrpc: "2.0",
        error: { code: -32700, message: `Parse error: ${String(error)}` },
        id: null,
      });
    }

    const server = factory();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    });
    res.on("close", () => {
      void transport.close();
      void server.close();
    });

    try {
      await server.connect(transport);
      await transport.handleRequest(req, res, body);
    } catch (error) {
      console.error(`[${name}] request failed`, error);
      if (!res.headersSent) {
        sendJson(res, 500, {
          jsonrpc: "2.0",
          error: { code: -32603, message: "Internal server error" },
          id: null,
        });
      }
    }
  });

  httpServer.listen(port, "0.0.0.0", () => {
    console.error(`[${name}] listening on :${port}/mcp`);
  });
}
