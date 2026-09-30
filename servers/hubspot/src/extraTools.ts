// Read-only HubSpot tools missing from @hubspot/mcp-server that the inbound
// funnel investigation needs: form definitions (fields, hidden UTM fields,
// lifecycle options), raw form submissions (pageUrl, hutk presence) and CRM
// pipelines/stages (where a lead is supposed to land).
//
// Private app scopes needed: forms, crm.objects.contacts.read (submissions),
// crm.objects.deals.read / tickets (pipelines).
import HubSpotClient from "@hubspot/mcp-server/dist/utils/client.js";

type JsonSchema = Record<string, unknown>;
type ToolResponse = {
  content: { type: "text"; text: string }[];
  isError?: boolean;
};

export interface ExtraTool {
  tool: {
    name: string;
    description: string;
    inputSchema: JsonSchema;
    annotations: Record<string, boolean>;
  };
  handleRequest(args: Record<string, unknown>): Promise<ToolResponse>;
}

let client: HubSpotClient | undefined;
function hubspot(): HubSpotClient {
  client ??= new HubSpotClient();
  return client;
}

const READ_ONLY = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true };

function ok(data: unknown): ToolResponse {
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
}

function fail(error: unknown): ToolResponse {
  return {
    isError: true,
    content: [{ type: "text", text: `Error: ${error instanceof Error ? error.message : String(error)}` }],
  };
}

function requireString(args: Record<string, unknown>, key: string): string {
  const value = args[key];
  if (typeof value !== "string" || !value.trim()) throw new Error(`'${key}' is required`);
  return encodeURIComponent(value.trim());
}

function pageParams(args: Record<string, unknown>, maxLimit: number): Record<string, string> {
  const params: Record<string, string> = {};
  const limit = Number(args.limit ?? maxLimit);
  params.limit = String(Math.min(Math.max(1, Number.isFinite(limit) ? limit : maxLimit), maxLimit));
  if (typeof args.after === "string" && args.after) params.after = args.after;
  return params;
}

function tool(
  name: string,
  description: string,
  properties: JsonSchema,
  required: string[],
  run: (args: Record<string, unknown>) => Promise<unknown>,
): ExtraTool {
  return {
    tool: {
      name,
      description,
      inputSchema: { type: "object", properties, required, additionalProperties: false },
      annotations: READ_ONLY,
    },
    async handleRequest(args) {
      try {
        return ok(await run(args ?? {}));
      } catch (error) {
        return fail(error);
      }
    },
  };
}

const paging = {
  limit: { type: "integer", minimum: 1, description: "Page size." },
  after: { type: "string", description: "Paging cursor from the previous response (paging.next.after)." },
};

export const extraTools: ExtraTool[] = [
  tool(
    "hubspot-list-forms",
    "Lists HubSpot forms (id, name, formType, createdAt, updatedAt, archived). Use to map every website form / LP form to its HubSpot form GUID.",
    {
      ...paging,
      archived: { type: "boolean", description: "Return archived forms instead of active ones." },
      formTypes: {
        type: "array",
        items: { type: "string", enum: ["hubspot", "captured", "flow", "blog_comment", "all"] },
        description: "Form types to include. 'captured' = non-HubSpot forms collected by the tracking code. Default: all.",
      },
    },
    [],
    async (args) => {
      const params = pageParams(args, 100);
      if (typeof args.archived === "boolean") params.archived = String(args.archived);
      params.formTypes = Array.isArray(args.formTypes) && args.formTypes.length ? args.formTypes.join(",") : "all";
      return hubspot().request("/marketing/v3/forms", { params });
    },
  ),
  tool(
    "hubspot-get-form",
    "Returns one form definition: field groups (including hidden fields such as utm_* or form_origin), legal consent, and configuration (lifecycleStages set on submit, notification recipients, post-submit action). Core evidence for 'form X lands in the wrong funnel'.",
    { formId: { type: "string", description: "Form GUID." } },
    ["formId"],
    async (args) => hubspot().request(`/marketing/v3/forms/${requireString(args, "formId")}`),
  ),
  tool(
    "hubspot-list-form-submissions",
    "Lists recent submissions of a form, newest first: submittedAt, pageUrl and submitted values. Check pageUrl (which site/LP/subdomain sent it) and whether UTM hidden fields were filled.",
    { formId: { type: "string", description: "Form GUID." }, ...paging },
    ["formId"],
    async (args) =>
      hubspot().request(`/form-integrations/v1/submissions/forms/${requireString(args, "formId")}`, {
        params: pageParams(args, 50),
      }),
  ),
  tool(
    "hubspot-list-pipelines",
    "Lists pipelines and their stages (id, label, displayOrder, metadata) for deals, tickets or leads. Use to translate stage IDs found on records into names and to define the expected funnel.",
    {
      objectType: {
        type: "string",
        enum: ["deals", "tickets", "leads"],
        description: "CRM object whose pipelines to list.",
      },
    },
    ["objectType"],
    async (args) => hubspot().request(`/crm/v3/pipelines/${requireString(args, "objectType")}`),
  ),
];
