import { expect, it } from 'vitest';
import { consumeSse } from '../src/shared/api/events';
import type { StreamEvent } from '../src/shared/types/domain';
it('собирает SSE из произвольных чанков и учитывает heartbeat', async () => {
  const encoder = new TextEncoder(),
    source =
      'id: 1\r\ndata: {"id":"1","type":"application","resourceId":"a"}\r\n\r\n: keep-alive\r\n\r\nid: 2\r\ndata: {"id":"2","type":"heartbeat"}\r\n\r\n';
  const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (let i = 0; i < source.length; i += 7)
          controller.enqueue(encoder.encode(source.slice(i, i + 7)));
        controller.close();
      },
    }),
    events: StreamEvent[] = [];
  await consumeSse(stream.getReader(), new AbortController().signal, (e) => events.push(e));
  expect(events.map((e) => e.type)).toEqual(['application', 'heartbeat']);
  expect(events[0].resourceId).toBe('a');
});
