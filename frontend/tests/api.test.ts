import { describe, expect, it } from 'vitest';
import { retryDelay, responseError } from '../src/shared/api/http';
describe('нормализация ошибок', () => {
  it('сохраняет адресованные ошибки полей 422', async () => {
    const error = await responseError(
      Response.json(
        { message: 'Проверьте поля', fields: { 'finance.revenue': 'Уточните выручку' } },
        { status: 422 },
      ),
    );
    expect(error.fields).toEqual({ 'finance.revenue': 'Уточните выручку' });
  });
  it.each([401, 403, 404, 409, 412, 422, 429, 503])('обрабатывает %i', async (status) => {
    const e = await responseError(new Response('<html>private debug</html>', { status }));
    expect(e.status).toBe(status);
    expect(e.message).not.toContain('private debug');
  });
  it('учитывает Retry-After', () => expect(retryDelay('3')).toBe(3000));
  it('безопасно обрабатывает файловую ошибку', async () => {
    const e = await responseError(new Response('secret', { status: 500 }), true);
    expect(e.message).toBe('Не удалось получить файл');
  });
});
