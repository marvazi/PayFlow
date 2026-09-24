export class ApiError extends Error { constructor(message, status) { super(message); this.status = status; } }
let schemaPromise;
export async function routes() {
  if (!schemaPromise) schemaPromise = fetch('/api/openapi.json').then(r => r.ok ? r.json() : null).catch(() => null);
  const schema = await schemaPromise;
  const paths = Object.keys(schema?.paths || {});
  const base = import.meta.env.VITE_ORGANIZATIONS_PATH || paths.find(p => /^\/(organizations?|orgs)\/?$/.test(p) && schema.paths[p].get && schema.paths[p].post) || '/organization';
  const memberPath = paths.find(p => p.startsWith(base.replace(/\/$/, '') + '/') && /\{[^}]+\}\/(members?|memberships)\/?$/.test(p) && schema.paths[p].post);
  return { base, memberPath, memberSegment: import.meta.env.VITE_MEMBERS_SEGMENT || 'members' };
}
export async function request(path, { token, body, method = 'GET', signal } = {}) {
  let response;
  try {
    response = await fetch('/api' + path, { method, signal, headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('Не удалось подключиться к серверу. Проверь, что FastAPI запущен на порту 8000.', 0);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    let message = data?.detail;
    if (Array.isArray(message)) message = message.map(e => `${(e.loc || []).filter(x => x !== 'body').join('.')}: ${e.msg}`).join(' • ');
    if (typeof message !== 'string') message = response.status >= 500 ? 'Сервер недоступен. Проверь запуск FastAPI и повтори попытку.' : `Ошибка запроса (${response.status})`;
    if (response.status === 401 && token) window.dispatchEvent(new Event('payflow:expired'));
    throw new ApiError(message, response.status);
  }
  return data;
}
export async function organizations(token, options = {}) { const { base } = await routes(); return request(base, { token, ...options }); }
export async function organization(token, id) { const { base } = await routes(); return request(`${base.replace(/\/$/, '')}/${encodeURIComponent(id)}`, { token }); }
export async function addMember(token, id, body) {
  const r = await routes();
  const path = r.memberPath ? r.memberPath.replace(/\{[^}]+\}/, encodeURIComponent(id)) : `${r.base.replace(/\/$/, '')}/${encodeURIComponent(id)}/${r.memberSegment}`;
  return request(path, { token, method: 'POST', body });
}

export async function members(token, organizationId, { userId, ...options } = {}) {
  const r = await routes();
  const collection = r.memberPath ? r.memberPath.replace(/\{[^}]+\}/, encodeURIComponent(organizationId)) : `${r.base.replace(/\/$/, '')}/${encodeURIComponent(organizationId)}/${r.memberSegment}`;
  const path = userId ? `${collection.replace(/\/$/, '')}/${encodeURIComponent(userId)}` : collection;
  return request(path, { token, ...options });
}
export async function customers(token, organizationId, { id, ...options } = {}) {
  const { base } = await routes();
  const path = `${base.replace(/\/$/, '')}/${encodeURIComponent(organizationId)}/customers${id ? '/' + encodeURIComponent(id) : ''}`;
  return request(path, { token, ...options });
}
