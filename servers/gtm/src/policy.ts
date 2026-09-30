// Access policy for the GTM tools: which `action` of which gtm_* tool may run,
// and which OAuth scopes the process asks for.
//
//   GTM_ACCESS_MODE=read   (default) get/list-style actions only, readonly scope.
//   GTM_ACCESS_MODE=write  also create/update/revert/versioning inside workspaces.
//     GTM_ALLOW_DELETE=true   additionally allows `remove`.
//     GTM_ALLOW_PUBLISH=true  additionally allows `publish` / `setLatest`
//                             (i.e. changes go live on the site).
//
// Account, user-permission, environment and container-level surgery stay
// read-only in every mode: those are admin operations for a human.
// The Google-side permission of the service account (Read / Edit / Approve /
// Publish in GTM) is the real boundary; this policy keeps the agent honest and
// gives it clear errors.

const SCOPE = "https://www.googleapis.com/auth/tagmanager";

export const READ_ACTIONS = [
  "get",
  "list",
  "live", // gtm_version: the published version
  "latest", // gtm_version_header
  "lookup", // gtm_container: find container by tag id / destination
  "snippet", // gtm_container: install snippet
  "getStatus", // gtm_workspace: pending changes and conflicts
  "entities", // gtm_folder: entities inside a folder
];

const WRITE_ACTIONS = [
  "create",
  "update",
  "revert",
  "undelete",
  "createVersion", // gtm_workspace: snapshot a workspace into a (unpublished) version
  "quickPreview",
  "sync",
  "resolveConflict",
  "moveEntitiesToFolder",
];

const DELETE_ACTIONS = ["remove"];
const PUBLISH_ACTIONS = ["publish", "setLatest"];

const ALWAYS_READ_ONLY_TOOLS = new Set([
  "gtm_account",
  "gtm_user_permission",
  "gtm_environment",
  "gtm_container",
]);

export type AccessMode = "read" | "write";

export interface GtmPolicy {
  mode: AccessMode;
  scopes: string[];
  banner: string;
  /** Returns null when allowed, otherwise the reason shown to the agent. */
  check(tool: string, action: string): string | null;
}

const flag = (value: string | undefined) => value === "true" || value === "1";

export function policyFromEnv(env: NodeJS.ProcessEnv): GtmPolicy {
  const raw = (env.GTM_ACCESS_MODE ?? "read").toLowerCase();
  if (raw !== "read" && raw !== "write") {
    throw new Error(`GTM_ACCESS_MODE must be 'read' or 'write', got '${raw}'.`);
  }
  const mode: AccessMode = raw;
  const allowDelete = mode === "write" && flag(env.GTM_ALLOW_DELETE);
  const allowPublish = mode === "write" && flag(env.GTM_ALLOW_PUBLISH);

  const read = new Set(READ_ACTIONS);
  const allowed = new Set(READ_ACTIONS);
  if (mode === "write") WRITE_ACTIONS.forEach((a) => allowed.add(a));
  if (allowDelete) DELETE_ACTIONS.forEach((a) => allowed.add(a));
  if (allowPublish) PUBLISH_ACTIONS.forEach((a) => allowed.add(a));

  const scopes = [`${SCOPE}.readonly`];
  if (mode === "write") scopes.push(`${SCOPE}.edit.containers`, `${SCOPE}.edit.containerversions`);
  if (allowPublish) scopes.push(`${SCOPE}.publish`);

  const banner =
    mode === "read"
      ? "[READ-ONLY deployment]"
      : `[WRITE deployment: edits${allowDelete ? " + delete" : ""}${allowPublish ? " + publish" : ", no publish"}]`;

  return {
    mode,
    scopes,
    banner,
    check(tool, action) {
      if (read.has(action)) return null;
      if (ALWAYS_READ_ONLY_TOOLS.has(tool)) {
        return `${tool} is read-only in every mode (admin operation). Ask a human.`;
      }
      if (allowed.has(action)) return null;
      if (mode === "read") {
        return "This GTM server is read-only (GTM_ACCESS_MODE=read). Propose the change instead, or use the write deployment.";
      }
      if (DELETE_ACTIONS.includes(action)) return "Deleting is disabled (GTM_ALLOW_DELETE is not set).";
      if (PUBLISH_ACTIONS.includes(action)) {
        return "Publishing is disabled (GTM_ALLOW_PUBLISH is not set). Create a version and hand it to a human to publish.";
      }
      return `Action '${action}' is not allowed by this deployment's policy.`;
    },
  };
}
