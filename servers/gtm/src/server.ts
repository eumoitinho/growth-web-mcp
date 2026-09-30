// Google Tag Manager MCP server for Cloud Run.
//
// Tools come unchanged from stape-io's google-tag-manager-mcp-core (Apache-2.0),
// the same package behind their hosted server and npm CLI. This file only adds:
//   1. Auth: Application Default Credentials (the Cloud Run runtime service
//      account) with the minimum scopes for the configured access mode.
//   2. A guard that checks every tool call's `action` against the access policy
//      (see policy.ts) before it reaches Google, so the agent gets a clear error
//      instead of a 403.
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import {
  createAuthFromEnv,
  createGtmMcpServer,
  GtmAuthProvider,
  registerGtmTools,
  resolveAuthMode,
  setLogSink,
} from "google-tag-manager-mcp-core";
import { GoogleAuth } from "google-auth-library";
import { serveStateless } from "./http.js";
import { GtmPolicy, policyFromEnv } from "./policy.js";

setLogSink((message, ...rest) => console.error(message, ...rest));

const policy = policyFromEnv(process.env);

function createAuth(scopes: string[]): GtmAuthProvider {
  // Local runs may pass explicit credentials exactly like the upstream CLI.
  if (resolveAuthMode(process.env) !== "unconfigured") {
    return createAuthFromEnv({ ...process.env, GTM_SCOPES: scopes.join(" ") });
  }
  const googleAuth = new GoogleAuth({ scopes });
  return {
    async getAccessToken() {
      const token = await googleAuth.getAccessToken();
      if (!token) throw new Error("ADC returned no access token for GTM.");
      return token;
    },
  };
}

// Wraps server.tool()/registerTool() so every handler checks the policy first.
function guarded(server: McpServer, policy: GtmPolicy): McpServer {
  const guardHandler =
    (tool: string, handler: (...a: unknown[]) => unknown) =>
    (input: unknown, ...rest: unknown[]) => {
      const action = (input as { action?: unknown } | undefined)?.action;
      const reason = typeof action === "string" ? policy.check(tool, action) : null;
      if (reason) {
        console.error(`[growth-gtm-mcp] refused ${tool}.${String(action)}: ${reason}`);
        return {
          isError: true,
          content: [{ type: "text", text: `Action '${String(action)}' on ${tool} refused. ${reason}` }],
        };
      }
      if (policy.mode === "write" && typeof action === "string") {
        console.error(`[growth-gtm-mcp] audit ${tool}.${action} ${JSON.stringify(input)}`);
      }
      return handler(input, ...rest);
    };

  return new Proxy(server, {
    get(target, prop, receiver) {
      if (prop === "tool") {
        return (...args: unknown[]) => {
          const last = args.length - 1;
          args[last] = guardHandler(String(args[0]), args[last] as never);
          if (typeof args[1] === "string") args[1] = `${policy.banner} ${args[1]}`;
          return (target.tool as (...a: unknown[]) => unknown).apply(target, args);
        };
      }
      if (prop === "registerTool") {
        return (name: string, config: { description?: string }, handler: never) =>
          target.registerTool(
            name,
            { ...config, description: `${policy.banner} ${config.description ?? ""}` },
            guardHandler(name, handler) as never,
          );
      }
      return Reflect.get(target, prop, receiver);
    },
  });
}

const auth = createAuth(policy.scopes);
console.error(`[growth-gtm-mcp] access mode: ${policy.banner} scopes: ${policy.scopes.join(" ")}`);

serveStateless("growth-gtm-mcp", () => {
  // Build the server without tools, then register upstream's default tool set
  // through the guarding proxy so every handler checks the policy.
  const server = createGtmMcpServer({
    auth,
    serverInfo: { name: "growth-gtm-mcp" },
    tools: [],
  });
  registerGtmTools(guarded(server, policy), { auth });
  return server;
});
