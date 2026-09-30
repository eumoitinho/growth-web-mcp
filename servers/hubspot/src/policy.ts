export const UPSTREAM_READ_TOOLS = new Set([
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

export function enabledTools(env: NodeJS.ProcessEnv): Set<string> {
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

