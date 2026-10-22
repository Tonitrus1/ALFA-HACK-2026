import type { QueryClient } from '@tanstack/react-query';
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
  let stopped = false;
  const timer = setInterval(() => { if (!stopped && document.visibilityState === 'visible') {
    void query.refetchQueries({ predicate: q => ['applications','application','documents','offer'].includes(String(q.queryKey[0])), type: 'active' }).then(() => changed(false)).catch(() => changed(true));
  } }, 5000);
  return () => {stopped=true;clearInterval(timer);};
}
