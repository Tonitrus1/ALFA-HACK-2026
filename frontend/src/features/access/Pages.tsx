import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from 'antd';
import { ArrowRight, Building2, Check } from 'lucide-react';
import { api } from '../../shared/api/client';
import { useSession } from '../../app/session';
import { ErrorState, Field, PageTitle } from '../../shared/ui/common';
export function Login() {
  const { setSession } = useSession(),
    navigate = useNavigate(),
    form = useForm({ defaultValues: { name: 'Александр' } });
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
          <h2>Рады вас видеть</h2>
          <p className="muted">Войдите, чтобы продолжить путь вашего бизнеса.</p>
          <form onSubmit={form.handleSubmit((v) => login.mutate(v))}>
            <Field
              id="name"
              label="Как к вам обращаться?"
              error={form.formState.errors.name?.message}
            >
              <input
                id="name"
                autoComplete="given-name"
                {...form.register('name', {
                  required: 'Введите имя',
                  maxLength: { value: 50, message: 'Не более 50 символов' },
                })}
              />
            </Field>
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
        description="Выберите компанию, от имени которой хотите продолжить."
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
            <p className="muted">ИНН {c.inn}</p>
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
