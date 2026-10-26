import { context, request } from './http';
import type { Operation } from '../types/domain';
interface CommandRecord {
  key: string;
  company: string;
  resource: string;
  type: string;
  createdAt: string;
}
const storageKey = 'flow-command-keys-v1';
function records(): CommandRecord[] {
  try {
    return JSON.parse(sessionStorage.getItem(storageKey) ?? '[]') as CommandRecord[];
  } catch {
    return [];
  }
}
function persist(record: CommandRecord) {
  try {
    sessionStorage.setItem(
      storageKey,
      JSON.stringify([...records().filter((r) => r.key !== record.key), record].slice(-100)),
    );
  } catch {
    /* Работа без storage разрешена; сверка по серверному списку */
  }
}
// В storage только метаданные: ни body, ни финансов, ни токенов.
export function createCommand<T>(
  path: string,
  resource: string,
  type: string,
  body: unknown,
  version?: number,
) {
  const key = crypto.randomUUID(),
    payload = JSON.stringify(body),
    company = context.get()?.companyId ?? '';
  persist({ key, company, resource, type, createdAt: new Date().toISOString() });
  let active: Promise<T> | undefined;
  const send = (): Promise<T> => {
    if (active) return active;
    active = request<T>(path, {
      method: 'POST',
      headers: {
        'Idempotency-Key': key,
        ...(version !== undefined ? { 'If-Match': `"${version}"` } : {}),
      },
      body: payload,
    })
      .catch(async (error) => {
        if (
          error instanceof TypeError ||
          (error instanceof DOMException && error.name === 'TimeoutError')
        ) {
          const operation = await request<Operation | null>(`/api/operations/by-key/${key}`);
          if (operation?.status === 'COMPLETED') return operation.result as T;
        }
        throw error;
      })
      .finally(() => {
        active = undefined;
      });
    return active;
  };
  return { key, send };
}
export async function recoverOperations(): Promise<Operation[]> {
  const company = context.get()?.companyId;
  const stored = records().filter(
    (r) => r.company === company && Date.now() - Date.parse(r.createdAt) < 7 * 86400000,
  );
  const list = await request<Operation[]>('/api/operations?windowDays=7');
  const recovered = await Promise.all(
    stored.map((r) => request<Operation | null>(`/api/operations/by-key/${r.key}`)),
  );
  return [
    ...new Map(
      [...list, ...recovered.filter((x): x is Operation => x !== null)].map((o) => [o.key, o]),
    ).values(),
  ];
}
