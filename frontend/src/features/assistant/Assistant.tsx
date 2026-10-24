import { useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { Alert, Button } from 'antd';
import { ArrowUp, BookOpen, Sparkles, Square } from 'lucide-react';
import { api } from '../../shared/api/client';
import type { AssistantMessage } from '../../shared/types/domain';
import { ErrorState, PageTitle, Panel } from '../../shared/ui/common';
export function allowedSource(href: string) {
  if (/^\/help\/(application|finance)$/.test(href)) return true;
  try { const u=new URL(href); return u.protocol==='https:' && ['alfabank.ru','cbr.ru','fincult.info','nalog.gov.ru'].some(d=>u.hostname===d || u.hostname.endsWith('.'+d)); } catch { return false; }
}
export function Assistant() {
  const { conversationId = 'general' } = useParams(),
    query = useQueryClient(),
    history = useQuery({
      queryKey: ['conversation', conversationId],
      queryFn: () => api.conversation(conversationId),
    }),
    form = useForm({ defaultValues: { text: '' } }),
    [pending, setPending] = useState(false),
    [error, setError] = useState<unknown>(),
    [cancelled, setCancelled] = useState(false),
    controller = useRef<AbortController | null>(null);
  const submit = form.handleSubmit(async ({ text }) => {
    if (!text.trim() || pending) return;
    setPending(true);
    setError(undefined);
    setCancelled(false);
    controller.current = new AbortController();
    const user: AssistantMessage = { id: crypto.randomUUID(), role: 'user', text };
    query.setQueryData<AssistantMessage[]>(['conversation', conversationId], (old) => [
      ...(old ?? []),
      user,
    ]);
    form.reset();
    try {
      const answer = await api.ask(conversationId, text, controller.current.signal);
      query.setQueryData<AssistantMessage[]>(['conversation', conversationId], (old) => [
        ...(old ?? []),
        answer,
      ]);
    } catch (e) {
      if (controller.current.signal.aborted) setCancelled(true);
      else setError(e);
    } finally {
      setPending(false);
    }
  });
  return (
    <>
      <PageTitle
        eyebrow="ПОМОЩНИК ПО ВАШЕМУ ДЕЛУ"
        title="Сложные вопросы. Понятные ответы."
        description="Поможет найти информацию и пройти путь заявки. Не принимает кредитных решений."
      />
      <div className="assistant-layout">
        <Panel className="chat-panel">
          <div className="chat-messages" aria-live="polite">
            {!history.data?.length && (
              <div className="chat-welcome">
                <span className="spark-icon">
                  <Sparkles size={30} />
                </span>
                <h2>С чего начнём?</h2>
                <p className="muted">
                  Спросите о документах, финансовых показателях или этапах рассмотрения.
                </p>
                {[
                  'Что нужно для подачи заявки?',
                  'Как подтвердить финансовые данные?',
                  'Покажи ссылки на источники',
                ].map((text) => (
                  <button
                    className="suggestion"
                    key={text}
                    onClick={() => form.setValue('text', text)}
                  >
                    {text} ↗
                  </button>
                ))}
              </div>
            )}
            {history.data?.map((m) => (
              <article className={'chat-message ' + m.role} key={m.id}>
                <span className="eyebrow">{m.role === 'user' ? 'ВЫ' : 'ПОМОЩНИК'}</span>
                <p>{m.revoked ? 'Ответ скрыт: источник больше недоступен.' : m.text}</p>
                {!m.revoked && m.state === 'SEARCH_ONLY' && (
                  <p className="muted">Доступен только поиск по источникам.</p>
                )}
                {!m.revoked && m.state === 'INSUFFICIENT_EVIDENCE' && (
                  <span className="muted">Недостаточно проверяемых данных для ответа.</span>
                )}
                {!m.revoked &&
                  m.sources
                    ?.filter((s) => allowedSource(s.href))
                    .map((s) => (
                      <a className="source-link" href={s.href} key={s.href} target="_blank" rel="noopener noreferrer">
                        <BookOpen size={14} />
                        {s.title}
                      </a>
                    ))}
              </article>
            ))}
            {pending && (
              <p role="status" className="muted">
                Ищем ответ в базе знаний… Запрос можно отменить.
              </p>
            )}
            {cancelled && <p role="status">Запрос отменён. Можно продолжить оформление заявки.</p>}
            {!!(error || history.error) && <ErrorState error={error ?? history.error} />}
          </div>
          <form className="chat-compose" onSubmit={submit}>
            <label className="sr-only" htmlFor="question">
              Ваш вопрос
            </label>
            <textarea
              id="question"
              placeholder="Например, какие документы подготовить?"
              rows={2}
              maxLength={2000}
              {...form.register('text', { required: true, maxLength: 2000 })}
            />
            {pending ? (
              <Button
                aria-label="Отменить запрос"
                icon={<Square size={16} />}
                onClick={() => controller.current?.abort()}
              />
            ) : (
              <Button
                type="primary"
                htmlType="submit"
                aria-label="Отправить вопрос"
                icon={<ArrowUp size={21} />}
              />
            )}
          </form>
          <small className="muted">
            Ответ может содержать ошибки. Проверяйте источники. Лимит ожидания — 65 секунд.
          </small>
        </Panel>
        <Panel className="assistant-rules">
          <h3>На что можно опереться</h3>
          <p>Ответы сопровождаются разрешёнными источниками базы знаний.</p>
          <Alert
            type="info"
            message="Решения — в заявке"
            description="Помощник не обещает одобрение, не объясняет персональную риск-оценку и не подписывает документы."
          />
          <Link to="/workspace">Вернуться в кабинет →</Link>
        </Panel>
      </div>
    </>
  );
}
