import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { Alert, Button, Timeline } from 'antd';
import { CheckCircle2, Clock3, RefreshCw } from 'lucide-react';
import { api } from '../../shared/api/client';
import { recoverOperations } from '../../shared/api/commands';
import {
  AssistantWidget,
  ErrorState,
  LoadingState,
  NextActionCard,
  PageTitle,
  Panel,
  StatusBadge,
  statusLabels,
} from '../../shared/ui/common';
import { money } from '../../shared/lib/money';
export function StatusPage() {
  const { id = '' } = useParams(),
    a = useQuery({
      queryKey: ['application', id],
      queryFn: () => api.application(id),
      refetchInterval: (q) =>
        q.state.data && ['SUBMITTED', 'PROCESSING'].includes(q.state.data.status) ? 2500 : false,
    }),
    operations = useQuery({ queryKey: ['operations'], queryFn: recoverOperations });
  if (a.isPending) return <LoadingState />;
  if (a.error) return <ErrorState error={a.error} retry={() => void a.refetch()} />;
  const app = a.data;
  return (
    <>
      <PageTitle
        eyebrow={'ЗАЯВКА № ' + id.slice(0, 8)}
        title="Каждый шаг — на виду"
        description="Следите за рассмотрением и следующими действиями в одном месте."
        action={
          <Button
            icon={<RefreshCw size={16} />}
            onClick={() => void a.refetch()}
            loading={a.isFetching}
          >
            Обновить
          </Button>
        }
      />
      <div className="two-column">
        <div>
          <Panel className="status-panel">
            <div className="status-orb">
              {app.status === 'COMPLETED' ? <CheckCircle2 size={32} /> : <Clock3 size={32} />}
            </div>
            <StatusBadge status={app.status} />
            <h2>{statusLabels[app.status]}</h2>
            <strong className="amount">{money(app.need.amount)}</strong>
            <p className="muted">
              {app.need.purpose} · {app.need.months} мес.
            </p>
            {app.status === 'MANUAL' && (
              <Alert
                type="info"
                message="Заявку проверяет специалист"
                description="Это не отказ. Следите за сообщениями: при необходимости появится запрос уточнений."
              />
            )}
            {app.status === 'DECLINED' && (
              <Alert
                type="warning"
                message="Рассмотрение завершено с отрицательным решением"
                description="По этой заявке принято отрицательное решение. Вы можете изучить другие продукты и выбрать подходящий вариант."
              />
            )}
            {app.status === 'COMPLETED' && <Alert type="success" message="Оформление завершено" />}
            {['SUBMITTED', 'PROCESSING'].includes(app.status) && (
              <p>Мы приняли заявку. Здесь появится результат или запрос дополнительных сведений.</p>
            )}
            {app.status === 'DECLINED' && (
              <p>
                <Link to="/products">Изучить другие продукты →</Link>
              </p>
            )}
            <Link to={`/applications/${id}/files`}>Документы заявки →</Link>
          </Panel>
          <div className="mt">
            <NextActionCard application={app} />
          </div>
          <Panel className="mt">
            <h2>История заявки</h2>
            <Timeline
              items={app.history.map((h) => ({
                color: 'red',
                children: (
                  <div>
                    <strong>{h.title}</strong>
                    <p className="muted small">{new Date(h.at).toLocaleString('ru-RU')}</p>
                  </div>
                ),
              }))}
            />
          </Panel>
          {operations.error && (
            <Alert
              className="mt"
              type="warning"
              message="Не удалось сверить операции"
              description="Перед повтором значимой команды восстановите связь и обновите статус."
            />
          )}
        </div>
        <AssistantWidget />
      </div>
    </>
  );
}
