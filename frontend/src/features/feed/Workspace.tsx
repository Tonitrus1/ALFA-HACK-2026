import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  ArrowUpRight,
  FileCheck2,
  Plus,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { FeedPanel } from './FeedPanel';
import { api } from '../../shared/api/client';
import { useSession } from '../../app/session';
import {
  ApplicationCard,
  AssistantWidget,
  EmptyState,
  ErrorState,
  LoadingState,
  NextActionCard,
  PageTitle,
  Panel,
} from '../../shared/ui/common';
export function Workspace() {
  const { session } = useSession(),
    applications = useQuery({ queryKey: ['applications'], queryFn: api.applications });
  const list = applications.data ?? [],
    active = list.filter((a) => !['DECLINED', 'COMPLETED'].includes(a.status)),
    next = list.find((a) => a.status === 'NEEDS_INFO') ?? list.find((a) => a.nextAction);
  return (
    <>
      <PageTitle
        eyebrow="ВАШ БИЗНЕС В ДВИЖЕНИИ"
        title={`Добрый день, ${session?.actor ?? 'коллега'}`}
        description="Здесь всё, что нужно для следующего шага вашего дела."
        action={
          <span className="today">
            {new Date().toLocaleDateString('ru-RU', {
              day: 'numeric',
              month: 'long',
              year: 'numeric',
            })}
          </span>
        }
      />
      <section className="hero-banner">
        <div className="hero-copy">
          <span className="hero-label">
            <span />
            ФИНАНСИРОВАНИЕ ДЛЯ БИЗНЕСА
          </span>
          <h2>
            Планируйте смелее.
            <br />
            Растите с уверенностью.
          </h2>
          <p>
            Подберите финансирование под вашу цель.
            <br />
            Весь путь — онлайн, в понятных шагах.
          </p>
          <Link className="button hero-button" to="/needs">
            Подобрать финансирование <ArrowUpRight size={19} />
          </Link>
          <small>Условия определяются после рассмотрения заявки</small>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="art-grid" />
          <div className="growth-block block-a" />
          <div className="growth-block block-b" />
          <div className="growth-block block-c" />
          <div className="art-arrow">↗</div>
          <div className="growth-chip">
            <TrendingUp size={18} />
            <span>Время расти</span>
          </div>
          <div className="art-dot" />
        </div>
      </section>
      <div className="stats-row">
        <div>
          <span className="stat-icon peach">
            <FileCheck2 />
          </span>
          <span>
            <strong>{active.length}</strong>
            <small>Активных заявок</small>
          </span>
        </div>
        <div>
          <span className="stat-icon green">
            <TrendingUp />
          </span>
          <span>
            <strong>{list.filter((a) => a.status === 'APPROVED').length}</strong>
            <small>Предложений готово</small>
          </span>
        </div>
        <div>
          <span className="stat-icon violet">
            <Sparkles />
          </span>
          <span>
            <strong>Каталог</strong>
            <small>Серверные условия</small>
          </span>
        </div>
      </div>
      {next && <NextActionCard application={next} />}
      <div className="workspace-grid">
        <div>
          <div className="section-heading">
            <h2>
              Ваши заявки <span>{list.length}</span>
            </h2>
            <Link to="/needs">
              <Plus size={16} />
              Новая заявка
            </Link>
          </div>
          {applications.isPending ? (
            <LoadingState />
          ) : applications.error ? (
            <ErrorState error={applications.error} retry={() => void applications.refetch()} />
          ) : list.length ? (
            <div className="application-list">
              {list.map((a) => (
                <ApplicationCard key={a.id} application={a} />
              ))}
            </div>
          ) : (
            <EmptyState
              description="Здесь появится ваша первая заявка"
              action={
                <Link className="button white" to="/needs">
                  Выбрать финансирование <ArrowRight size={15} />
                </Link>
              }
            />
          )}
          <div className="section-heading feed-heading">
            <h2>Полезно для вашего дела</h2>
            <span className="muted">Персональная подборка</span>
          </div>
          <FeedPanel />
        </div>
        <aside className="right-rail">
          <AssistantWidget />
          <Panel className="journey-preview">
            <h3>Простой путь к решению</h3>
            {['Подберите продукт', 'Заполните заявку', 'Получите результат'].map((t, i) => (
              <div key={t}>
                <span>{i + 1}</span>
                <p>
                  {t}
                  <small>
                    {
                      [
                        'Под вашу цель и сумму',
                        'Данные, финансы, согласия',
                        'Статус и следующий шаг',
                      ][i]
                    }
                  </small>
                </p>
              </div>
            ))}
            <p className="muted">Вы всегда знаете, что происходит.</p>
          </Panel>
        </aside>
      </div>
    </>
  );
}
