// @hubspot/mcp-server ships JavaScript only; these are the internals we reuse.
declare module "@hubspot/mcp-server/dist/tools/toolsRegistry.js";

declare module "@hubspot/mcp-server/dist/tools/index.js" {
  export function getTools(): Array<{ name: string; [key: string]: unknown }>;
  export function handleToolCall(
    name: string,
    args: Record<string, unknown>,
  ): Promise<{ content: { type: string; text: string }[]; isError?: boolean }>;
}

declare module "@hubspot/mcp-server/dist/utils/client.js" {
  export default class HubSpotClient {
    constructor();
    request<T = unknown>(
      path: string,
      options?: { method?: string; body?: unknown; params?: Record<string, string | number | boolean> },
    ): Promise<T>;
  }
}
