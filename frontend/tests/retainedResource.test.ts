import { expect, it, vi } from 'vitest';
import { RetainedResource } from '../src/shared/lib/retainedResource';
it('сохраняет одну очередь и новую версию после размонтирования подписчика', async () => {
  let release!: () => void;
  const saves: { value: string; version: number }[] = [];
  const resource = new RetainedResource('initial', 1, async (value, version) => {
    saves.push({ value, version });
    if (value === 'first')
      await new Promise<void>((resolve) => {
        release = resolve;
      });
    return version + 1;
  });
  const old = vi.fn(),
    newView = vi.fn(),
    unsubscribe = resource.subscribe(old);
  resource.enqueue('first');
  const saving = resource.queue.flush();
  unsubscribe();
  resource.subscribe(newView);
  resource.enqueue('second');
  expect(saves).toHaveLength(1);
  release();
  await saving;
  expect(saves).toEqual([
    { value: 'first', version: 1 },
    { value: 'second', version: 2 },
  ]);
  expect(resource.snapshot).toBe(3);
  expect(resource.value).toBe('second');
  expect(newView).toHaveBeenLastCalledWith('saved', undefined);
});
