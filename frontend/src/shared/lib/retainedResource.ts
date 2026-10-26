import { SaveQueue } from './autosave';
import type { SaveState } from './autosave';
// Одна очередь живёт в памяти ресурса и переживает размонтирование формы.
export class RetainedResource<T, S> {
  readonly queue: SaveQueue<T>;
  error: unknown;
  private listeners = new Set<(state: SaveState, error?: unknown) => void>();
  constructor(
    public value: T,
    public snapshot: S,
    save: (value: T, snapshot: S) => Promise<S>,
  ) {
    this.queue = new SaveQueue(
      async (value) => {
        this.snapshot = await save(value, this.snapshot);
      },
      (state, error) => {
        this.error = error;
        this.listeners.forEach((listener) => listener(state, error));
      },
    );
  }
  enqueue(value: T) {
    this.value = structuredClone(value);
    this.queue.enqueue(value);
  }
  subscribe(listener: (state: SaveState, error?: unknown) => void) {
    this.listeners.add(listener);
    listener(this.queue.state, this.error);
    return () => {
      this.listeners.delete(listener);
    };
  }
  replace(value: T, snapshot: S) {
    this.value = structuredClone(value);
    this.snapshot = snapshot;
    this.queue.discard();
  }
}
