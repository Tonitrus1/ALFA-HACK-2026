import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Bell, ArrowUpRight } from 'lucide-react';
import { api } from '../../shared/api/client';
import { EmptyState, ErrorState, LoadingState, PageTitle, Panel } from '../../shared/ui/common';
export function Inbox() {
  const query = useQueryClient(),
    n = useQuery({ queryKey: ['inbox'], queryFn: api.notices });
  return (
    <>
      <PageTitle
        eyebrow="НА СВЯЗИ"
        title="Ничего важного не пропустите"
        description="Запросы уточнений, готовые предложения и новости ваших заявок."
      />
      {n.isPending ? (
        <LoadingState />
      ) : n.error ? (
        <ErrorState error={n.error} />
      ) : !n.data.length ? (
        <EmptyState description="Новых сообщений пока нет" />
      ) : (
        <Panel>
          {n.data.map((item) => (
            <article className={'notice ' + (!item.read ? 'unread' : '')} key={item.id}>
              <span className="notice-icon">
                <Bell size={20} />
              </span>
              <div>
                <span className="eyebrow">{new Date(item.at).toLocaleString('ru-RU')}</span>
                <h3>
                  {item.title} {!item.read && <i aria-label="Непрочитано" />}
                </h3>
                <p className="muted">{item.text}</p>
                <Link
                  to={item.href}
                  onClick={() =>
                    void api
                      .readNotice(item.id)
                      .then(() => query.invalidateQueries({ queryKey: ['inbox'] }))
                  }
                >
                  Перейти к заявке <ArrowUpRight size={16} />
                </Link>
              </div>
            </article>
          ))}
        </Panel>
      )}
    </>
  );
}
