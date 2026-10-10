import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { AgentClient } from '../dist/client.js';

test('SDK uses HTTP/form/multipart/idempotency and bounded async status transport', async () => {
  const calls = [];
  const server = createServer(async (req, res) => {
    let body = ''; for await (const chunk of req) body += chunk;
    calls.push({ path: req.url, method: req.method, headers: req.headers, body });
    res.setHeader('Content-Type', 'application/json');
    const value = req.url.endsWith('/oauth/token') ? { access_token: 'transport-only-token', token_type: 'Bearer', expires_in: 30, scope: 'project:read' }
      : req.url.endsWith('/workflow') ? { workflow_run_id: 'run', status: 'ACCEPTED' }
      : req.url.endsWith('/workflows/run') ? { workflow_run_id: 'run', status: 'COMPLETED' } : { project_id: 'project', version: 1 };
    res.end(JSON.stringify(value));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const sdk = new AgentClient(`http://127.0.0.1:${server.address().port}`);
    await sdk.authenticate('client', 'one-time-transport-secret');
    await sdk.createProject({ name: 'ERP', facts: { analysis_as_of_date: '2026-10-10' } }, 'create-key');
    await sdk.uploadDocument('project', new Blob(['real binary'], { type: 'text/plain' }), 'input.txt', 1, 'upload-key');
    await sdk.startAnalysis('project', 'snapshot', 'start-key');
    assert.equal((await sdk.waitForCompletion('run', 1000, 10)).status, 'COMPLETED');
    assert.match(calls[0].headers['content-type'], /application\/x-www-form-urlencoded/);
    assert.equal(calls[1].headers.authorization, 'Bearer transport-only-token');
    assert.equal(calls[1].headers['idempotency-key'], 'create-key');
    assert.match(calls[2].headers['content-type'], /multipart\/form-data/);
    assert.match(calls[2].body, /real binary/);
    assert.equal(calls[3].body, '{}');
    assert.equal(calls[4].method, 'GET');
  } finally { await new Promise(resolve => server.close(resolve)); }
});
