import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Alert, Button } from 'antd';
import { ArrowRight, Building2, Check, ShieldCheck } from 'lucide-react';
import { api } from '../../shared/api/client';
import { useSession } from '../../app/session';
import { Disclosure, ErrorState, Field, PageTitle } from '../../shared/ui/common';
export function Login() {
  const { setSession } = useSession(),
    navigate = useNavigate(),
    form = useForm({ defaultValues: { name: '' } }),
    accounts = useQuery({ queryKey: ['demo-accounts'], queryFn: api.accounts });
  const login = useMutation({
    mutationFn: ({ name }: { name: string }) => api.login(name),
    onSuccess: (s) => {
      setSession(s);
      navigate('/companies');
    },
  });
  return (
    <div className="login-page">
      <section className="login-story">
        <Link to="/login" className="brand light">
          <span className="brand-mark">п</span>поток.
        </Link>
        <div>
          <p className="eyebrow">БОЛЬШЕ ВОЗМОЖНОСТЕЙ ДЛЯ ВАШЕГО ДЕЛА</p>
          <h1>
            Ваш бизнес.
            <br />
            Следующий
            <br />
            <em>большой шаг.</em>
          </h1>
          <p>
            От идеи до финансирования —<br />в одном понятном кабинете.
          </p>
        </div>
        <span className="login-foot">Создано для движения вперёд ↗</span>
        <div className="orbit orbit-one" />
        <div className="orbit orbit-two" />
      </section>
      <section className="login-form">
        <div>
          <span className="demo-tag">Демонстрационный вход</span>
          <h2>Рады вас видеть</h2>
          <p className="muted">Войдите, чтобы продолжить путь вашего бизнеса.</p>
          <form onSubmit={form.handleSubmit((v) => login.mutate(v))}>
            <Field
              id="name"
              label="Демонстрационный представитель"
              error={form.formState.errors.name?.message}
            >
              <select id="name" {...form.register('name', { required: 'Выберите представителя' })}>
                <option value="">Выберите аккаунт</option>
                {accounts.data?.map(a => <option key={a.accountId} value={a.accountId}>{a.displayName}</option>)}
              </select>
              {accounts.error && <ErrorState error={accounts.error} />}
            </Field>
            <Alert
              type="info"
              message="Только искусственные данные"
              description="Пароль, телефон и банковские реквизиты не нужны. Заявки и результаты сохраняются на сервере."
            />
            <Button
              type="primary"
              size="large"
              htmlType="submit"
              loading={login.isPending}
              block
              className="mt"
            >
              Войти в кабинет <ArrowRight size={17} />
            </Button>
            {login.error && <ErrorState error={login.error} />}
          </form>
          <p className="login-safety">
            <ShieldCheck size={17} /> Без реальных банковских операций
          </p>
          <Disclosure />
        </div>
      </section>
    </div>
  );
}
export function Companies() {
  const { session, changeCompany } = useSession(),
    navigate = useNavigate(),
    [busy, setBusy] = useState<string>(),
    [error, setError] = useState<unknown>();
  const choose = async (id: string) => {
    setBusy(id);
    setError(undefined);
    try {
      await changeCompany(id);
      navigate('/workspace');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(undefined);
    }
  };
  return (
    <>
      <PageTitle
        eyebrow="ВАШ БИЗНЕС"
        title="От имени какой компании работаем?"
        description="Доступные организации определяются вашей серверной сессией."
      />
      <div className="company-grid">
        {session?.companies.map((c) => (
          <button
            key={c.id}
            className="company-card"
            disabled={!!busy}
            onClick={() => void choose(c.id)}
          >
            <span className="large-icon">
              <Building2 />
            </span>
            <h2>{c.name}</h2>
            <p className="muted">ИНН {c.inn} · Искусственные данные</p>
            <p>{c.industry}</p>
            <span className="company-choice">
              {busy === c.id ? (
                'Переключаем…'
              ) : session.companyId === c.id ? (
                <>
                  <Check size={16} />
                  Активная компания
                </>
              ) : (
                <>
                  Перейти в кабинет <ArrowRight size={17} />
                </>
              )}
            </span>
          </button>
        ))}
      </div>
      {!!error && <ErrorState error={error} />}
    </>
  );
}
