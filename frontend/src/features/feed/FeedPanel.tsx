import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Modal, Tooltip } from 'antd';
import {
  ArrowRight,
  Bookmark,
  BookOpen,
  ChevronDown,
  Clock3,
  SlidersHorizontal,
  Sparkles,
  ThumbsDown,
} from 'lucide-react';
import { api } from '../../shared/api/client';
import type { Card, Preferences, Feed, SavedFeed } from '../../shared/api/client';
import { context } from '../../shared/api/http';
import { ErrorState, LoadingState } from '../../shared/ui/common';

type Action = 'VIEW' | 'CLICK' | 'HELPFUL' | 'NOT_INTERESTED';
const pending = new Map<string, Parameters<typeof api.feedback>[0]>();
const topics: Record<string, { label: string; tone: string }> = {
  CASH_GAP: { label: 'Денежный поток', tone: 'mint' },
  WORKING_CAPITAL: { label: 'Оборотные средства', tone: 'sand' },
  EQUIPMENT: { label: 'Рост бизнеса', tone: 'lavender' },
  APPLICATION: { label: 'О заявке', tone: 'blue' },
  FINANCING_COST: { label: 'Стоимость финансирования', tone: 'peach' },
  SEASONALITY: { label: 'Планирование', tone: 'mint' },
};
const preferenceFields = [
  {
    key: 'task',
    label: 'Ваша задача',
    options: [
      ['PURCHASE', 'Закупка'],
      ['CASH_GAP', 'Кассовый разрыв'],
      ['EQUIPMENT', 'Оборудование'],
      ['EXPANSION', 'Расширение'],
      ['EXPLORING', 'Изучаю'],
    ],
  },
  {
    key: 'help',
    label: 'Чем помочь',
    options: [
      ['AMOUNT', 'Сумма'],
      ['OPTIONS', 'Варианты'],
      ['COST', 'Стоимость'],
      ['APPLICATION', 'Заявка'],
    ],
  },
  {
    key: 'depth',
    label: 'Глубина материала',
    options: [
      ['BASICS', 'Основы'],
      ['EXPLAINED', 'С объяснением'],
      ['PRACTICAL', 'Практика'],
    ],
  },
] as const;

