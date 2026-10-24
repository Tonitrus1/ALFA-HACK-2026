import type { Session } from '../types/domain';
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fields: Record<string, string> = {},
    public retryAfter = 0,
  ) {
    super(message);
  }
}
const messages: Record<number, string> = {
  401: 'Сессия завершена. Войдите снова. Несохранённый ввод остаётся в этой вкладке.',
  403: 'Недостаточно полномочий',
  404: 'Объект не найден или недоступен',
  409: 'Данные изменились. Сопоставьте версии перед сохранением.',
  412: 'Версия устарела. Сопоставьте версии перед сохранением.',
  422: 'Проверьте заполнение полей',
  429: 'Слишком много запросов. Подождите перед повтором.',
  503: 'Сервис временно недоступен. Повторите позже.',
};
let session: Session | null = null;
let generation = 0;
const controllers = new Set<AbortController>();
export function trackController(controller: AbortController) {
  controllers.add(controller);
  return () => {
    controllers.delete(controller);
  };
}
const backoffs = new Map<string, number>();
export const context = {
  get: () => session,
  set: (s: Session | null) => {
    session = s;
  },
  reset: () => {
    generation++;
    controllers.forEach((c) => c.abort());
    controllers.clear();
    session = null;
  },
  get generation() {
    return generation;
  },
};
export function retryDelay(value: string | null): number {
  if (!value) return 0;
  return /^\d+$/.test(value) ? Number(value) * 1000 : Math.max(0, Date.parse(value) - Date.now());
}
export async function responseError(response: Response, file = false): Promise<ApiError> {
  let detail: { message?: string; fields?: Record<string, string> } = {};
  if (!file && response.headers.get('content-type')?.includes('json')) {
    try {
      detail = await response.json();
    } catch {
      /* Безопасное стандартное сообщение */
    }
  }
  return new ApiError(
    response.status,
    detail.message ??
      messages[response.status] ??
      (file ? 'Не удалось получить файл' : 'Не удалось выполнить запрос'),
    detail.fields,
    retryDelay(response.headers.get('Retry-After')),
  );
}
export async function request<T>(path: string, init: RequestInit = {}, file = false): Promise<T> {
  const until = backoffs.get(path) ?? 0;
  if (until > Date.now())
    throw new ApiError(
      429,
      'Повторите после паузы: ' + Math.ceil((until - Date.now()) / 1000) + ' с.',
      {},
      until - Date.now(),
    );
  const controller = new AbortController(),
    ownGeneration = generation;
  controllers.add(controller);
  const abort = () => controller.abort(init.signal?.reason);
  init.signal?.addEventListener('abort', abort, { once: true });
  if (init.signal?.aborted) abort();
  const timeout = setTimeout(
    () => controller.abort(new DOMException('Время ожидания истекло', 'TimeoutError')),
    65000,
  );
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && init.body)
    headers.set('Content-Type', 'application/json');
  if (session) {
    headers.set('X-Company-Context', String(session.contextVersion));
    if (init.method && init.method !== 'GET') headers.set('X-CSRF-Token', session.csrfToken);
  }
  try {
    const response = await fetch(path, {
      ...init,
      headers,
      credentials: 'include',
      signal: controller.signal,
    });
    if (ownGeneration !== generation) throw new DOMException('Компания изменилась', 'AbortError');
    if (!response.ok) {
      const error = await responseError(response, file);
      if (error.retryAfter > 0) backoffs.set(path, Date.now() + error.retryAfter);
      if (response.status === 401) window.dispatchEvent(new Event('session-expired'));
      throw error;
    }
    if (file) return (await response.blob()) as T;
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } finally {
    clearTimeout(timeout);
    controllers.delete(controller);
    init.signal?.removeEventListener('abort', abort);
  }
}
