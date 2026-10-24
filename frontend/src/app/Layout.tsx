import { useEffect, useState } from 'react';
import { NavLink, Navigate, Outlet, Link, useLocation } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Alert, Button } from 'antd';
import {
  ArrowUpRight,
  Bell,
  Building2,
  ChevronDown,
  CircleHelp,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Plus,
  ShieldCheck,
  Sparkles,
  Wallet,
} from 'lucide-react';
import { useSession } from './session';
import { LoadingState } from '../shared/ui/common';
import { startEvents } from '../shared/api/events';
export function Layout() {
  const { session, loading, expired, logout } = useSession(),
    query = useQueryClient(),
    [stale, setStale] = useState(false),
    [lastFresh, setLastFresh] = useState(() => new Date()),
    [mobile, setMobile] = useState(false),
    location = useLocation();
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width:760px)').matches);
  useEffect(() => {
    const media = window.matchMedia('(max-width:760px)');
    const change = () => setNarrow(media.matches);
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);
  const company = session?.companies.find((c) => c.id === session.companyId);
  useEffect(() => {
    if (!session?.companyId || expired || loading) return;
    return startEvents(query, (value) => {
      setStale(value);
      if (!value) setLastFresh(new Date());
    });
  }, [session?.companyId, session?.contextVersion, expired, loading, query]);
  useEffect(() => {
    setMobile(false);
    const timer = setTimeout(() => document.querySelector<HTMLHeadingElement>('h1')?.focus(), 100);
    return () => clearTimeout(timer);
  }, [location.pathname]);
  if (loading) return <LoadingState />;
  if (!session) return <Navigate to="/login" replace />;
  if (!company && location.pathname !== '/companies') return <Navigate to="/companies" replace />;
  return (
    <div className="app-shell">
      <a className="skip" href="#content">
        К содержимому
      </a>
      <aside
        inert={narrow && !mobile}
        aria-hidden={narrow && !mobile}
        className={'sidebar ' + (mobile ? 'open' : '')}
      >
        <Link to="/workspace" className="brand">
          <span className="brand-mark">п</span>поток<span className="brand-dot">.</span>
        </Link>
        <span className="brand-sub">БИЗНЕС ДВИЖЕТСЯ ВПЕРЁД</span>
        <div className="nav-group-label">МОЙ БИЗНЕС</div>
        <nav aria-label="Основная навигация">
          <NavLink to="/workspace">
            <LayoutDashboard size={19} />
            Обзор
          </NavLink>
          <NavLink to="/products">
            <Wallet size={19} />
            Финансирование
          </NavLink>
          <NavLink to="/inbox">
            <MessageSquare size={19} />
            Сообщения
          </NavLink>
          <NavLink to="/assistant">
            <Sparkles size={19} />
            AI-помощник<span className="tiny-tag">AI</span>
          </NavLink>
        </nav>
        <Link className="new-application" to="/needs">
          <Plus size={18} />
          Новая заявка
        </Link>
        <div className="sidebar-bottom">
          <div className="secure-note">
            <ShieldCheck size={23} />
            <div>
              <strong>Всё под контролем</strong>
              <small>
                Данные доступны только
                <br />
                вашей компании
              </small>
            </div>
          </div>
          <Link to="/help/application">
            <CircleHelp size={18} />
            Помощь и поддержка
            <ArrowUpRight size={15} />
          </Link>
          <button onClick={() => void logout()}>
            <LogOut size={17} />
            Выйти
          </button>
          <p>
            Хакатон · 2026
            <br />
            Демонстрационный прототип
          </p>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="mobile-menu icon-button"
            aria-label="Открыть меню"
            aria-expanded={mobile}
            onClick={() => setMobile(!mobile)}
          >
            <Menu />
          </button>
          <Link className="company-switch" to="/companies">
            <span className="company-icon">
              <Building2 size={20} />
            </span>
            <span>
              {company?.name ?? 'Выберите компанию'}
              <small>Бизнес-кабинет</small>
            </span>
            <ChevronDown size={15} />
          </Link>
          <div className="header-right">
            <span className="demo-tag">Учебный прототип</span>
            <Link to="/inbox" className="icon-button" aria-label="Сообщения">
              <Bell size={21} />
            </Link>
            <span className="avatar" title={session.actor}>
              {session.actor.slice(0, 2).toUpperCase()}
            </span>
          </div>
        </header>
        <main id="content" className="content">
          {expired ? (
            <Alert
              type="warning"
              showIcon
              message="Сессия завершена"
              description="Несохранённый ввод остаётся в памяти этой вкладки. После входа вернитесь к заявке."
              action={
                <Link className="button red" to="/login">
                  Войти снова
                </Link>
              }
            />
          ) : (
            <>
              {Date.parse(session.expiresAt) - Date.now() < 300000 && (
                <Alert type="warning" message="Сессия скоро завершится. Сохраните изменения." />
              )}
              {stale && (
                <Alert
                  className="mb"
                  type="warning"
                  showIcon
                  message="Обновление задерживается"
                  description={`Данные на ${lastFresh.toLocaleTimeString('ru-RU')}. Статус заявки не изменён из-за потери связи. Информация обновится после восстановления соединения.`}
                  action={<Button onClick={() => void query.invalidateQueries()}>Обновить</Button>}
                />
              )}
              <Outlet />
            </>
          )}
        </main>
        <footer className="footer">
          <span>Поток · Финансирование вашего дела</span>
          <span>
            <ShieldCheck size={13} /> Демонстрационные данные
          </span>
        </footer>
      </div>
    </div>
  );
}
