const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const esbuild = require('esbuild');
const code = esbuild.transformSync(fs.readFileSync('src/api.js', 'utf8'), { format: 'cjs', define: { 'import.meta.env': '{}' } }).code;
function setup() {
  const calls = []; let reply = { status: 200, data: [] }; let expired = false;
  const context = { module: { exports: {} }, Event, window: { dispatchEvent: () => expired = true }, fetch: async (path, options = {}) => {
    calls.push({ path, ...options });
    if (path === '/api/openapi.json') return { ok: true, json: async () => ({ paths: { '/organization': { get: {}, post: {} }, '/organization/{organization_id}/members': { get: {}, post: {} } } }) };
    return { ok: reply.status < 400, status: reply.status, json: async () => { if (reply.status === 204) throw new SyntaxError(); return reply.data; } };
  }};
  vm.runInNewContext(code, context);
  return { api: context.module.exports, calls, respond: (status, data) => reply = { status, data }, expired: () => expired };
}
test('customer CRUD uses organization scope, partial PATCH and bearer token', async () => {
  const { api, calls, respond } = setup();
  await api.customers('token', 'org'); assert.equal(calls.at(-1).path, '/api/organization/org/customers');
  await api.customers('token', 'org', { id: 'customer' }); assert.equal(calls.at(-1).path, '/api/organization/org/customers/customer');
  await api.customers('token', 'org', { method: 'POST', body: { name: 'Max', email: 'max@example.com' } }); assert.equal(calls.at(-1).method, 'POST');
  await api.customers('token', 'org', { id: 'customer', method: 'PATCH', body: { name: 'New' } });
  assert.equal(calls.at(-1).body, '{"name":"New"}'); assert.equal(calls.at(-1).headers.Authorization, 'Bearer token');
  respond(204); assert.equal(await api.customers('token', 'org', { id: 'customer', method: 'DELETE' }), null);
  assert.equal(calls.at(-1).method, 'DELETE'); assert.equal(calls.at(-1).body, undefined);
});
test('membership mutations address user_id', async () => {
  const { api, calls, respond } = setup();
  await api.members('token', 'org'); assert.equal(calls.at(-1).path, '/api/organization/org/members');
  await api.members('token', 'org', { method: 'POST', body: { user_id: 'user', role: 'viewer' } }); assert.equal(calls.at(-1).method, 'POST');
  await api.members('token', 'org', { userId: 'user', method: 'PATCH', body: { role: 'manager' } });
  assert.equal(calls.at(-1).path, '/api/organization/org/members/user'); assert.equal(calls.at(-1).body, '{"role":"manager"}');
  respond(204); assert.equal(await api.members('token', 'org', { userId: 'user', method: 'DELETE' }), null);
});
test('403, 404, 409, 422 stay actionable and 401 expires session', async () => {
  const { api, respond, expired } = setup();
  for (const status of [403, 404, 409]) { respond(status, { detail: 'Ошибка операции' }); await assert.rejects(() => api.customers('token', 'org'), e => e.status === status && e.message === 'Ошибка операции'); }
  respond(422, { detail: [{ loc: ['body', 'email'], msg: 'Invalid email' }] }); await assert.rejects(() => api.customers('token', 'org'), /email: Invalid email/);
  assert.equal(expired(), false);
  respond(401, { detail: 'Сессия истекла' }); await assert.rejects(() => api.members('token', 'org'), /Сессия истекла/); assert.equal(expired(), true);
});
