import type { ReactNode } from 'react';
import { Alert, Button, Empty, Skeleton, Tag } from 'antd';
import { ArrowRight, Check, CircleAlert, Clock3, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Application, Status } from '../types/domain';
import { money } from '../lib/money';
import { ApiError } from '../api/http';
import { financeFields } from '../types/domain';
export const statusLabels: Record<Status, string> = {
  DRAFT: 'Черновик',
  SUBMITTED: 'Отправлена',
  REVIEW: 'На рассмотрении',
  NEEDS_INFO: 'Нужно уточнение',
  MANUAL: 'Ручная проверка',
  DECLINED: 'Отрицательное решение',
  APPROVED: 'Предложение готово',
  ACCEPTED: 'Условия приняты',
  COMPLETED: 'Оформление завершено',
  ALTERNATIVE: 'Альтернативное предложение',
  CANCELLED: 'Отменена',
  EXPIRED: 'Срок истёк',
};
export function StatusBadge({ status }: { status: Status }) {
  return (
    <Tag
      className="status"
      color={
        status === 'DECLINED'
          ? 'red'
          : status === 'NEEDS_INFO'
            ? 'orange'
            : ['APPROVED', 'COMPLETED'].includes(status)
              ? 'green'
              : status === 'DRAFT'
                ? 'default'
                : 'blue'
      }
    >
      {statusLabels[status]}
    </Tag>
  );
}
export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 tabIndex={-1}>{title}</h1>
        {description && <p className="muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>;
}
export function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className={'field' + (error ? ' invalid' : '')}>
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && <small>{hint}</small>}
      {!!error && (
        <span className="field-error" role="alert" id={id + '-error'}>
          {error}
        </span>
      )}
    </div>
  );
}
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <Alert
      type="error"
      showIcon
      message="Не удалось выполнить действие"
      description={
        <>
          <span>{error instanceof Error ? error.message : 'Сервис недоступен'}</span>
          {error instanceof ApiError && Object.keys(error.fields).length > 0 && (
            <ul>
              {Object.entries(error.fields).map(([field, message]) => (
                <li key={field}>
                  {financeFields[field.replace('finance.', '') as keyof typeof financeFields] ??
                    (
                      {
                        companyName: 'Название компании',
                        address: 'Адрес',
                        activity: 'Деятельность',
                        period: 'Период',
                        consents: 'Согласие',
                        confirmed: 'Подтверждение',
                      } as Record<string, string>
                    )[field] ??
                    'Поле заявки'}
                  : {message}
                </li>
              ))}
            </ul>
          )}
          {retry && (
            <div className="mt">
              <Button onClick={retry}>Повторить</Button>
            </div>
          )}
        </>
      }
    />
  );
}
export function LoadingState() {
  return (
    <Panel>
      <Skeleton active paragraph={{ rows: 5 }} />
    </Panel>
  );
}
export function EmptyState({ description, action }: { description: string; action?: ReactNode }) {
  return (
    <Panel>
      <Empty description={description}>{action}</Empty>
    </Panel>
  );
}
export function NextActionCard({ application }: { application: Application }) {
  return application.nextAction ? (
    <div className="next-action">
      <span className="action-icon">
        <CircleAlert size={23} />
      </span>
      <div>
        <p className="eyebrow">Следующий шаг</p>
        <h3>{application.nextAction.label}</h3>
        <p>
          Заявка № {application.id.slice(0, 8)} · {money(application.need.amount)}
        </p>
      </div>
      <Link className="button red" to={application.nextAction.href}>
        {application.nextAction.label} <ArrowRight size={17} />
      </Link>
    </div>
  ) : null;
}
export function ApplicationCard({ application: a }: { application: Application }) {
  return (
    <article className="application-card">
      <div className="spread">
        <span className="muted">№ {a.id.slice(0, 8)}</span>
        <StatusBadge status={a.status} />
      </div>
      <h3>
        {a.productId === 'working-capital'
          ? 'Оборотный кредит'
          : a.productId === 'credit-line'
            ? 'Кредитная линия'
            : 'Овердрафт'}
      </h3>
      <strong className="amount">{money(a.need.amount)}</strong>
      <p className="muted">
        {a.need.months} мес. · {a.need.purpose}
      </p>
      <div className="card-bottom">
        <span>
          <Clock3 size={14} /> {new Date(a.createdAt).toLocaleDateString('ru-RU')}
        </span>
        <Link
          to={
            a.status === 'DRAFT' ? `/applications/${a.id}/company` : `/applications/${a.id}/status`
          }
        >
          Открыть <ArrowRight size={16} />
        </Link>
      </div>
    </article>
  );
}
export function AssistantWidget() {
  return (
    <Panel className="assistant-widget">
      <div className="spark-icon">
        <Sparkles size={25} />
      </div>
      <h3>Разберёмся вместе</h3>
      <p className="muted">
        Какие документы подготовить? Как заполнить заявку? Чат с помощником скоро появится. Пока доступны инструкции по заполнению.
      </p>
      <Link className="button white" to="/assistant">
        AI-помощник · скоро <ArrowRight size={16} />
      </Link>
      <small>Не оценивает вероятность одобрения</small>
    </Panel>
  );
}
export function Stepper({ id, step }: { id: string; step: string }) {
  const steps = [
    ['company', 'Компания'],
    ['business', 'Финансы'],
    ['documents', 'Документы'],
    ['review', 'Проверка'],
  ];
  const active = steps.findIndex(([key]) => key === step);
  return (
    <nav className="stepper" aria-label="Шаги заявки">
      {steps.map(([key, label], index) => (
        <Link
          key={key}
          to={`/applications/${id}/${key}`}
          aria-current={key === step ? 'step' : undefined}
          className={index === active ? 'active' : index < active ? 'done' : ''}
        >
          <span>{index < active ? <Check size={14} /> : index + 1}</span>
          {label}
        </Link>
      ))}
    </nav>
  );
}
export function Disclosure() {
  return (
    <p className="disclosure">
      Учебный прототип. Синтетические условия не являются офертой и не гарантируют одобрение. Не
      является официальным продуктом банка.
    </p>
  );
}
