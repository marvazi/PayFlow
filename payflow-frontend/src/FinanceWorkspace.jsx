import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Plus, RefreshCw, X, Copy, Check, FileText, CreditCard } from 'lucide-react';
import { members, customers } from './api';
import { financeRequest } from './finance-api';

const labels = { draft: 'Черновик', issued: 'Выставлен', paid: 'Оплачен', cancelled: 'Отменён', pending: 'В обработке', succeeded: 'Успешно', failed: 'Отклонён' };
const roles = { owner: 'Владелец', manager: 'Менеджер', viewer: 'Наблюдатель' };
const date = value => value ? new Date(value).toLocaleString('ru-RU') : '—';
const money = value => new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' }).format(value / 100);
const short = value => value ? `${value.slice(0, 8)}…` : '—';
function Badge({ status }) { return <span className={`pf-status pf-${status}`}>{labels[status] || status}</span>; }
function Id({ value }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef();
  useEffect(() => () => clearTimeout(timer.current), []);
  if (!value) return <span className="muted">Ещё не получен</span>;
  return <button className="pf-id" title="Скопировать идентификатор" onClick={async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); clearTimeout(timer.current); timer.current = setTimeout(() => setCopied(false), 1500); }
    catch { setCopied(false); }
  }}>{copied ? <Check size={13}/> : <Copy size={13}/>}<span>{value}</span></button>;
}
function Dialog({ title, busy, close, children }) {
  const ref = useRef();
  useEffect(() => {
    const before = document.activeElement;
    ref.current?.focus();
    return () => before?.isConnected && before.focus();
  }, []);
  function keyboard(e) {
    if (e.key === 'Escape' && !busy) close();
    if (e.key !== 'Tab') return;
    const nodes = [...ref.current.querySelectorAll('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled)')].filter(n => !n.closest('fieldset:disabled'));
    const first = nodes[0], last = nodes.at(-1);
    if (!first) { e.preventDefault(); return; }
    if (e.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || document.activeElement === ref.current)) { e.preventDefault(); first.focus(); }
  }
  return <div className="overlay" onClick={e => { if (!busy && e.target === e.currentTarget) close(); }}>
    <section className="modal pf-modal" ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} onKeyDown={keyboard}>
      <button type="button" className="icon close" disabled={busy} onClick={close} aria-label="Закрыть"><X/></button>
      <h2>{title}</h2>{children}
    </section>
  </div>;
}
function parseAmount(value) {
  const normalized = value.trim().replace(',', '.');
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) throw new Error('Введи сумму в рублях, максимум два знака после запятой.');
  const [whole, fraction = ''] = normalized.split('.');
  const minor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  // JSON numbers beyond this limit cannot be represented exactly in JS.
  if (minor <= 0n || minor > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('Сумма должна быть положительной и не превышать 90 071 992 547 409,91 ₽.');
  return Number(minor);
}
function amountInput(minor) {
  if (!Number.isSafeInteger(minor)) return '';
  return `${Math.floor(minor / 100)}.${String(minor % 100).padStart(2, '0')}`;
}

