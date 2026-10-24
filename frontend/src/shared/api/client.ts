import type {
  Application,
  AssistantMessage,
  Company,
  DocumentItem,
  Draft,
  InformationRequest,
  Need,
  Notice,
  Offer,
  Product,
  Session,
} from '../types/domain';
import { documentReferences, submissionBody } from '../lib/submission';
import { createCommand } from './commands';
import { context, request, trackController } from './http';
const json = (body: unknown) => JSON.stringify(body);
export const api = {
  session: () => request<Session>('/api/session'),
  login: (name: string) =>
    request<Session>('/api/access/demo-login', { method: 'POST', body: json({ name }) }),
  logout: () => request<void>('/api/access/logout', { method: 'POST' }),
  companies: () => request<Company[]>('/api/companies'),
  selectCompany: (id: string) =>
    request<Session>('/api/session/company', { method: 'POST', body: json({ companyId: id }) }),
  products: (need?: Need) =>
    request<Product[]>(
      '/api/products' + (need ? `?amount=${need.amount}&months=${need.months}` : ''),
    ),
  product: (id: string) => request<Product>(`/api/products/${id}`),
  needs: (need: Need) => request<Need>('/api/needs', { method: 'PUT', body: json(need) }),
  getNeed: () => request<Need>('/api/needs'),
  applications: () => request<Application[]>('/api/applications'),
  application: (id: string) => request<Application>(`/api/applications/${id}`),
  createApplication: (productId: string, need: Need) =>
    createCommand<Application>('/api/applications', 'new', 'create', { productId, need }),
  save: (id: string, draft: Draft, version: number) =>
    request<Application>(`/api/applications/${id}`, {
      method: 'PATCH',
      headers: { 'If-Match': `"${version}"` },
      body: json({ draft }),
    }),
  submit: (app: Application, documents: DocumentItem[] = []) =>
    createCommand<Application>(
      `/api/applications/${app.id}/submit`,
      app.id,
      'submit',
      submissionBody(app, documents),
      app.version,
    ),
  documents: (id: string) => request<DocumentItem[]>(`/api/applications/${id}/documents`),
  upload: async (id: string, file: File, onProgress: (v: number) => void) => {
    const intent = await request<{ url: string; documentId: string; maxBytes: number }>(
      `/api/applications/${id}/upload-intents`,
      { method: 'POST', body: json({ name: file.name, size: file.size, type: file.type }) },
    );
    if (file.size > intent.maxBytes) throw new Error('Файл превышает допустимый размер');
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const controller = new AbortController(),
        generation = context.generation;
      const release = trackController(controller);
      controller.signal.addEventListener('abort', () => xhr.abort(), { once: true });
      xhr.onloadend = release;
      xhr.onabort = () =>
        reject(new DOMException('Загрузка отменена при смене контекста', 'AbortError'));
      xhr.open('PUT', intent.url);
      xhr.withCredentials = true;
      const s = context.get();
      if (s) {
        xhr.setRequestHeader('X-CSRF-Token', s.csrfToken);
        xhr.setRequestHeader('X-Company-Context', String(s.contextVersion));
      }
      xhr.timeout = 65000;
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && generation === context.generation)
          onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () =>
        xhr.status >= 200 && xhr.status < 300 && generation === context.generation
          ? resolve()
          : reject(new Error('Не удалось загрузить файл. Повторите загрузку.'));
      xhr.onerror = () => reject(new Error('Загрузка прервана'));
      xhr.ontimeout = () => reject(new Error('Время загрузки истекло'));
      xhr.send(file);
    });
    onProgress(100);
    return intent.documentId;
  },
  file: (documentId: string) => request<Blob>(`/api/documents/${documentId}/content`, {}, true),
  confirmOcr: (
    id: string,
    document: DocumentItem,
    finance: Draft['finance'],
    confirmed: Draft['confirmed'],
    financialVersion: number,
  ) =>
    request<Application>(`/api/applications/${id}/ocr-confirmations`, {
      method: 'POST',
      headers: { 'If-Match': `"${financialVersion}"` },
      body: json({
        documentId: document.id,
        objectVersion: document.objectVersion,
        extractionId: document.extractionId,
        finance,
        confirmed,
      }),
    }),
  information: (id: string, requestId: string) =>
    request<InformationRequest>(`/api/applications/${id}/information/${requestId}`),
  saveInformation: (r: InformationRequest) =>
    request<InformationRequest>(`/api/applications/${r.applicationId}/information/${r.id}`, {
      method: 'PATCH',
      headers: { 'If-Match': `"${r.draftVersion}"` },
      body: json(r),
    }),
  respond: (r: InformationRequest, documents: DocumentItem[] = []) =>
    createCommand<Application>(
      `/api/applications/${r.applicationId}/information/${r.id}/respond`,
      r.id,
      'rfi-response',
      {
        requestVersion: r.requestVersion,
        requirementsVersion: r.requirementsVersion,
        draftVersion: r.draftVersion,
        financialVersion: r.financialVersion,
        documentReferences: documentReferences(documents),
      },
      r.requestVersion,
    ),
  offer: (id: string) => request<Offer>(`/api/offers/${id}`),
  accept: (o: Offer) =>
    createCommand<Offer>(
      `/api/offers/${o.id}/accept`,
      o.id,
      'accept',
      { version: o.version },
      o.version,
    ),
  complete: (o: Offer) =>
    createCommand<Offer>(
      `/api/offers/${o.id}/complete`,
      o.id,
      'complete',
      { version: o.version },
      o.version,
    ),
  notices: () => request<Notice[]>('/api/inbox'),
  readNotice: (id: string) => request<void>(`/api/inbox/${id}/read`, { method: 'POST' }),
  conversation: (id: string) => request<AssistantMessage[]>(`/api/assistant/${id}`),
  ask: (id: string, text: string, signal: AbortSignal) =>
    request<AssistantMessage>(`/api/assistant/${id}`, {
      method: 'POST',
      body: json({ text }),
      signal,
    }),
  exposure: (itemId: string, type: 'VIEW' | 'CLICK', exposureId: string) =>
    request<void>('/api/feed/events', {
      method: 'POST',
      body: json({ clientEventId: crypto.randomUUID(), exposureId, itemId, type }),
    }),
};
