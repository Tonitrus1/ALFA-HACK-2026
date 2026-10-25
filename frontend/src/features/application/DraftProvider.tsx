import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import type { UseFormReturn } from 'react-hook-form';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Outlet, useLocation, useParams } from 'react-router-dom';
import { Alert, Button, Modal } from 'antd';
import { api } from '../../shared/api/client';
import { RetainedResource } from '../../shared/lib/retainedResource';
import type { SaveState } from '../../shared/lib/autosave';
import type { Application, Draft } from '../../shared/types/domain';
import { ErrorState, LoadingState, Stepper } from '../../shared/ui/common';
import { context } from '../../shared/api/http';
import { financeFields } from '../../shared/types/domain';
function DraftSummary({draft}:{draft?:Draft}){
  if(!draft)return <p>Загружаем сохранённые данные…</p>;
  return <dl className="details">{Object.entries({Компания:draft.companyName,Деятельность:draft.activity,'Срок работы, месяцев':draft.businessAgeMonths,'Предварительная выручка, ₽':draft.preliminaryRevenue,'Отчётный год':draft.period,...Object.fromEntries(Object.entries(financeFields).map(([key,label])=>[label+', ₽',draft.finance[key as keyof typeof financeFields]]))}).map(([label,value])=><div className="detail-row" key={label}><dt>{label}</dt><dd>{value?.trim()||'Не заполнено'}</dd></div>)}</dl>;
}
interface DraftContext {
  application: Application;
  form: UseFormReturn<Draft>;
  flush: () => Promise<void>;
  version: () => number;
  replace: (a: Application) => void;
}
const DraftState = createContext<DraftContext | null>(null);
const retained = new Map<string, RetainedResource<Draft, Application>>();
export function DraftRoute() {
  const { id = '' } = useParams(),
    a = useQuery({ queryKey: ['application', id], queryFn: () => api.application(id) });
  if (a.isPending) return <LoadingState />;
  if (a.error) return <ErrorState error={a.error} retry={() => void a.refetch()} />;
  return (
    <DraftEditor key={id + ':' + a.data.companyId} application={a.data}>
      <Outlet />
    </DraftEditor>
  );
}
function DraftEditor({ application, children }: { application: Application; children: ReactNode }) {
  const query = useQueryClient(),
    location = useLocation(),
    suppress = useRef(false);
  const [resource] = useState(() => {
    const actor = context.get()?.actor ?? '',
      companyId = application.companyId,
      key = actor + ':' + companyId + ':' + application.id;
    let existing = retained.get(key);
    if (!existing) {
      existing = new RetainedResource(application.draft, application, async (draft, snapshot) => {
        if (context.get()?.companyId !== companyId || context.get()?.actor !== actor)
          throw new Error('Компания изменилась. Вернитесь к черновику в прежней компании.');
        const saved = await api.save(application.id, draft, snapshot.version);
        query.setQueryData(['application', application.id], saved);
        return saved;
      });
      retained.set(key, existing);
    } else if (
      existing.queue.state === 'saved' &&
      existing.snapshot.version !== application.version
    )
      existing.replace(application.draft, application);
    return existing;
  });
  const form = useForm<Draft>({ defaultValues: resource.value, mode: 'onBlur' }),
    [state, setState] = useState<SaveState>(resource.queue.state),
    [error, setError] = useState<unknown>(resource.error),
    [comparison, setComparison] = useState<Application>(),
    [modal, setModal] = useState(false);
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
  const replace = (a: Application) => {
    suppress.current = true;
    resource.replace(a.draft, a);
    form.reset(a.draft);
    query.setQueryData(['application', a.id], a);
    suppress.current = false;
  };
  const compare = async () => {
    try {
      setComparison(await api.application(application.id));
      setModal(true);
    } catch (e) {
      setError(e);
    }
  };
  const stage = location.pathname.split('/').at(-1) ?? 'company',
    remoteChanged = application.version > resource.snapshot.version && state === 'saved';
  return (
    <DraftState.Provider
      value={{
        application,
        form,
        flush: () => resource.queue.flush(),
        version: () => resource.snapshot.version,
        replace,
      }}
    >
      <FormProvider {...form}>
        <div className="spread">
          <p className="eyebrow">ЗАЯВКА № {application.id.slice(0, 8)}</p>
          <span role="status" className={'save-indicator ' + state}>
            <span />
            {
              {
                saved: 'Сохранено',
                pending: 'Есть изменения',
                saving: 'Сохранение…',
                error: 'Ошибка сохранения',
                conflict: 'Конфликт версий',
              }[state]
            }
          </span>
        </div>
        <Stepper id={application.id} step={stage} />
        {application.status !== 'DRAFT' ? (
          <Alert
            type="info"
            message="Заявка уже отправлена"
            description={
              <Link to={`/applications/${application.id}/status`}>
                Открыть статус и отправленный снимок
              </Link>
            }
          />
        ) : (
          <>
            {(state === 'error' || state === 'conflict' || remoteChanged) && (
              <div className="mb">
                <ErrorState
                  error={
                    error ??
                    new Error('На сервере появилась новая версия. Сопоставьте её с вашим вводом.')
                  }
                />
                <div className="mt">
                  {state === 'conflict' || remoteChanged ? (
                    <Button onClick={() => void compare()}>Сопоставить версии</Button>
                  ) : (
                    <Button onClick={() => void resource.queue.retry().catch(() => {})}>
                      Повторить сохранение
                    </Button>
                  )}
                </div>
              </div>
            )}
            {children}
          </>
        )}
        <Modal
          title="Сопоставьте изменения"
          open={modal}
          onCancel={() => setModal(false)}
          footer={null}
        >
          <p>
            Ваш ввод сохранён в памяти. Выберите, какую версию оставить. Ничего не перезаписывается
            автоматически.
          </p>
          <div className="compare-grid">
            <div>
              <h3>Ваш ввод</h3>
              <DraftSummary draft={form.getValues()}/>
            </div>
            <div>
              <h3>Сервер · версия {comparison?.version}</h3>
              <DraftSummary draft={comparison?.draft}/>
            </div>
          </div>
          <div className="form-actions">
            <Button
              onClick={() => {
                if (comparison) replace(comparison);
                setModal(false);
              }}
            >
              Загрузить серверную версию
            </Button>
            <Button
              type="primary"
              onClick={() => {
                if (!comparison) return;
                resource.replace(form.getValues(), comparison);
                resource.enqueue(form.getValues());
                setModal(false);
                void resource.queue.flush().catch(() => {});
              }}
            >
              Сохранить мой ввод поверх версии {comparison?.version}
            </Button>
          </div>
        </Modal>
      </FormProvider>
    </DraftState.Provider>
  );
}
export function useDraft() {
  const state = useContext(DraftState);
  if (!state) throw new Error('DraftProvider missing');
  return state;
}
