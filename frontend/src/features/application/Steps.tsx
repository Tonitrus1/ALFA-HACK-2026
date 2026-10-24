import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useWatch } from 'react-hook-form';
import { App, Alert, Button, Checkbox } from 'antd';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { useDraft } from './DraftProvider';
import { api } from '../../shared/api/client';
import { financeFields, signedFields } from '../../shared/types/domain';
import type { Application, FinanceKey } from '../../shared/types/domain';
import { financeErrors } from '../../shared/lib/validation';
import { money, toKopecks } from '../../shared/lib/money';
import { ErrorState, Field, PageTitle, Panel } from '../../shared/ui/common';
import { DocumentUploader, OcrReview } from '../documents/Documents';
export function CompanyStep() {
  const { form, flush, application } = useDraft(),
    navigate = useNavigate(),
    [error, setError] = useState<unknown>(),
    [pending, setPending] = useState(false);
  const submit = form.handleSubmit(async () => {
    setPending(true);
    try {
      await flush();
      navigate(`/applications/${application.id}/business`);
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  });
  return (
    <>
      <PageTitle
        title="Познакомимся с вашим бизнесом"
        description="Проверьте предзаполненные сведения. Изменения сохраняются автоматически."
      />
      <Panel>
        <form onSubmit={submit}>
          <div className="form-grid">
            <Field
              id="companyName"
              label="Название компании"
              error={form.formState.errors.companyName?.message}
            >
              <input
                id="companyName"
                {...form.register('companyName', { required: 'Укажите название', maxLength: 200 })}
              />
            </Field>
            <Field id="inn" label="ИНН">
              <input id="inn" readOnly {...form.register('inn')} />
            </Field>
            <Field
              id="activity"
              label="Основная деятельность"
              error={form.formState.errors.activity?.message}
            >
              <input
                id="activity"
                {...form.register('activity', { required: 'Укажите деятельность', maxLength: 200 })}
              />
            </Field>
            <Field id="address" label="Адрес" error={form.formState.errors.address?.message}>
              <input
                id="address"
                {...form.register('address', { required: 'Укажите адрес', maxLength: 300 })}
              />
            </Field>
          </div>
          <div className="form-actions">
            <Link className="button white" to="/workspace">
              В кабинет
            </Link>
            <Button type="primary" htmlType="submit" loading={pending}>
              К финансовым данным <ArrowRight size={16} />
            </Button>
          </div>
          {!!error && <ErrorState error={error} />}
        </form>
      </Panel>
    </>
  );
}
export function BusinessStep() {
  const { form, flush, application } = useDraft(),
    navigate = useNavigate(),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const values = useWatch({ control: form.control });
  const next = async () => {
    setError(undefined);
    const errors = financeErrors(form.getValues('finance'));
    for (const [key, message] of Object.entries(errors))
      form.setError(`finance.${key as FinanceKey}`, { message });
    if (Object.keys(errors).length) {
      requestAnimationFrame(() =>
        document.querySelector<HTMLInputElement>('.invalid input')?.focus(),
      );
      return;
    }
    if (!Object.values(form.getValues('confirmed')).every(Boolean)) {
      setError(new Error('Проверьте и подтвердите каждый из восьми показателей'));
      return;
    }
    setBusy(true);
    try {
      await flush();
      navigate(`/applications/${application.id}/documents`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageTitle
        title="Цифры, за которыми стоит ваш бизнес"
        description="Все значения в рублях. Проверьте данные и подтвердите каждый показатель."
      />
      <Alert
        className="mb"
        type="info"
        message="Как заполнить показатели"
        description="Прибыль, EBIT и капитал могут быть отрицательными. Пустое значение отличается от нуля."
      />
      <Panel>
        <div className="form-grid">
          <Field id="period" label="Отчётный период">
            <select
              id="period"
              {...form.register('period', {
                onChange: () => {
                  for (const k of Object.keys(financeFields) as FinanceKey[])
                    form.setValue(`confirmed.${k}`, false);
                },
              })}
            >
              <option value="2025">2025 год</option>
              <option value="2024">2024 год</option>
            </select>
          </Field>
          <Field id="currency" label="Валюта и единицы">
            <input id="currency" readOnly value="Российский рубль · ₽, не тыс. ₽" />
          </Field>
        </div>
        <div className="financial-grid">
          {(Object.entries(financeFields) as [FinanceKey, string][]).map(([key, label]) => (
            <div key={key} className="financial-field">
              <Field
                id={key}
                label={label}
                error={form.formState.errors.finance?.[key]?.message}
                hint={
                  signedFields.includes(key)
                    ? 'Допустимо отрицательное значение'
                    : 'Неотрицательная сумма'
                }
              >
                <div className="money-input">
                  <input
                    id={key}
                    inputMode="decimal"
                    aria-describedby={
                      form.formState.errors.finance?.[key] ? key + '-error' : undefined
                    }
                    {...form.register(`finance.${key}`, {
                      onChange: () => {
                        form.setValue(`confirmed.${key}`, false);
                        form.clearErrors(`finance.${key}`);
                      },
                      validate: (v) => {
                        try {
                          toKopecks(v, signedFields.includes(key));
                          return true;
                        } catch (e) {
                          return (e as Error).message;
                        }
                      },
                    })}
                  />
                  <span>₽</span>
                </div>
              </Field>
              <Checkbox
                aria-label={'Подтвердить: ' + label}
                checked={values.confirmed?.[key] ?? false}
                onChange={(e) =>
                  form.setValue(`confirmed.${key}`, e.target.checked, { shouldDirty: true })
                }
              >
                Значение проверено
              </Checkbox>
            </div>
          ))}
        </div>
        <div className="form-actions">
          <Link className="button white" to={`/applications/${application.id}/company`}>
            Назад
          </Link>
          <Button type="primary" loading={busy} onClick={() => void next()}>
            К документам <ArrowRight size={16} />
          </Button>
        </div>
        {!!error && <ErrorState error={error} />}
      </Panel>
    </>
  );
}
export function DocumentsStep() {
  const { application, form } = useDraft(),
    consents = useWatch({ control: form.control, name: 'consents' });
  return (
    <>
      <PageTitle
        title="Документы и согласия"
        description="Прикрепите документы для проверки сведений. Распознавание поможет сверить данные, но не подтвердит их за вас."
      />
      <DocumentUploader applicationId={application.id} />
      <OcrReview />
      <Panel className="mt">
        <h2>
          <ShieldCheck size={21} /> Ваше согласие
        </h2>
        <Checkbox
          checked={consents}
          onChange={(e) => form.setValue('consents', e.target.checked, { shouldDirty: true })}
        >
          Подтверждаю полномочия представлять компанию и согласен на обработку данных для
          рассмотрения заявки.
        </Checkbox>

        <div className="form-actions">
          <Link className="button white" to={`/applications/${application.id}/business`}>
            Назад
          </Link>
          <Link className="button red" to={`/applications/${application.id}/review`}>
            Проверить заявку <ArrowRight size={16} />
          </Link>
        </div>
      </Panel>
    </>
  );
}
export function ReviewStep() {
  const { message } = App.useApp();
  const query = useQueryClient();
  const { application, form, flush, version } = useDraft(),
    values = useWatch({ control: form.control }),
    navigate = useNavigate(),
    [error, setError] = useState<unknown>(),
    [pending, setPending] = useState(false),
    [verified, setVerified] = useState(false);
  const command = useRef<ReturnType<typeof api.submit> | null>(null);
  const submit = async () => {
    setError(undefined);
    setPending(true);
    try {
      await flush();
      const errors = financeErrors(form.getValues('finance'));
      if (
        Object.keys(errors).length ||
        !Object.values(form.getValues('confirmed')).every(Boolean) ||
        !form.getValues('consents')
      )
        throw new Error(
          'Проверьте финансовые показатели, восемь подтверждений и согласия. Вернитесь на соответствующий шаг.',
        );
      const fresh = await api.application(application.id);
      if (fresh.version !== version())
        throw new Error('Серверная версия изменилась. Вернитесь к форме и сопоставьте данные.');
      const docs = await api.documents(application.id);
      if (!command.current) command.current = api.submit(fresh, docs);
      const result: Application = await command.current.send();
      void message.success('Заявка отправлена на рассмотрение');
      query.setQueryData(['application', result.id], result);
      void query.invalidateQueries({ queryKey: ['applications'] });
      navigate(`/applications/${result.id}/status`);
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  };
  return (
    <>
      <PageTitle
        title="Всё готово к следующему шагу?"
        description="Проверьте заявку перед отправкой. После отправки изменить снимок можно только по запросу уточнений."
      />
      <div className="two-column">
        <Panel>
          <div className="spread">
            <h2>Данные компании</h2>
            <Link to={`/applications/${application.id}/company`}>Изменить</Link>
          </div>
          <dl className="details">
            <dt>Название</dt>
            <dd>{values.companyName}</dd>
            <dt>ИНН</dt>
            <dd>{values.inn}</dd>
            <dt>Деятельность</dt>
            <dd>{values.activity}</dd>
            <dt>Адрес</dt>
            <dd>{values.address}</dd>
          </dl>
          <div className="spread mt">
            <h2>Финансы · {values.period}</h2>
            <Link to={`/applications/${application.id}/business`}>Изменить</Link>
          </div>
          <dl className="details">
            {(Object.entries(financeFields) as [FinanceKey, string][]).map(([k, v]) => (
              <div className="detail-row" key={k}>
                <dt>{v}</dt>
                <dd>
                  {values.finance?.[k] || 'Не указано'} ₽{' '}
                  <span className={values.confirmed?.[k] ? 'confirmed' : 'muted'}>
                    {values.confirmed?.[k] ? '✓' : 'не подтверждено'}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
          <h3>Согласия</h3>
          <p>
            {values.consents
              ? '✓ Получено согласие представителя'
              : 'Не подтверждены — вернитесь к документам'}
          </p>
          <Link to={`/applications/${application.id}/documents`}>Документы и согласия →</Link>
          <ReviewDocuments id={application.id} />
        </Panel>
        <Panel className="review-summary">
          <p className="eyebrow">ВАША ЗАЯВКА</p>
          <strong className="hero-amount">{money(application.need.amount)}</strong>
          <p>
            {application.need.purpose} · {application.need.months} мес.
          </p>
          <hr />
          <Checkbox checked={verified} onChange={(e) => setVerified(e.target.checked)}>
            Я проверил сведения в заявке и подтверждаю их достоверность.
          </Checkbox>
          <Button
            type="primary"
            size="large"
            block
            className="mt"
            disabled={!verified}
            loading={pending}
            onClick={() => void submit()}
          >
            Отправить на рассмотрение <ArrowRight size={16} />
          </Button>
          {!!error && (
            <div className="mt">
              <ErrorState error={error} />
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}

function ReviewDocuments({ id }: { id: string }) {
  const documents = useQuery({ queryKey: ['documents', id], queryFn: () => api.documents(id) });
  return (
    <div className="mt">
      <h3>Прикреплённые документы</h3>
      {documents.data?.length ? (
        documents.data.map((d) => (
          <p className="muted small" key={d.id}>
            {d.name} · версия {d.objectVersion} ·{' '}
            {d.status === 'CLEAN'
              ? 'Будет включён в заявку'
              : d.status === 'FAILED'
                ? 'Не пройден контроль, не включается'
                : 'Ожидает проверки'}
          </p>
        ))
      ) : (
        <p className="muted small">
          Документы не прикреплены. Вы можете добавить их на предыдущем шаге.
        </p>
      )}
      {documents.error && <ErrorState error={documents.error} />}
    </div>
  );
}
