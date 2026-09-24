import React, { useEffect, useRef, useState } from 'react';
import { Plus, RefreshCw, ArrowLeft, X, Search, Users, UserRound } from 'lucide-react';
import { members, customers } from './api';
const roles = { owner: 'Владелец', manager: 'Менеджер', viewer: 'Наблюдатель' };
const date = value => new Date(value).toLocaleString('ru-RU');
const uuidPattern = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';
function Dialog({ title, busy, close, children }) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    ref.current?.focus();
    return () => previous?.focus();
  }, []);
  function keyboard(e) {
    if (e.key === 'Escape' && !busy) close();
    if (e.key !== 'Tab') return;
    const els = [...ref.current.querySelectorAll('button:not(:disabled),input,select,[tabindex="0"]')];
    const first = els[0], last = els.at(-1);
    if (!first) { e.preventDefault(); return; }
    if (e.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || document.activeElement === ref.current)) { e.preventDefault(); first.focus(); }
  }
  return <div className="overlay" onClick={e => { if (e.target === e.currentTarget && !busy) close(); }}><section ref={ref} tabIndex={-1} onKeyDown={keyboard} className="modal" role="dialog" aria-modal="true" aria-label={title}><button className="icon close" disabled={busy} onClick={close} aria-label="Закрыть"><X/></button><h2>{title}</h2>{children}</section></div>;
}
export default function OrganizationWorkspace({ token, organization, user, onBack }) {
  const [team, setTeam] = useState([]), [list, setList] = useState([]), [tab, setTab] = useState('customers');
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [query, setQuery] = useState(''), [dialog, setDialog] = useState(null), [busy, setBusy] = useState(false), [formError, setFormError] = useState('');
  const [current, setCurrent] = useState(null), [opening, setOpening] = useState(false);
  const generation = useRef(0);
  const ownRole = team.find(m => m.user_id === user?.id)?.role;
  const canWrite = ['owner', 'manager'].includes(ownRole);
  const isOwner = ownRole === 'owner';
  async function reload() {
    const run = ++generation.current;
    setLoading(true); setError(''); setCurrent(null);
    try {
      const [newTeam, newList] = await Promise.all([members(token, organization.id), customers(token, organization.id)]);
      if (run !== generation.current) return;
      setTeam(newTeam); setList(newList);
    } catch (e) { if (run === generation.current) { setError(e.message); setTeam([]); setList([]); } }
    finally { if (run === generation.current) setLoading(false); }
  }
  useEffect(() => { reload(); return () => { generation.current++; }; }, [token, organization.id]);
  function open(type, item) { setFormError(''); setDialog({ type, item }); }
  async function showCustomer(id) {
    setOpening(true); setError('');
    try { setCurrent(await customers(token, organization.id, { id })); }
    catch (e) { setError(e.message); }
    finally { setOpening(false); }
  }
  async function submit(e) {
    e.preventDefault(); if (busy) return;
    const { type, item } = dialog;
    const form = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true); setFormError('');
    try {
      if (type === 'createCustomer' || type === 'editCustomer') {
        const normalized = { name: form.name.trim(), email: form.email.trim().toLowerCase() };
        if (!normalized.name) throw new Error('Укажи имя клиента.');
        const body = type === 'editCustomer' ? Object.fromEntries(Object.entries(normalized).filter(([key, value]) => value !== item[key])) : normalized;
        if (!Object.keys(body).length) { setDialog(null); setNotice('Данные не изменились.'); return; }
        const saved = await customers(token, organization.id, { id: item?.id, method: item ? 'PATCH' : 'POST', body });
        setList(prev => item ? prev.map(c => c.id === saved.id ? saved : c) : [...prev, saved]);
        if (current?.id === saved.id) setCurrent(saved);
        setNotice(item ? 'Данные клиента обновлены.' : 'Клиент создан.');
      } else if (type === 'deleteCustomer') {
        await customers(token, organization.id, { id: item.id, method: 'DELETE' });
        setList(prev => prev.filter(c => c.id !== item.id));
        if (current?.id === item.id) setCurrent(null);
        setNotice('Клиент удалён.');
      } else if (type === 'addMember') {
        const saved = await members(token, organization.id, { method: 'POST', body: form });
        setTeam(prev => [...prev, saved]); setNotice('Участник добавлен.');
      } else if (type === 'editMember') {
        const saved = await members(token, organization.id, { userId: item.user_id, method: 'PATCH', body: { role: form.role } });
        setTeam(prev => prev.map(m => m.id === saved.id ? saved : m)); setNotice('Роль обновлена.');
      } else {
        await members(token, organization.id, { userId: item.user_id, method: 'DELETE' });
        setTeam(prev => prev.filter(m => m.id !== item.id)); setNotice('Участник удалён из организации.');
      }
      setDialog(null);
    } catch (e) { setFormError(e.message); }
    finally { setBusy(false); }
  }
  const visible = list.filter(c => `${c.name} ${c.email}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const type = dialog?.type, item = dialog?.item;
  const titles = { createCustomer: 'Новый клиент', editCustomer: 'Редактировать клиента', deleteCustomer: 'Удалить клиента?', addMember: 'Добавить участника', editMember: 'Изменить роль', deleteMember: 'Удалить участника?' };
  const deleting = type?.startsWith('delete');
  return <>
    <button className="back" onClick={onBack}><ArrowLeft size={16}/> Все организации</button>
    <div className="heading"><div><div className="eyebrow">ОРГАНИЗАЦИЯ</div><h1>{organization.name}</h1><p className="muted">Создана {date(organization.created_at)} · {roles[ownRole] || 'Проверяем доступ…'}</p></div><button className="secondary" disabled={loading || busy || opening} onClick={reload}><RefreshCw size={16}/> Обновить</button></div>
    <p className="org-id">ID организации: {organization.id}</p>
    {notice && <div className="success" role="status">{notice}</div>}
    {error && <div className="alert" role="alert">{error}</div>}
    <div className="tabs section-tabs"><button className={tab === 'customers' ? 'active' : ''} onClick={() => { setTab('customers'); setCurrent(null); }}><UserRound size={16}/> Клиенты <span>{list.length}</span></button><button className={tab === 'team' ? 'active' : ''} onClick={() => { setTab('team'); setCurrent(null); }}><Users size={16}/> Команда <span>{team.length}</span></button></div>
    {loading ? <div className="empty" role="status">Загружаем данные организации…</div> : error ? <div className="empty">Не удалось загрузить данные. Нажми «Обновить», чтобы повторить запрос.</div> : tab === 'customers' ? <>
      {current ? <section className="panel customer-detail"><button className="back" onClick={() => setCurrent(null)}><ArrowLeft size={16}/> Все клиенты</button><h2>{current.name}</h2><dl><dt>Email</dt><dd>{current.email}</dd><dt>ID клиента</dt><dd>{current.id}</dd><dt>Организация</dt><dd>{current.organization_id}</dd><dt>Создан</dt><dd>{date(current.created_at)}</dd></dl>{canWrite && <div className="row-actions"><button className="secondary" onClick={() => open('editCustomer', current)}>Редактировать</button><button className="danger" onClick={() => open('deleteCustomer', current)}>Удалить</button></div>}</section> : <>
      <div className="list-toolbar"><h2>Клиенты организации</h2><div className="search"><Search size={17}/><input aria-label="Поиск клиентов" placeholder="Имя или email" value={query} onChange={e => setQuery(e.target.value)}/></div>{canWrite && <button className="primary" onClick={() => open('createCustomer')}><Plus size={16}/> Новый клиент</button>}</div>
      {!canWrite && <p className="muted small">Твоя роль позволяет просматривать клиентов. Изменения доступны менеджеру и владельцу.</p>}
      {!visible.length ? <div className="empty"><UserRound size={30}/><h2>{query ? 'Клиенты не найдены' : 'Пока нет клиентов'}</h2><p>{query ? 'Измени поисковый запрос.' : 'Здесь будут покупатели вашей организации.'}</p></div> : <div className="table-scroll"><table><thead><tr><th>Клиент</th><th>Создан</th><th>Действия</th></tr></thead><tbody>{visible.map(c => <tr key={c.id}><td><button className="text-button" disabled={opening} onClick={() => showCustomer(c.id)}>{c.name}</button><small>{c.email}</small></td><td>{date(c.created_at)}</td><td><div className="row-actions"><button className="secondary compact" disabled={opening} onClick={() => showCustomer(c.id)}>Открыть</button>{canWrite && <><button className="secondary compact" onClick={() => open('editCustomer', c)}>Изменить</button><button className="danger compact" onClick={() => open('deleteCustomer', c)}>Удалить</button></>}</div></td></tr>)}</tbody></table></div>}
      </>}
    </> : <>
      <div className="list-toolbar"><h2>Участники организации</h2>{isOwner && <button className="primary" onClick={() => open('addMember')}><Plus size={16}/> Добавить участника</button>}</div>
      <p className="muted small">Участники показаны по ID пользователя. Управлять составом команды может владелец.</p>
      <div className="table-scroll"><table><thead><tr><th>Пользователь</th><th>Роль</th><th>Добавлен</th><th>Действия</th></tr></thead><tbody>{team.map(m => <tr key={m.id}><td><span className="mono">{m.user_id}</span>{m.user_id === user?.id && <small>Это ты · {user.name}</small>}</td><td><span className={`role-badge ${m.role}`}>{roles[m.role] || m.role}</span></td><td>{date(m.created_at)}</td><td>{isOwner && m.role !== 'owner' ? <div className="row-actions"><button className="secondary compact" onClick={() => open('editMember', m)}>Роль</button><button className="danger compact" onClick={() => open('deleteMember', m)}>Удалить</button></div> : <span className="muted">—</span>}</td></tr>)}</tbody></table></div>
    </>}
    {dialog && <Dialog title={titles[type]} busy={busy} close={() => setDialog(null)}><form onSubmit={submit}><fieldset disabled={busy}>
      {formError && <div className="alert" role="alert">{formError}</div>}
      {(type === 'createCustomer' || type === 'editCustomer') && <><label>Имя клиента<input name="name" required maxLength={255} pattern=".*\S.*" defaultValue={item?.name || ''}/></label><label>Email<input name="email" type="email" required defaultValue={item?.email || ''}/></label></>}
      {type === 'addMember' && <label>ID пользователя<input name="user_id" required pattern={uuidPattern} placeholder="UUID из профиля пользователя"/></label>}
      {type === 'editMember' && <p className="mono">{item.user_id}</p>}
      {(type === 'addMember' || type === 'editMember') && <label>Роль<select name="role" defaultValue={item?.role || 'viewer'}><option value="viewer">Наблюдатель</option><option value="manager">Менеджер</option></select></label>}
      {type === 'deleteCustomer' && <p>Клиент <strong>{item.name}</strong> ({item.email}) будет удалён. Это действие нельзя отменить.</p>}
      {type === 'deleteMember' && <p>Пользователь <span className="mono">{item.user_id}</span> потеряет доступ к этой организации. Его аккаунт сохранится.</p>}
      <div className="dialog-actions"><button type="button" className="secondary" onClick={() => setDialog(null)}>Отмена</button><button className={deleting ? 'danger solid' : 'primary'}>{busy ? 'Сохраняем…' : deleting ? 'Удалить' : 'Сохранить'}</button></div>
    </fieldset></form></Dialog>}
  </>;
}
