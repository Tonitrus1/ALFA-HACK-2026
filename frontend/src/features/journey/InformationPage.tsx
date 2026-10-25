import { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Alert, Button, Modal } from 'antd';
import { ApiError, context } from '../../shared/api/http';
import { api } from '../../shared/api/client';
import type { Finance, FinanceKey, InformationRequest } from '../../shared/types/domain';
import { financeFields } from '../../shared/types/domain';
import { userMessage } from '../../shared/lib/userMessage';
import { RetainedResource } from '../../shared/lib/retainedResource';
import type { SaveState } from '../../shared/lib/autosave';
import { DocumentUploader } from '../documents/Documents';
import { ErrorState, Field, LoadingState, PageTitle, Panel } from '../../shared/ui/common';
type ResponseForm = { finance: Finance; confirmed: boolean };
const retained = new Map<string, RetainedResource<ResponseForm, InformationRequest>>();
export function InformationPage() {
  const { id = '', requestId = '' } = useParams(),
    r = useQuery({
      queryKey: ['information', id, requestId],
      queryFn: () => api.information(id, requestId),
    });
  return r.isPending ? (
    <LoadingState />
  ) : r.error ? (
    <ErrorState error={r.error} />
  ) : (
    <InformationForm
      key={requestId + ':' + r.data.requestVersion + ':' + r.data.requirementsVersion}
      request={r.data}
    />
  );
}
function InformationForm({ request: r }: { request: InformationRequest }) {
  const query = useQueryClient(),
    navigate = useNavigate(),
    suppress = useRef(false),
    command = useRef<ReturnType<typeof api.respond> | null>(null);
  const actor = context.get()?.actor ?? '',
    company = context.get()?.companyId ?? '',
    retainedKey = actor + ':' + company + ':' + r.id;
  const [resource] = useState(() => {
    let existing = retained.get(retainedKey);
    if (!existing) {
      existing = new RetainedResource<ResponseForm, InformationRequest>(
        { finance: r.finance, confirmed: r.confirmed },
        r,
        async (value, snapshot) => {
          if (context.get()?.actor !== actor || context.get()?.companyId !== company)
            throw new Error('Контекст изменился. Вернитесь к запросу в прежней компании.');
          const saved = await api.saveInformation({ ...snapshot, ...value });
          query.setQueryData(['information', r.applicationId, r.id], saved);
          return saved;
        },
      );
      retained.set(retainedKey, existing);
    } else if (
      existing.queue.state === 'saved' &&
      existing.snapshot.draftVersion !== r.draftVersion
    )
      existing.replace({ finance: r.finance, confirmed: r.confirmed }, r);
    return existing;
  });
  const form = useForm<ResponseForm>({ defaultValues: resource.value }),
    [state, setState] = useState<SaveState>(resource.queue.state),
    [error, setError] = useState<unknown>(resource.error),
    [pending, setPending] = useState(false),
    [conflict, setConflict] = useState<InformationRequest>();
  useEffect(
    () =>
      resource.subscribe((state, error) => {
        setState(state);
        setError(error);
      }),
    [resource],
  );
  useEffect(() => {
    const subscription = form.watch(() => {
      if (!suppress.current) resource.enqueue(form.getValues());
    });
    return () => subscription.unsubscribe();
  }, [form, resource]);
  const send = form.handleSubmit(async () => {
    setPending(true);
    setError(undefined);
    try {
      await resource.queue.flush();
      const fresh = await api.information(r.applicationId, r.id);
      if (
        fresh.draftVersion !== resource.snapshot.draftVersion ||
        fresh.requestVersion !== resource.snapshot.requestVersion ||
        fresh.requirementsVersion !== resource.snapshot.requirementsVersion ||
        fresh.financialVersion !== resource.snapshot.financialVersion
      )
        throw new ApiError(412, 'Запрос изменился. Сопоставьте версии.');
      const docs = await api.documents(r.applicationId);
      if (docs.some((d) => d.status === 'SCANNING' || d.status === 'QUARANTINE'))
        throw new Error('Дождитесь проверки документов');
      if (!command.current) command.current = api.respond(fresh, docs);
      const result = await command.current.send();
      retained.delete(retainedKey);
      query.setQueryData(['application', result.id], result);
      void query.invalidateQueries({ queryKey: ['applications'] });
      navigate(`/applications/${r.applicationId}/status`);
    } catch (e) {
      setError(e);
      if (e instanceof ApiError && (e.status === 409 || e.status === 412)) setState('conflict');
    } finally {
      setPending(false);
    }
  });
  return (
    <>
      <PageTitle
        eyebrow="УТОЧНЕНИЕ ПО ВАШЕЙ ЗАЯВКЕ"
        title="Один ответ — и движемся дальше"
        description={`Ответьте до ${new Date(r.dueAt).toLocaleDateString('ru-RU')}. Новая заявка не создаётся.`}
      />
      <Alert type="info" className="mb" message="Что нужно уточнить" description={userMessage(r.message,'Проверьте данные, отмеченные в запросе, и отправьте уточнения.')} />
      <Panel>
        <form onSubmit={send}>
          <div className="spread">
            <h2>Финансовые данные</h2>
            <span role="status">
              {state === 'saved'
                ? 'Сохранено'
                : state === 'saving'
                  ? 'Сохранение…'
                  : state === 'pending'
                    ? 'Есть изменения'
                    : 'Ошибка сохранения'}
            </span>
          </div>
          <p className="muted">
            Доступны только запрошенные поля. Остальные значения показаны для контекста.
          </p>
          <div className="financial-grid">
            {(Object.entries(financeFields) as [FinanceKey, string][]).map(([k, label]) => (
              <Field
                key={k}
                id={'rfi-' + k}
                label={label}
                hint={
                  resource.snapshot.editableFields.includes(k)
                    ? 'Запрошено уточнение · ₽'
                    : 'Не запрошено · только чтение'
                }
                error={form.formState.errors.finance?.[k]?.message}
              >
                <input
                  id={'rfi-' + k}
                  inputMode="decimal"
                  readOnly={!resource.snapshot.editableFields.includes(k)}
                  {...form.register(`finance.${k}`, {
                    required: 'Укажите значение',
                    onChange: () => form.setValue('confirmed', false),
                  })}
                />
              </Field>
            ))}
          </div>
          <label className="native-check mt">
            <input
              type="checkbox"
              {...form.register('confirmed', { validate: (v) => v || 'Подтвердите ответ' })}
            />
            Подтверждаю уточнённые сведения
          </label>
          {form.formState.errors.confirmed && (
            <p className="field-error">Подтвердите проверенные финансовые показатели</p>
          )}
          {!!error && (
            <div className="mt">
              <ErrorState error={error} />
              {state === 'conflict' ? (
                <Button
                  className="mt"
                  onClick={() => void api.information(r.applicationId, r.id).then(setConflict)}
                >
                  Сопоставить версии
                </Button>
              ) : state === 'error' ? (
                <Button className="mt" onClick={() => void resource.queue.retry().catch(() => {})}>
                  Повторить сохранение
                </Button>
              ) : null}
            </div>
          )}
          <div className="form-actions">
            <Link className="button white" to={`/applications/${r.applicationId}/status`}>
              К статусу заявки
            </Link>
            <Button type="primary" htmlType="submit" loading={pending}>
              Отправить ответ
            </Button>
          </div>
        </form>
      </Panel>
      {r.documentRequired && (
        <div className="mt">
          <Alert
            type="warning"
            message="Приложите подтверждающий документ"
            description="Отправка доступна после получения статуса «Проверен»."
          />
          <DocumentUploader applicationId={r.applicationId} />
        </div>
      )}
      <Modal
        title="Изменения в ответе на запрос"
        open={!!conflict}
        onCancel={() => setConflict(undefined)}
        footer={null}
      >
        <h3>Ваш ввод</h3>
        <pre>{JSON.stringify(form.getValues().finance, null, 2)}</pre>
        <h3>Серверная версия</h3>
        <pre>{JSON.stringify(conflict?.finance, null, 2)}</pre>
        <p>Обновление требований требует повторной проверки запрошенных полей.</p>
        <Button
          onClick={() => {
            if (!conflict) return;
            suppress.current = true;
            resource.replace({ finance: conflict.finance, confirmed: false }, conflict);
            form.reset({ finance: conflict.finance, confirmed: false });
            suppress.current = false;
            setConflict(undefined);
            query.setQueryData(['information', r.applicationId, r.id], conflict);
          }}
        >
          Загрузить актуальный запрос
        </Button>
      </Modal>
    </>
  );
}
