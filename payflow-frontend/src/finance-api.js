import { request } from './api';

let schemaPromise;
async function schema() {
  if (!schemaPromise) {
    schemaPromise = request('/openapi.json').catch(error => {
      schemaPromise = undefined;
      throw error;
    });
  }
  return schemaPromise;
}

// Match the resource and HTTP method; never guess a mutation URL.
export async function endpoint(resource, method, kind = 'collection') {
  const spec = await schema();
  const noun = resource === 'invoice' ? 'invoices?' : 'payments?';
  const ending = kind === 'collection' ? `${noun}/?$`
    : kind === 'item' ? `${noun}/\\{[^}]+\\}/?$`
    : `${noun}/\\{[^}]+\\}/${kind}/?$`;
  const candidates = Object.keys(spec.paths || {}).filter(path =>
    path.includes('{organization_id}') && new RegExp(`/${ending}`).test(path)
      && spec.paths[path][method.toLowerCase()]
  );
  if (candidates.length !== 1) {
    throw new Error(`Не удалось однозначно определить маршрут ${method} ${resource}/${kind}. Проверь /api/openapi.json.`);
  }
  return { path: candidates[0], operation: spec.paths[candidates[0]][method.toLowerCase()] };
}

export async function financeRequest(resource, token, organizationId, {
  method = 'GET', kind = 'collection', id, invoiceId, body,
} = {}) {
  const route = await endpoint(resource, method, kind);
  const values = { organization_id: organizationId, invoice_id: resource === 'invoice' ? id : invoiceId, payment_id: id };
  const path = route.path.replace(/\{([^}]+)\}/g, (_, key) => {
    if (!values[key]) throw new Error(`Не задан параметр маршрута: ${key}`);
    return encodeURIComponent(values[key]);
  });
  const query = new URLSearchParams();
  if (resource === 'payment' && method === 'GET' && kind === 'collection') {
    if (!invoiceId) throw new Error('Выбери счёт для просмотра платежей.');
    query.set('invoice_id', invoiceId);
  }
  return request(path + (query.size ? `?${query}` : ''), { token, method, body });
}
