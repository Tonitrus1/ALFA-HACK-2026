export type SaveState = 'saved' | 'pending' | 'saving' | 'error' | 'conflict';
// Одна очередь на ресурс. Ответ сервера никогда не используется для reset формы.
export class SaveQueue<T> {
  private pending: T | undefined;
  private running: Promise<void> | undefined;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private failure: unknown;
  state: SaveState = 'saved';
  constructor(
    private save: (value: T) => Promise<void>,
    private changed: (state: SaveState, error?: unknown) => void,
    private delay = 600,
  ) {}
  private set(state: SaveState, error?: unknown) {
    this.state = state;
    this.changed(state, error);
  }
  enqueue(value: T) {
    this.pending = structuredClone(value);
    clearTimeout(this.timer);
    if (this.failure) return;
    this.set('pending');
    this.timer = setTimeout(() => {
      void this.flush().catch(() => {});
    }, this.delay);
  }
  async flush(): Promise<void> {
    clearTimeout(this.timer);
    if (this.failure) throw this.failure;
    if (this.running) {
      await this.running;
      return this.flush();
    }
    const execute = async () => {
      while (this.pending !== undefined) {
        const value = this.pending;
        this.pending = undefined;
        this.set('saving');
        try {
          await this.save(value);
        } catch (error) {
          if (this.pending === undefined) this.pending = value;
          this.failure = error;
          const code = (error as { status?: number }).status;
          this.set(code === 409 || code === 412 ? 'conflict' : 'error', error);
          throw error;
        }
      }
      this.set('saved');
    };
    this.running = execute();
    try {
      await this.running;
    } finally {
      this.running = undefined;
    }
  }
  async retry() {
    this.failure = undefined;
    return this.flush();
  }
  discard() {
    clearTimeout(this.timer);
    this.pending = undefined;
    this.failure = undefined;
    this.set('saved');
  }
  stop() {
    clearTimeout(this.timer);
  }
}