function FeedbackCard({
  card,
  exposureId,
  onHidden,
}: {
  card: Card;
  exposureId: string;
  onHidden: (id: string) => void;
}) {
  const query = useQueryClient(),
    ref = useRef<HTMLElement>(null),
    viewed = useRef(false);
  const [error, setError] = useState<unknown>(),
    [opened, setOpened] = useState(false),
    [busy, setBusy] = useState(false),
    [reaction, setReaction] = useState(card.userReaction);
  const identity = [
    context.get()?.actor,
    context.get()?.companyId,
    exposureId,
    card.contentId,
  ].join(':');
  const sendRef = useRef<(action: Action) => Promise<void>>(async () => {});
  const topic = topics[card.topic] ?? {
    label: 'Для вашего бизнеса',
    tone: 'sand',
  };
  const minutes = Math.max(1, Math.ceil(card.text.trim().split(/\s+/).length / 180));
  const saved = reaction === 'HELPFUL';
  const send = async (action: Action) => {
    const key = identity + ':' + action;
    let event = pending.get(key);
    if (!event) {
      event = {
        clientEventId: crypto.randomUUID(),
        exposureId,
        itemId: card.contentId,
        action,
        occurredAt: new Date().toISOString(),
      };
      pending.set(key, event);
    }
    setBusy(true);
    try {
      await api.feedback(event);
      pending.delete(key);
      setError(undefined);
      if (action === 'VIEW') viewed.current = true;
      if (action === 'HELPFUL' || action === 'NOT_INTERESTED') {
        setReaction(action);
        await query.invalidateQueries({ queryKey: ['saved-feed'] });
        if (action === 'NOT_INTERESTED') onHidden(card.contentId);
      }
      if (action === 'CLICK') setOpened(true);
    } catch (e) {
      setError(e);
      throw e;
    } finally {
      setBusy(false);
    }
  };
  sendRef.current = send;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let timer: ReturnType<typeof setTimeout> | undefined,
      ratio = 0;
    const update = () => {
      clearTimeout(timer);
      if (ratio >= 0.5 && document.visibilityState === 'visible' && !viewed.current)
        timer = setTimeout(() => {
          void sendRef.current('VIEW').catch(() => {});
        }, 1000);
    };
    const observer = new IntersectionObserver(
      (entries) => {
        ratio = entries[0]?.intersectionRatio ?? 0;
        update();
      },
      { threshold: [0, 0.5, 1] },
    );
    observer.observe(el);
    document.addEventListener('visibilitychange', update);
    return () => {
      clearTimeout(timer);
      observer.disconnect();
      document.removeEventListener('visibilitychange', update);
    };
  }, [identity]);
  const retry = async () => {
    for (const event of [...pending.values()].filter(
      (e) => e.exposureId === exposureId && e.itemId === card.contentId,
    ))
      await send(event.action);
  };
  return (
    <>
      <article
        ref={ref}
        className={'feed-card feed-tone-' + topic.tone}
        data-testid="feed-card"
        data-content-id={card.contentId}
      >
        <button
          type="button"
          className="feed-card-art"
          aria-label={'Читать: ' + card.title}
          disabled={busy}
          onClick={() => void send('CLICK').catch(() => {})}
        >
          <img src={card.illustration} alt="" width="224" height="168" loading="lazy" />
        </button>
        <div className="feed-card-body">
          <div className="feed-card-meta">
            <span className="feed-card-topic">{topic.label}</span>
            <span className="feed-read-time">
              <Clock3 size={12} />
              {minutes} мин
            </span>
          </div>
          <h3>{card.title}</h3>
          <p className="feed-card-excerpt">{card.text}</p>
        </div>
        <div className="feed-card-footer">
          <p className="feed-card-reason">
            <Sparkles size={13} />
            <span>{card.reason}</span>
          </p>
          <div className="feed-card-actions">
            <Button
              type="text"
              className="feed-read-button"
              disabled={busy}
              onClick={() => void send('CLICK').catch(() => {})}
            >
              Читать <ArrowRight size={15} />
            </Button>
            <div className="feed-reactions">
              <Button
                type="text"
                className={'feed-save-button' + (saved ? ' is-saved' : '')}
                disabled={busy}
                aria-pressed={saved}
                onClick={() => void send('HELPFUL').catch(() => {})}
              >
                <Bookmark size={16} fill={saved ? 'currentColor' : 'none'} />
                {saved ? '✓ В полезном' : 'Полезно'}
              </Button>
              <Tooltip title="Показывать меньше похожего">
                <Button
                  type="text"
                  className="feed-dismiss-button"
                  aria-label="Не интересно"
                  disabled={busy}
                  onClick={() => void send('NOT_INTERESTED').catch(() => {})}
                  icon={<ThumbsDown size={16} />}
                />
              </Tooltip>
            </div>
          </div>
        </div>
        {!!error && (
          <div className="feed-card-error">
            <ErrorState error={error} retry={() => void retry().catch(() => {})} />
          </div>
        )}
      </article>
      <Modal
        className="feed-reader"
        title={
          <>
            <span className="feed-reader-topic">
              {topic.label} · {minutes} мин чтения
            </span>
            <h2>{card.title}</h2>
          </>
        }
        open={opened}
        onCancel={() => setOpened(false)}
        footer={null}
        width={680}
      >
        <div className="feed-reader-text">
          {card.text
            .split(/\n+/)
            .filter(Boolean)
            .map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
        </div>
        <div className="feed-reader-footer">
          <span>Сохраните, чтобы вернуться к материалу</span>
          <Button
            disabled={busy}
            icon={<Bookmark size={16} />}
            onClick={() => void send('HELPFUL').catch(() => {})}
          >
            {saved ? '✓ В полезном' : 'Полезно'}
          </Button>
        </div>
        {!!error && <ErrorState error={error} retry={() => void retry().catch(() => {})} />}
      </Modal>
    </>
  );
}

