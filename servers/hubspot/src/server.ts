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

const UPSTREAM_READ_TOOLS = new Set([
  "hubspot-get-user-details",
  "hubspot-list-objects",
  "hubspot-search-objects",
  "hubspot-batch-read-objects",
  "hubspot-get-schemas",
  "hubspot-list-properties",
  "hubspot-get-property",
  "hubspot-list-associations",
  "hubspot-get-association-definitions",
  "hubspot-get-engagement",
  "hubspot-list-workflows",
  "hubspot-get-workflow",
  "hubspot-get-link",
]);

const UPSTREAM_WRITE_TOOLS = [
  "hubspot-batch-update-objects",
  "hubspot-batch-create-objects",
  "hubspot-batch-create-associations",
  "hubspot-create-property",
  "hubspot-update-property",
  "hubspot-create-engagement",
  "hubspot-update-engagement",
];

function enabledTools(env: NodeJS.ProcessEnv): Set<string> {
  const mode = (env.HUBSPOT_ACCESS_MODE ?? "read").toLowerCase();
  if (mode !== "read" && mode !== "write") {
    throw new Error(`HUBSPOT_ACCESS_MODE must be 'read' or 'write', got '${mode}'.`);
  }
  const enabled = new Set(UPSTREAM_READ_TOOLS);
  if (mode === "write") {
    const requested = env.HUBSPOT_WRITE_TOOLS?.split(",").map((t) => t.trim()).filter(Boolean);
    for (const name of requested ?? UPSTREAM_WRITE_TOOLS) {
      if (!UPSTREAM_WRITE_TOOLS.includes(name)) throw new Error(`Unknown HubSpot write tool '${name}'.`);
      enabled.add(name);
    }
  }
  console.error(`[growth-hubspot-mcp] access mode: ${mode}; write tools: ${[...enabled].filter((t) => UPSTREAM_WRITE_TOOLS.includes(t)).join(", ") || "none"}`);
  return enabled;
}

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
