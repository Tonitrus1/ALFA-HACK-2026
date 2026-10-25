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
import { Disclosure, ErrorState, Field, PageTitle, Panel } from '../../shared/ui/common';
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
      navigate(`/applications/${application.id}/documents`);
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
        description="Название и ИНН определяет сервер. Деятельность и срок работы сохраняются в заявке."
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
                id="companyName" readOnly
                {...form.register('companyName', { required: 'Укажите название', maxLength: 200 })}
              />
            </Field>
            <Field id="inn" label="ИНН" hint="Идентификационный номер налогоплательщика">
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
            <Field id="businessAgeMonths" label="Срок работы бизнеса, месяцев">
              <input id="businessAgeMonths" inputMode="numeric" {...form.register('businessAgeMonths', { required: 'Укажите срок', pattern: {value: /^\d+$/, message: 'Целое число месяцев'} })} />
            </Field>
            <Field id="preliminaryRevenue" label="Предварительная годовая выручка, ₽" hint="Необязательно. Это ваше заявление, не независимый источник.">
              <input id="preliminaryRevenue" inputMode="decimal" {...form.register('preliminaryRevenue')} />
            </Field>
          </div>
          <div className="form-actions">
            <Link className="button white" to="/workspace">
              В кабинет
            </Link>
            <Button type="primary" htmlType="submit" loading={pending}>
              К документам <ArrowRight size={16} />
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
      navigate(`/applications/${application.id}/review`);
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
        description="Проверьте показатели, перенесённые из документов, и заполните недостающие. Можно ввести все значения вручную."
      />
      <Alert
        className="mb"
        type="info"
        message="Финансовые показатели за полный календарный год"
        description="Все обязательства включают долг и прочие обязательства. Прибыль, EBIT и капитал могут быть отрицательными. Пустое значение отличается от нуля."
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
          <Link className="button white" to={`/applications/${application.id}/documents`}>
            Назад
          </Link>
          <Button type="primary" loading={busy} onClick={() => void next()}>
            Проверить заявку <ArrowRight size={16} />
          </Button>
        </div>
        {!!error && <ErrorState error={error} />}
      </Panel>
    </>
  );
}
export function DocumentsStep() {
  const { application, form, flush } = useDraft(),
    consents = useWatch({ control: form.control, name: 'consents' });
  const navigate=useNavigate(),[error,setError]=useState<unknown>(),[busy,setBusy]=useState(false);
  const next=async()=>{setBusy(true);setError(undefined);try{await flush();navigate(`/applications/${application.id}/business`);}catch(e){setError(e);}finally{setBusy(false);}};
  return (
    <>
      <PageTitle
        title="Документы для заполнения анкеты"
        description="Загрузите отчётность, дождитесь распознавания и сверьте найденные показатели. В анкету попадут только проверенные вами значения."
      />
      <Panel className="mb"><Field id="document-period" label="Отчётный год документов"><select id="document-period" {...form.register('period',{onChange:()=>{for(const k of Object.keys(financeFields) as FinanceKey[])form.setValue(`confirmed.${k}`,false);}})}><option value="2025">2025 год</option><option value="2024">2024 год</option></select></Field><p className="muted">Прикрепите баланс и отчёт о финансовых результатах за один год. Документы необязательны: можно сразу перейти к ручному вводу.</p></Panel>
      <DocumentUploader applicationId={application.id} />
      <OcrReview />

      <Panel className="mt">
        <h2>
          <ShieldCheck size={21} /> Подтверждение сведений
        </h2>
        <Checkbox
          checked={consents}
          onChange={(e) => form.setValue('consents', e.target.checked, { shouldDirty: true })}
        >
          Подтверждаю корректность сведений в заявке.
        </Checkbox>
        <div className="form-actions">
          <Link className="button white" to={`/applications/${application.id}/company`}>
            Назад
          </Link>
          <Button type="primary" disabled={!consents} loading={busy} onClick={()=>void next()}>К финансовым данным <ArrowRight size={16}/></Button>
        </div>
        {!!error && <ErrorState error={error}/>}
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
          <h3>Подтверждение сведений</h3>
          <p>
            {values.consents
              ? '✓ Сведения проверены'
              : 'Сведения не подтверждены — вернитесь к документам'}
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
            Я проверил сведения в заявке и подтверждаю их корректность.
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
          <Disclosure />
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
          Документы не прикреплены. Для первичной заявки они необязательны.
        </p>
      )}
      {documents.error && <ErrorState error={documents.error} />}
    </div>
  );
}
