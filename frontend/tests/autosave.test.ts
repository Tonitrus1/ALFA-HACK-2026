import { describe, expect, it, vi } from 'vitest';
import { SaveQueue } from '../src/shared/lib/autosave';
describe('последовательное автосохранение', () => {
  it('объединяет ввод по debounce', async () => {
    vi.useFakeTimers();
    const save = vi.fn(async () => {}),
      queue = new SaveQueue(save, () => {}, 50);
    queue.enqueue('a');
    queue.enqueue('ab');
    await vi.advanceTimersByTimeAsync(50);
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith('ab');
    vi.useRealTimers();
  });
  it('не запускает второй запрос до завершения первого и сохраняет новый ввод', async () => {
    let release!: () => void;
    const saves: string[] = [];
    const queue = new SaveQueue<string>(
      async (v) => {
        saves.push(v);
        if (v === 'a')
          await new Promise<void>((r) => {
            release = r;
          });
      },
      () => {},
      60000,
    );
    queue.enqueue('a');
    const flushing = queue.flush();
    queue.enqueue('b');
    queue.enqueue('c');
    expect(saves).toEqual(['a']);
    release();
    await flushing;
    expect(saves).toEqual(['a', 'c']);
    expect(queue.state).toBe('saved');
  });
  it('блокирует flush при конфликте и не теряет ввод', async () => {
    let conflict = true;
    const saved: string[] = [];
    const queue = new SaveQueue<string>(
      async (v) => {
        if (conflict) throw Object.assign(new Error('CAS'), { status: 412 });
        saved.push(v);
      },
      () => {},
      60000,
    );
    queue.enqueue('a');
    await expect(queue.flush()).rejects.toThrow('CAS');
    queue.enqueue('b');
    await expect(queue.flush()).rejects.toThrow();
    expect(queue.state).toBe('conflict');
    conflict = false;
    await queue.retry();
    expect(saved).toEqual(['b']);
  });
});
