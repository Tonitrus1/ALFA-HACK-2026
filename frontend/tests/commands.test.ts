import { afterEach, describe, expect, it, vi } from 'vitest';
import { createCommand, recoverOperations } from '../src/shared/api/commands';
import { context } from '../src/shared/api/http';
afterEach(() => {
  vi.unstubAllGlobals();
  context.set(null);
});
describe('идемпотентные команды', () => {
  it('повторяет прежний ключ и тело, а в storage держит только метаданные', async () => {
    const values = new Map<string, string>();
    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => values.get(k) ?? null,
      setItem: (k: string, v: string) => values.set(k, v),
    });
    context.set({
      actor: 'Тест',
      companyId: 'atelier',
      contextVersion: 1,
      csrfToken: 'not-to-store',
      companies: [],
      expiresAt: new Date().toISOString(),
    });
    const calls: { key: string | null; body: BodyInit | null | undefined }[] = [];
    let first = true;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string, init: RequestInit) => {
        if (path.includes('/operations/by-key/')) return Response.json(null);
        calls.push({ key: new Headers(init.headers).get('Idempotency-Key'), body: init.body });
        if (first) {
          first = false;
          throw new TypeError('network');
        }
        return Response.json({ ok: true });
      }),
    );
    const body = { amount: '123456789' },
      command = createCommand('/api/submit', 'resource', 'submit', body, 3);
    body.amount = 'changed';
    await expect(command.send()).rejects.toThrow('network');
    await expect(command.send()).resolves.toEqual({ ok: true });
    expect(calls[0]).toEqual(calls[1]);
    expect(calls[1].body).toBe('{"amount":"123456789"}');
    const stored = [...values.values()].join('');
    expect(stored).not.toContain('123456789');
    expect(stored).not.toContain('not-to-store');
    expect(stored).toContain(command.key);
  });
  it('находит завершённую операцию после потери ответа', async () => {
    vi.stubGlobal('sessionStorage', { getItem: () => null, setItem: () => {} });
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string) => {
        if (path.includes('/operations/by-key/'))
          return Response.json({
            key: 'key',
            resourceId: 'app',
            status: 'COMPLETED',
            result: { id: 'recovered' },
          });
        throw new TypeError('response lost');
      }),
    );
    await expect(createCommand('/api/submit', 'app', 'submit', {}).send()).resolves.toEqual({
      id: 'recovered',
    });
  });
  it('сверяет также серверный список операций после reload', async () => {
    vi.stubGlobal('sessionStorage', { getItem: () => null, setItem: () => {} });
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json([{ key: 'unknown-to-tab', resourceId: 'app', status: 'COMPLETED' }]),
      ),
    );
    expect(await recoverOperations()).toHaveLength(1);
  });
});
