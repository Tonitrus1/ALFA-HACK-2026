/** Actual backend MVP client. No provisional-v1 routes, model scores or service tokens. */
export type Session = { userId: string; companyId?: string; contextVersion: number; csrfToken: string; expiresAt: string };
export type Preferences = {
  task?: 'PURCHASE' | 'CASH_GAP' | 'EQUIPMENT' | 'EXPANSION' | 'EXPLORING' | null;
  help?: 'AMOUNT' | 'OPTIONS' | 'COST' | 'APPLICATION' | null;
  depth?: 'BASICS' | 'EXPLAINED' | 'PRACTICAL' | null;
};
export type Card = { contentId: string; version: number; title: string; text: string; topic: string; depth: string;
  illustration: string; reason: string; reasonCategory: string; userReaction: 'HELPFUL' | 'NOT_INTERESTED' | null };
export type Feed = { cards: Card[]; rankingMode: 'MODEL' | 'RULES'; hasMore: boolean; nextCursor?: string;
  rankingMetadata: { exposureId: string; releaseId: string; mode: 'MODEL' | 'RULES'; catalogVersion: number; candidateSetDigest: string; catalogDigest: string } };
export type SavedFeed = { cards: Card[]; exposureId: string; catalogVersion: number; catalogDigest: string; savedVersion: number; hasMore: boolean; nextCursor?: string };
export type FinancialStatement = { periodStart: string; periodEnd: string; reportingStandard: 'DEMO'; currency: 'RUB';
  values: Record<'totalAssetsMinor' | 'totalLiabilitiesMinor' | 'currentAssetsMinor' | 'currentLiabilitiesMinor' | 'equityMinor' | 'revenueMinor' | 'netProfitMinor' | 'ebitMinor', number>;
  sourceDocumentReferences: { documentId: string; documentVersion: number; objectVersion: string }[] };

export class BackendApi {
  private session?: Session;
  private async request<T>(path: string, method = 'GET', body?: unknown, extra: Record<string, string> = {}): Promise<T> {
    const headers: Record<string, string> = { ...extra };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (this.session) {
      headers['X-Company-Context'] = String(this.session.contextVersion);
      if (method !== 'GET') headers['X-CSRF-Token'] = this.session.csrfToken;
    }
    const response = await fetch(path, { method, headers, credentials: 'include', body: body === undefined ? undefined : JSON.stringify(body) });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ code: 'REQUEST_FAILED' }));
      throw Object.assign(new Error(error.message ?? 'Запрос не выполнен'), { status: response.status, code: error.code });
    }
    return response.status === 204 ? undefined as T : await response.json() as T;
  }
  async login(accountId: string): Promise<Session> {
    this.session = await this.request<Session>('/demo/api/v1/session', 'POST', { accountId });
    return this.session;
  }
  async restore(): Promise<Session> { this.session = await this.request<Session>('/api/v1/session'); return this.session; }
  async selectCompany(companyId: string): Promise<Session> {
    this.session = await this.request<Session>('/api/v1/session/company', 'POST', { companyId }); return this.session;
  }
  private companyQuery(cursor?: string): string {
    if (!this.session?.companyId) throw new Error('Выберите компанию');
    const query = new URLSearchParams({ companyId: this.session.companyId });
    if (cursor) query.set('cursor', cursor);
    return query.toString();
  }
  preferences(): Promise<Preferences> { return this.request('/api/v1/feed/preferences?' + this.companyQuery()); }
  savePreferences(value: Preferences): Promise<Preferences> { return this.request('/api/v1/feed/preferences?' + this.companyQuery(), 'PUT', value); }
  feed(cursor?: string): Promise<Feed> { return this.request('/api/v1/feed?' + this.companyQuery(cursor)); }
  saved(cursor?: string): Promise<SavedFeed> { return this.request('/api/v1/feed/saved?' + this.companyQuery(cursor)); }
  feedback(exposureId: string, itemId: string, action: 'VIEW' | 'CLICK' | 'HELPFUL' | 'NOT_INTERESTED', clientEventId: string, occurredAt: string): Promise<unknown> {
    // On retry the caller MUST reuse clientEventId, occurredAt and the original payload.
    // VIEW is sent only after >=50% visibility for >=1000 ms, never on receipt of a page.
    return this.request('/api/v1/recommendation-feedback', 'POST', { exposureId, itemId, action, clientEventId, occurredAt });
  }
  financialStatement(applicationId: string): Promise<unknown> { return this.request(`/api/v1/applications/${encodeURIComponent(applicationId)}/financial-statement`); }
  saveFinancialStatement(applicationId: string, value: FinancialStatement, containerVersion: number, key: string): Promise<unknown> {
    for (const amount of Object.values(value.values)) if (!Number.isSafeInteger(amount)) throw new Error('Суммы должны быть целыми копейками');
    return this.request(`/api/v1/applications/${encodeURIComponent(applicationId)}/financial-statement`, 'PUT', value,
      { 'If-Match': `"v${containerVersion}"`, 'Idempotency-Key': key });
  }
}
