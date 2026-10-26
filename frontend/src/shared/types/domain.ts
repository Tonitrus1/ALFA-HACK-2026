// ВРЕМЕННЫЙ контракт: оригинальные OpenAPI и state-machine недоступны.
export const financeFields = {
  revenue: 'Выручка',
  netProfit: 'Чистая прибыль',
  ebit: 'EBIT',
  equity: 'Собственный капитал',
  totalAssets: 'Активы',
  currentAssets: 'Оборотные активы',
  currentLiabilities: 'Краткосрочные обязательства',
  totalLiabilities: 'Все обязательства',
} as const;
export type FinanceKey = keyof typeof financeFields;
export const signedFields: FinanceKey[] = ['netProfit', 'ebit', 'equity'];
export type Finance = Record<FinanceKey, string>;
export type Status =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'REVIEW'
  | 'NEEDS_INFO'
  | 'MANUAL'
  | 'DECLINED'
  | 'APPROVED'
  | 'ACCEPTED'
  | 'COMPLETED'
  | 'ALTERNATIVE'
  | 'CANCELLED'
  | 'EXPIRED';
export interface Company {
  id: string;
  name: string;
  inn: string;
  industry: string;
  address: string;
}
export interface Session {
  actor: string;
  companyId: string | null;
  contextVersion: number;
  csrfToken: string;
  expiresAt: string;
  companies: Company[];
}
export interface Need {
  purpose: string;
  amount: string;
  months: number;
}
export interface Product {
  id: string;
  version?: number;
  title: string;
  description: string;
  maxAmount: string;
  minAmount: string;
  maxMonths: number;
  rate: string;
  eligible: boolean;
  restriction: string;
  benefits: string[];
}
export interface Draft {
  companyName: string;
  inn: string;
  address: string;
  activity: string;
  businessAgeMonths?: string;
  preliminaryRevenue?: string;
  period: string;
  currency: 'RUB';
  unit: 'RUB';
  finance: Finance;
  confirmed: Record<FinanceKey, boolean>;
  consents: boolean;
}
export interface HistoryEvent {
  id: string;
  title: string;
  at: string;
}
export interface Application {
  id: string;
  companyId: string;
  productId: string;
  need: Need;
  status: Status;
  version: number;
  financialVersion: number;
  draft: Draft;
  history: HistoryEvent[];
  createdAt: string;
  nextAction: { label: string; href: string } | null;
  requestId?: string;
  offerId?: string;
}
export interface InformationRequest {
  id: string;
  applicationId: string;
  requestVersion: number;
  requirementsVersion: number;
  draftVersion: number;
  financialVersion: number;
  editableFields: FinanceKey[];
  message: string;
  dueAt: string;
  documentRequired: boolean;
  finance: Finance;
  confirmed: boolean;
}
export interface DocumentItem {
  id: string;
  applicationId: string;
  name: string;
  size: number;
  type: string;
  objectVersion: string | number;
  documentVersion?: number;
  status: 'QUARANTINE' | 'SCANNING' | 'CLEAN' | 'FAILED';
  ocrStatus: 'PENDING' | 'READY' | 'FAILED';
  extractionId?: string;
  extractedPeriod?: string;
  values?: Finance;
  canDownload: boolean;
}
export interface Offer {
  id: string;
  applicationId: string;
  version: number;
  amount: string;
  months: number;
  rate: string;
  expiresAt: string;
  status: 'AVAILABLE' | 'ACCEPTED' | 'COMPLETED' | 'EXPIRED' | 'WITHDRAWN';
  termsDisclosure?: string;
}
export interface Notice {
  id: string;
  title: string;
  text: string;
  href: string;
  read: boolean;
  at: string;
}
export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  state?: 'ANSWER' | 'SEARCH_ONLY' | 'INSUFFICIENT_EVIDENCE';
  sources?: { title: string; href: string }[];
  revoked?: boolean;
}
export interface Operation {
  key: string;
  resourceId: string;
  status: 'PENDING' | 'COMPLETED' | 'FAILED';
  result?: unknown;
}
export interface StreamEvent {
  id: string;
  type: 'application' | 'document' | 'offer' | 'gap' | 'heartbeat';
  resourceId?: string;
}
export type Scenario =
  'success' | 'rfi' | 'manual' | 'declined' | 'network' | 'conflict' | 'ocr-failed';
