import type { QueryClient } from '@tanstack/react-query';
import { context, responseError, request } from './http';
import type { StreamEvent } from '../types/domain';
export async function consumeSse(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  signal: AbortSignal,
  onEvent: (e: StreamEvent) => void,
) {
  const decoder = new TextDecoder();
  let buffer = '';
  while (!signal.aborted) {
    const part = await reader.read();
    if (part.done) break;
    buffer = (buffer + decoder.decode(part.value, { stream: true })).replace(/\r\n/g, '\n');
    if (buffer.length > 65536) throw new Error('Событие превышает допустимый размер');
    let split: number;
    while ((split = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      const data = block
        .split('\n')
        .filter((l) => l.startsWith('data:'))
        .map((l) => l.slice(5).trimStart())
        .join('\n');
      if (data) onEvent(JSON.parse(data) as StreamEvent);
    }
  }
}
export function startEvents(query: QueryClient, changed: (stale: boolean) => void) {
  const master = new AbortController();
  let cursor = '',
    attempt = 0;
  const wait = (ms: number) =>
    new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, ms);
      master.signal.addEventListener(
        'abort',
        () => {
          clearTimeout(timer);
          resolve();
        },
        { once: true },
      );
    });
  const sync = async () => {
    let page: string | undefined;
    do {
      const snapshot = await request<{ complete: boolean; cursor: string; nextPage?: string }>(
        '/api/sync' + (page ? `?page=${encodeURIComponent(page)}` : ''),
        { signal: master.signal },
      );
      cursor = snapshot.cursor;
      if (!snapshot.complete && !snapshot.nextPage) throw new Error('Неполный snapshot');
      page = snapshot.nextPage;
    } while (page);
    await query.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'session' });
  };
  const loop = async () => {
    while (!master.signal.aborted) {
      const connection = new AbortController();
      const abort = () => connection.abort();
      master.signal.addEventListener('abort', abort, { once: true });
      let heartbeat: ReturnType<typeof setTimeout> | undefined;
      try {
        const session = context.get();
        const response = await fetch('/api/events', {
          credentials: 'include',
          headers: {
            Accept: 'text/event-stream',
            'Last-Event-ID': cursor,
            'X-Company-Context': String(session?.contextVersion ?? 0),
          },
          signal: connection.signal,
        });
        if (!response.ok) throw await responseError(response);
        if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body)
          throw new Error('Поток событий недоступен');
        const touch = () => {
          clearTimeout(heartbeat);
          heartbeat = setTimeout(() => connection.abort(), 15000);
        };
        touch();
        changed(false);
        attempt = 0;
        await consumeSse(response.body.getReader(), connection.signal, (event) => {
          touch();
          cursor = event.id;
          changed(false);
          if (event.type === 'gap') {
            void sync().catch(() => changed(true));
            return;
          }
          if (event.type === 'heartbeat') return;
          void query.invalidateQueries({
            predicate: (q) => q.queryKey[0] !== 'session' && q.queryKey[0] !== 'conversation',
          });
        });
        if (!master.signal.aborted) throw new Error('Поток закрыт');
      } catch (error) {
        if (master.signal.aborted) break;
        changed(true);
        if ((error as { status?: number }).status === 401) {
          window.dispatchEvent(new Event('session-expired'));
          break;
        }
        attempt++;
        await wait(Math.min(1000 * 2 ** Math.min(attempt, 4), 16000));
        if (!master.signal.aborted)
          try {
            await sync();
          } catch {
            /* Сохраняем предыдущие данные */
          }
      } finally {
        clearTimeout(heartbeat);
        master.signal.removeEventListener('abort', abort);
      }
    }
  };
  void loop();
  return () => master.abort();
}