export default function FinanceWorkspace({ token, organization, user, onBack }) {
  const [invoices, setInvoices] = useState([]), [clients, setClients] = useState([]), [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [query, setQuery] = useState(''), [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState(null), [payments, setPayments] = useState([]);
  const [detailError, setDetailError] = useState(''), [opening, setOpening] = useState(false);
  const [dialog, setDialog] = useState(null), [formError, setFormError] = useState(''), [busy, setBusy] = useState(false);
  const run = useRef(0), detailRun = useRef(0), lock = useRef(false);
  const ownRole = team.find(m => m.user_id === user?.id)?.role;
  const canWrite = ['owner', 'manager'].includes(ownRole);
  const call = (resource, options) => financeRequest(resource, token, organization.id, options);
  const customerName = id => clients.find(c => c.id === id)?.name || short(id);
  function updateInvoice(item) { setInvoices(prev => prev.some(i => i.id === item.id) ? prev.map(i => i.id === item.id ? item : i) : [...prev, item]); }

  async function reload() {
    const generation = ++run.current;
    ++detailRun.current;
    setLoading(true); setError(''); setSelected(null); setPayments([]);
    try {
      const [newTeam, newClients, list] = await Promise.all([
        members(token, organization.id), customers(token, organization.id), call('invoice'),
      ]);
      if (generation !== run.current) return;
      if (![newTeam, newClients, list].every(Array.isArray)) throw new Error('Сервер вернул неожиданный формат списка.');
      setTeam(newTeam); setClients(newClients); setInvoices(list);
    } catch (e) { if (generation === run.current) { setError(e.message); setTeam([]); } }
    finally { if (generation === run.current) setLoading(false); }
  }
  useEffect(() => { reload(); return () => { ++run.current; ++detailRun.current; }; }, [token, organization.id]);

  async function showInvoice(id) {
    const generation = ++detailRun.current;
    setOpening(true); setDetailError(''); setPayments([]);
    try {
      const invoice = await call('invoice', { kind: 'item', id });
      if (generation !== detailRun.current) return;
      setSelected(invoice); updateInvoice(invoice);
      const list = await call('payment', { invoiceId: id });
      if (generation !== detailRun.current) return;
      if (!Array.isArray(list)) throw new Error('Сервер вернул неожиданный формат платежей.');
      setPayments(list);
    } catch (e) { if (generation === detailRun.current) setDetailError(e.message); }
    finally { if (generation === detailRun.current) setOpening(false); }
  }
  function open(type, item) { setFormError(''); setDialog({ type, item }); }
  async function submit(event) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true; setBusy(true); setFormError(''); setNotice('');
    const { type, item } = dialog;
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (!canWrite) throw new Error('Изменения доступны только владельцу и менеджеру.');
      if (type === 'create' || type === 'edit') {
        const description = fields.description.trim();
        if (!description) throw new Error('Укажи описание счёта.');
        const amount_minor = parseAmount(fields.amount);
        let body = { description, amount_minor };
        if (type === 'create') body = { ...body, customer_id: fields.customer_id, currency: 'RUB' };
        else body = Object.fromEntries(Object.entries(body).filter(([k, v]) => item[k] !== v));
        if (!Object.keys(body).length) { setDialog(null); setNotice('Данные не изменились.'); return; }
        const saved = await call('invoice', { method: type === 'create' ? 'POST' : 'PATCH', kind: type === 'create' ? 'collection' : 'item', id: item?.id, body });
        updateInvoice(saved); setDialog(null); setNotice(type === 'create' ? 'Черновик счёта создан.' : 'Счёт обновлён.');
        await showInvoice(saved.id);
      } else if (type === 'issue' || type === 'cancel') {
        const saved = await call('invoice', { method: 'POST', kind: type, id: item.id });
        updateInvoice(saved); setSelected(saved); setDialog(null);
        setNotice(type === 'issue' ? 'Счёт выставлен.' : 'Счёт отменён.');
        await showInvoice(saved.id);
      } else {
        const payment = await call('payment', type === 'pay'
          ? { method: 'POST', body: { invoice_id: item.id } }
          : { method: 'POST', kind: 'retry', id: item.id });
        setDialog(null); setNotice(type === 'pay' ? 'Платёж создан. Ожидаем результат обработки.' : 'Повторная отправка выполнена.');
        await showInvoice(payment.invoice_id);
      }
    } catch (e) {
      setFormError(e.message);
      // The server may have committed a payment before a PSP error.
      // Always reread before enabling another create attempt.
      if (type === 'pay' || type === 'retry') {
        const invoiceId = type === 'pay' ? item.id : item.invoice_id;
        setDialog(null);
        await showInvoice(invoiceId);
        setNotice(`Запрос не завершён: ${e.message}. Список платежей обновлён; если платёж сохранён, используй «Повторить отправку».`);
      }
    } finally { setBusy(false); lock.current = false; }
  }
  const pending = payments.some(p => p.status === 'pending');
  const visible = invoices.filter(i => (filter === 'all' || i.status === filter) && `${i.description} ${i.id} ${customerName(i.customer_id)}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const titles = { create: 'Новый счёт', edit: 'Редактировать черновик', issue: 'Выставить счёт?', cancel: 'Отменить счёт?', pay: 'Создать платёж?', retry: 'Повторить отправку в PSP?' };
  const type = dialog?.type, item = dialog?.item;
  return <div className="pf-finance">
    <button className="back" onClick={onBack}><ArrowLeft size={16}/> Все организации</button>
    <div className="heading"><div><div className="eyebrow">ФИНАНСЫ ОРГАНИЗАЦИИ</div><h1>{organization.name}</h1><p className="muted">Счета, платежи и их обработка · {roles[ownRole] || 'Проверяем доступ…'}</p></div><button className="secondary" disabled={loading || busy || opening} onClick={reload}><RefreshCw size={16}/> Обновить</button></div>
    {notice && <div className="pf-notice" role="status">{notice}</div>}
    {error && <div className="alert" role="alert">{error}</div>}
    {loading ? <div className="empty" role="status">Загружаем счета…</div> : error ? <div className="empty">Не удалось загрузить раздел. Нажми «Обновить», чтобы повторить.</div> : <>
      <div className="pf-stats">{['draft', 'issued', 'paid'].map(status => <div key={status}><span>{labels[status]}</span><strong>{invoices.filter(i => i.status === status).length}</strong><small>счетов</small></div>)}</div>
      {detailError && <div className="alert" role="alert">{detailError} <button className="secondary compact" disabled={opening} onClick={() => selected ? showInvoice(selected.id) : reload()}>Повторить загрузку</button></div>}
      {selected ? <>
        <button className="back" disabled={busy} onClick={() => { ++detailRun.current; setSelected(null); setDetailError(''); setOpening(false); }}><ArrowLeft size={16}/> Все счета</button>
        <section className="panel pf-invoice">
          <div className="pf-detail-heading"><div><Badge status={selected.status}/><h2>{selected.description}</h2><p className="muted">{customerName(selected.customer_id)} · {date(selected.created_at)}</p></div><strong className="pf-amount">{money(selected.amount_minor)}</strong></div>
          <dl><dt>ID счёта</dt><dd><Id value={selected.id}/></dd><dt>ID клиента</dt><dd><Id value={selected.customer_id}/></dd></dl>
          {canWrite && <div className="row-actions">
            {selected.status === 'draft' && <><button className="secondary" disabled={busy || opening} onClick={() => open('edit', selected)}>Редактировать</button><button className="primary" disabled={busy || opening} onClick={() => open('issue', selected)}>Выставить счёт</button></>}
            {selected.status === 'issued' && <button className="primary" disabled={busy || opening || pending || !!detailError} onClick={() => open('pay', selected)}><CreditCard size={16}/> Создать платёж</button>}
            {['draft', 'issued'].includes(selected.status) && <button className="danger" disabled={busy || opening || pending || !!detailError} onClick={() => open('cancel', selected)}>Отменить счёт</button>}
          </div>}
          {pending && <p className="muted small">Есть незавершённый платёж. Новый платёж и отмена счёта пока недоступны.</p>}
        </section>
        <div className="list-toolbar"><h2>Платежи по счёту</h2><button className="secondary compact" disabled={opening || busy} onClick={() => showInvoice(selected.id)}><RefreshCw size={15}/> Проверить статус</button></div>
        {opening ? <div className="empty" role="status">Загружаем платежи…</div> : detailError ? null : payments.length ? <div className="pf-payment-list">{payments.map(p => <section className="panel pf-payment" key={p.id}>
          <div className="pf-detail-heading"><Badge status={p.status}/><strong>{money(p.amount_minor)}</strong></div>
          <dl><dt>Платёж PayFlow</dt><dd><Id value={p.id}/></dd><dt>Транзакция PSP</dt><dd><Id value={p.provider_transaction_id}/></dd><dt>Создан</dt><dd>{date(p.created_at)}</dd><dt>Обновлён</dt><dd>{date(p.updated_at)}</dd></dl>
          {p.status === 'pending' && !p.provider_transaction_id && <><p className="muted small">Связь с PSP ещё не сохранена. Повторная отправка использует тот же платёж.</p>{canWrite && <button className="secondary" disabled={busy} onClick={() => open('retry', p)}><RefreshCw size={16}/> Повторить отправку</button>}</>}
        </section>)}</div> : <div className="empty"><CreditCard size={30}/><h2>Платежей пока нет</h2><p>Платёж можно создать после выставления счёта.</p></div>}
      </> : <>
        <div className="list-toolbar"><h2>Счета <span>{invoices.length}</span></h2><input className="pf-search" aria-label="Поиск счетов" placeholder="Клиент, описание или ID" value={query} onChange={e => setQuery(e.target.value)}/><select aria-label="Статус счёта" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Все статусы</option>{['draft', 'issued', 'paid', 'cancelled'].map(s => <option key={s} value={s}>{labels[s]}</option>)}</select>{canWrite && <button className="primary" disabled={!clients.length || busy || opening} onClick={() => open('create')}><Plus size={16}/> Новый счёт</button>}</div>
        {!clients.length && canWrite && <p className="muted">Сначала добавь клиента в разделе «Клиенты и команда».</p>}
        {!canWrite && <p className="muted small">Твоя роль позволяет просматривать счета и платежи.</p>}
        {opening && <p role="status">Открываем счёт…</p>}
        {visible.length ? <div className="table-scroll"><table><thead><tr><th>Счёт / клиент</th><th>Сумма</th><th>Статус</th><th>Создан</th><th/></tr></thead><tbody>{visible.map(i => <tr key={i.id}><td><button className="text-button" disabled={opening} onClick={() => showInvoice(i.id)}>{i.description}</button><small>{customerName(i.customer_id)}</small></td><td className="pf-nowrap">{money(i.amount_minor)}</td><td><Badge status={i.status}/></td><td>{date(i.created_at)}</td><td><button className="secondary compact" disabled={opening} onClick={() => showInvoice(i.id)}>Открыть</button></td></tr>)}</tbody></table></div> : <div className="empty"><FileText size={30}/><h2>{query || filter !== 'all' ? 'Счета не найдены' : 'Пока нет счетов'}</h2><p>Создай черновик, укажи клиента и сумму, затем выставь счёт.</p></div>}
      </>}
    </>}
    {dialog && <Dialog title={titles[type]} busy={busy} close={() => setDialog(null)}><form onSubmit={submit}><fieldset disabled={busy}>
      {formError && <div className="alert" role="alert">{formError}</div>}
      {['create', 'edit'].includes(type) ? <>
        {type === 'create' && <label>Клиент<select name="customer_id" required defaultValue=""><option value="" disabled>Выбери клиента</option>{clients.map(c => <option key={c.id} value={c.id}>{c.name} — {c.email}</option>)}</select></label>}
        <label>Описание<textarea name="description" required maxLength={500} rows={3} defaultValue={item?.description || ''}/></label>
        <label>Сумма, ₽<input name="amount" inputMode="decimal" required placeholder="Например, 970,00" defaultValue={item ? amountInput(item.amount_minor) : ''}/></label><p className="muted small">Валюта — RUB. Сумма передаётся в копейках.</p>
      </> : <p>{type === 'issue' ? 'После выставления редактировать счёт будет нельзя.' : type === 'cancel' ? 'Отменённый счёт нельзя оплатить. Подтверди отмену.' : type === 'pay' ? `Создать платёж на ${money(item.amount_minor)} и отправить его в PSP? Это ещё не подтверждение оплаты.` : 'Повторно отправить существующий платёж в PSP и сохранить идентификатор транзакции?'}</p>}
      <div className="dialog-actions"><button type="button" className="secondary" onClick={() => setDialog(null)}>Назад</button><button className={type === 'cancel' ? 'danger solid' : 'primary'}>{busy ? 'Выполняем…' : ['create', 'edit'].includes(type) ? 'Сохранить' : 'Подтвердить'}</button></div>
    </fieldset></form></Dialog>}
  </div>;
}
