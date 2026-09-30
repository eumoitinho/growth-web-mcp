// HubSpot MCP server for Cloud Run.
//
// Reuses the tool implementations of HubSpot's official @hubspot/mcp-server
// (MIT) plus extraTools (forms, submissions, pipelines). Authenticates with a
// HubSpot private app token (PRIVATE_APP_ACCESS_TOKEN, mounted from Secret
// Manager).
//
//   HUBSPOT_ACCESS_MODE=read  (default) read tools only; pair with a private
//                             app that has read-only scopes.
//   HUBSPOT_ACCESS_MODE=write also the upstream write tools listed in
//                             UPSTREAM_WRITE_TOOLS, or only the subset named in
//                             HUBSPOT_WRITE_TOOLS (comma separated). Pair with a
//                             *separate* private app whose write scopes match.
//
// For humans in Claude/ChatGPT, HubSpot's hosted remote server
// (https://mcp.hubspot.com, OAuth per user) is a good complement; this service
// exists so an unattended agent has a stable, audited identity.
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
// Side-effect import: registers upstream tools into its registry.
import "@hubspot/mcp-server/dist/tools/toolsRegistry.js";
import { getTools, handleToolCall } from "@hubspot/mcp-server/dist/tools/index.js";
import { extraTools } from "./extraTools.js";
import { serveStateless } from "./http.js";

import { enabledTools, UPSTREAM_READ_TOOLS } from "./policy.js";

const ENABLED_UPSTREAM_TOOLS = enabledTools(process.env);

if (!process.env.PRIVATE_APP_ACCESS_TOKEN && !process.env.HUBSPOT_ACCESS_TOKEN) {
  console.error("[growth-hubspot-mcp] PRIVATE_APP_ACCESS_TOKEN is not set; tool calls will fail.");
}

const extraByName = new Map(extraTools.map((t) => [t.tool.name, t]));

function listTools() {
  const upstream = getTools().filter((t: { name: string }) => ENABLED_UPSTREAM_TOOLS.has(t.name));
  return [...upstream, ...extraTools.map((t) => t.tool)];
}

function createServer(): Server {
  const server = new Server(
    { name: "growth-hubspot-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: listTools() }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args = {} } = request.params;
    const extra = extraByName.get(name);
    if (extra) return extra.handleRequest(args);
    if (ENABLED_UPSTREAM_TOOLS.has(name)) {
      if (!UPSTREAM_READ_TOOLS.has(name)) {
        console.error(`[growth-hubspot-mcp] audit ${name} ${JSON.stringify(args)}`);
      }
      return handleToolCall(name, args);
    }
    return {
      isError: true,
      content: [
        {
          type: "text",
          text: `Tool '${name}' is not enabled on this deployment (HUBSPOT_ACCESS_MODE / HUBSPOT_WRITE_TOOLS).`,
        },
      ],
    };
  });

  return server;
}

serveStateless("growth-hubspot-mcp", createServer);
