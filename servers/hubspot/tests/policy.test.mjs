import test from 'node:test';
import assert from 'node:assert/strict';
import { enabledTools } from '../dist/policy.js';
import { extraTools } from '../dist/extraTools.js';
test('read mode never enables write tools', () => {
  assert.ok(enabledTools({}).has('hubspot-search-objects'));
  assert.equal(enabledTools({ HUBSPOT_WRITE_TOOLS: 'hubspot-batch-create-objects' }).has('hubspot-batch-create-objects'), false);
});
test('write allowlist is exact and rejects unknown names/modes', () => {
  const tools = enabledTools({ HUBSPOT_ACCESS_MODE: 'write', HUBSPOT_WRITE_TOOLS: 'hubspot-batch-update-objects' });
  assert.ok(tools.has('hubspot-batch-update-objects'));
  assert.equal(tools.has('hubspot-batch-create-objects'), false);
  assert.throws(() => enabledTools({ HUBSPOT_ACCESS_MODE: 'root' }));
  assert.throws(() => enabledTools({ HUBSPOT_ACCESS_MODE: 'write', HUBSPOT_WRITE_TOOLS: 'delete-everything' }));
});
for (const name of ['hubspot-get-form', 'hubspot-list-form-submissions', 'hubspot-list-pipelines']) {
  test(`${name} returns MCP error for missing arguments without network`, async () => {
    const tool = extraTools.find(t => t.tool.name === name);
    assert.equal((await tool.handleRequest({})).isError, true);
    assert.equal(tool.tool.annotations.readOnlyHint, true);
  });
}
