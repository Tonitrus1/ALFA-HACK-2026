import { beforeEach, expect, it, vi } from 'vitest';
import { api } from '../src/shared/api/client';
import { context, request } from '../src/shared/api/http';

vi.mock('../src/shared/api/http', async (original) => ({
  ...await original<typeof import('../src/shared/api/http')>(), request: vi.fn(),
}));

beforeEach(() => { vi.mocked(request).mockReset(); context.reset(); });

it('sends login and password to the server and opens the company from its session', async () => {
  vi.mocked(request).mockImplementation(async path => {
    if (path === '/api/v1/auth/login') return {
      userId: 'representative-b', companyId: 'company-b', contextVersion: 1, csrfToken: 'csrf', expiresAt: '2030',
    };
    if (path === '/api/v1/companies') return { items: [{ companyId: 'company-b', displayName: 'Компания Б', taxId: '' }] };
    throw new Error('Unexpected request');
  });
  const session = await api.login(' company-b ', ' password-with-spaces ');
  expect(request).toHaveBeenNthCalledWith(1, '/api/v1/auth/login', {
    method: 'POST', body: JSON.stringify({ login: 'company-b', password: ' password-with-spaces ' }),
  });
  expect(session.companyId).toBe('company-b');
  expect(session.companies.map(c=>c.id)).toEqual(['company-b']);
  expect(session).not.toHaveProperty('password');
});
