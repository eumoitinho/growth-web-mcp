import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { serveStateless } from '../dist/http.js';
test('real HTTP/MCP lifecycle, malformed JSON and tool errors', async () => {
  process.env.PORT = '0';
  const host = serveStateless('contract-test', () => {
    const s = new Server({ name: 'fixture', version: '1' }, { capabilities: { tools: {} } });
    s.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: [{ name: 'probe', inputSchema: { type: 'object' } }] }));
    s.setRequestHandler(CallToolRequestSchema, async () => ({ isError: true, content: [{ type: 'text', text: 'upstream unavailable' }] }));
    return s;
  });
  await once(host, 'listening');
  const base = `http://127.0.0.1:${host.address().port}`;
  const client = new Client({ name: 'test', version: '1' });
  try {
    assert.equal((await fetch(base + '/healthz')).status, 200);
    assert.equal((await fetch(base + '/missing')).status, 404);
    assert.equal((await fetch(base + '/mcp')).status, 405);
    assert.equal((await fetch(base + '/mcp', { method: 'POST', body: '{' })).status, 400);
    await client.connect(new StreamableHTTPClientTransport(new URL(base + '/mcp')));
    assert.deepEqual((await client.listTools()).tools.map(t => t.name), ['probe']);
    assert.equal((await client.callTool({ name: 'probe', arguments: {} })).isError, true);
  } finally {
    await client.close();
    host.closeAllConnections();
    await new Promise(resolve => host.close(resolve));
  }
});
