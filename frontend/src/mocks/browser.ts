import { setupWorker } from 'msw/browser';
import { delay, http } from 'msw';
import { DemoStore } from './store';
import type { Scenario } from '../shared/types/domain';
const scenarios: Scenario[] = [
  'success',
  'rfi',
  'manual',
  'declined',
  'network',
  'conflict',
  'ocr-failed',
];
const configured = import.meta.env.VITE_DEMO_SCENARIO ?? 'success';
if (!scenarios.includes(configured as Scenario)) throw new Error('Неизвестный VITE_DEMO_SCENARIO');
const store = new DemoStore(configured as Scenario);
export const worker = setupWorker(
  http.get('/api/events', ({ request }) => {
    if (!store.session) return new Response(null, { status: 401 });
    let cursor = Number(request.headers.get('Last-Event-ID') ?? 0),
      timer: ReturnType<typeof setInterval>;
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder();
        timer = setInterval(() => {
          const events = store.events.filter((e) => Number(e.id) > cursor);
          const data = events.length ? events : [{ id: String(cursor), type: 'heartbeat' }];
          for (const e of data) {
            controller.enqueue(encoder.encode(`id: ${e.id}\ndata: ${JSON.stringify(e)}\n\n`));
            cursor = Number(e.id);
          }
        }, 800);
        request.signal.addEventListener(
          'abort',
          () => {
            clearInterval(timer);
            try {
              controller.close();
            } catch {
              /* Уже закрыт */
            }
          },
          { once: true },
        );
      },
      cancel() {
        clearInterval(timer);
      },
    });
    return new Response(stream, {
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    });
  }),
  http.all('/api/*', async ({ request }) => {
    await delay(request.url.includes('/assistant/') && request.method === 'POST' ? 1000 : 220);
    return store.dispatch(request);
  }),
);