export function FeedPanel() {
  const company = context.get()?.companyId,
    query = useQueryClient();
  const [tab, setTab] = useState<'feed' | 'saved'>('feed'),
    [cursor, setCursor] = useState<string>(),
    [hidden, setHidden] = useState<string[]>([]),
    [error, setError] = useState<unknown>(),
    [saving, setSaving] = useState(false);
  const preferencesRef = useRef<HTMLDetailsElement>(null);
  const p = useQuery({
    queryKey: ['preferences', company],
    queryFn: api.preferences,
  });
  const [form, setForm] = useState<Preferences>({});
  useEffect(() => {
    if (p.data) setForm(p.data);
  }, [p.data]);
  const f = useQuery<Feed | SavedFeed>({
    queryKey: [tab === 'feed' ? 'feed' : 'saved-feed', company, cursor],
    queryFn: () => (tab === 'feed' ? api.feed(cursor) : api.saved(cursor)),
    staleTime: Infinity,
  });
  const save = async () => {
    setSaving(true);
    try {
      await api.savePreferences(form);
      setCursor(undefined);
      setHidden([]);
      await query.invalidateQueries({ queryKey: ['preferences'] });
      await query.resetQueries({ queryKey: ['feed'] });
      setError(undefined);
      if (preferencesRef.current) preferencesRef.current.open = false;
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
    }
  };
  const changeTab = (value: 'feed' | 'saved') => {
    setTab(value);
    setCursor(undefined);
    setHidden([]);
  };
  const page = f.data,
    exposure =
      page && ('rankingMetadata' in page ? page.rankingMetadata.exposureId : page.exposureId);
  const cards = page?.cards.filter((card) => !hidden.includes(card.contentId)) ?? [];
  return (
    <section className="feed-panel" aria-label="Материалы для вашего бизнеса">
      <div className="feed-toolbar">
        <div className="feed-tabs" aria-label="Разделы материалов">
          <button type="button" aria-pressed={tab === 'feed'} onClick={() => changeTab('feed')}>
            <Sparkles size={15} />
            Подборка
          </button>
          <button type="button" aria-pressed={tab === 'saved'} onClick={() => changeTab('saved')}>
            <Bookmark size={15} />
            Полезные материалы
          </button>
        </div>
        <span className="feed-toolbar-note">Идеи, которые помогают расти</span>
      </div>
      <details className="feed-preferences" ref={preferencesRef}>
        <summary>
          <SlidersHorizontal size={15} />
          <span>Настроить подборку</span>
          <ChevronDown size={15} />
        </summary>
        <div className="feed-preferences-content">
          <p>Что сейчас важно для вашего бизнеса? Подберём материалы под вашу задачу.</p>
          <div className="feed-preference-fields">
            {preferenceFields.map(({ key, label, options }) => (
              <label key={key}>
                {label}
                <select
                  aria-label={key}
                  value={form[key] ?? ''}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value || null })}
                >
                  <option value="">Без предпочтения</option>
                  {options.map(([value, title]) => (
                    <option value={value} key={value}>
                      {title}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <Button type="primary" loading={saving} onClick={() => void save()}>
            Сохранить предпочтения
          </Button>
        </div>
      </details>
      {!!(p.error || error) && <ErrorState error={p.error || error} />}
      {f.isPending ? (
        <LoadingState />
      ) : f.error ? (
        <ErrorState
          error={f.error}
          retry={() => {
            setCursor(undefined);
            void f.refetch();
          }}
        />
      ) : (
        <>
          <div className="feed-cards">
            {cards.map((card) => (
              <FeedbackCard
                key={exposure + ':' + card.contentId}
                card={card}
                exposureId={exposure!}
                onHidden={(id) => setHidden((value) => [...value, id])}
              />
            ))}
          </div>
          {!cards.length && (
            <div className="feed-empty">
              <BookOpen size={28} />
              <h3>
                {tab === 'saved'
                  ? 'Всё полезное — в одном месте'
                  : 'Пока нет подходящих материалов'}
              </h3>
              <p>
                {tab === 'saved'
                  ? 'Отмечайте материалы кнопкой «Полезно», чтобы сохранить их здесь.'
                  : 'Измените предпочтения или загляните чуть позже — подберём что-нибудь для вас.'}
              </p>
            </div>
          )}
          {page?.hasMore && (
            <Button className="feed-next-page" onClick={() => setCursor(page.nextCursor)}>
              Следующая страница <ArrowRight size={15} />
            </Button>
          )}
        </>
      )}
    </section>
  );
}
