import type {
  Application,
  AssistantMessage,
  Company,
  DocumentItem,
  Draft,
  Finance,
  InformationRequest,
  Need,
  Notice,
  Offer,
  Operation,
  Product,
  Scenario,
  Session,
  Status,
  StreamEvent,
} from '../shared/types/domain';
import { documentReferences, financialSnapshot } from '../shared/lib/submission';
import { canTransition } from '../shared/lib/stateMachine';
import { financeFields } from '../shared/types/domain';
import { financeErrors } from '../shared/lib/validation';
import { fromKopecks, toKopecks } from '../shared/lib/money';
const now = () => new Date().toISOString();
const id = () => crypto.randomUUID();
const companies: Company[] = [
  {
    id: 'atelier',
    name: 'ООО «Мастерская роста»',
    inn: '0000000000',
    industry: 'Производство и торговля',
    address: 'Демонстрационный город, ул. Мастерская, 12',
  },
  {
    id: 'coffee',
    name: 'ООО «Кофе и дело»',
    inn: '0000000001',
    industry: 'Общественное питание',
    address: 'Демонстрационный город, ул. Кофейная, 7',
  },
];
export const products: Product[] = [
  {
    id: 'working-capital',
    title: 'Оборотный кредит',
    description: 'На закупки, новые заказы и ежедневное развитие бизнеса.',
    minAmount: '10000000',
    maxAmount: '1000000000',
    maxMonths: 36,
    rate: '24,5',
    eligible: true,
    restriction: 'Срок работы бизнеса от 12 месяцев. Разовая выдача.',
    benefits: ['Без залога в демосценарии', 'Фиксированный срок', 'Понятный график платежей'],
  },
  {
    id: 'credit-line',
    title: 'Кредитная линия',
    description: 'Резерв финансирования, к которому можно возвращаться.',
    minAmount: '50000000',
    maxAmount: '5000000000',
    maxMonths: 24,
    rate: '25,0',
    eligible: true,
    restriction: 'Каждый транш в пределах согласованного лимита.',
    benefits: [
      'Возобновляемый лимит',
      'Проценты на использованную сумму',
      'Для регулярных закупок',
    ],
  },
  {
    id: 'overdraft',
    title: 'Овердрафт',
    description: 'Для коротких кассовых разрывов между поступлениями.',
    minAmount: '10000000',
    maxAmount: '300000000',
    maxMonths: 12,
    rate: '26,0',
    eligible: true,
    restriction: 'Нужен расчётный счёт и регулярные поступления.',
    benefits: ['Короткий срок', 'Погашение из поступлений', 'Резерв для платежей'],
  },
];
export const initialFinance: Finance = {
  revenue: '12000000',
  netProfit: '1800000',
  ebit: '2300000',
  equity: '4500000',
  totalAssets: '9000000',
  currentAssets: '5000000',
  currentLiabilities: '2000000',
  totalLiabilities: '1500000',
};
export function initialDraft(company: Company): Draft {
  return {
    companyName: company.name,
    inn: company.inn,
    address: company.address,
    activity: company.industry,
    period: '2025',
    currency: 'RUB',
    unit: 'RUB',
    finance: { ...initialFinance },
    confirmed: Object.fromEntries(
      Object.keys(financeFields).map((k) => [k, false]),
    ) as Draft['confirmed'],
    consents: false,
  };
}
class Failure extends Error {
  constructor(
    public code: number,
    message: string,
  ) {
    super(message);
  }
}
export class DemoStore {
  session: Session | null = null;
  applications = new Map<string, Application>();
  documents = new Map<string, DocumentItem>();
  fileContents = new Map<string, ArrayBuffer>();
  offers = new Map<string, Offer>();
  information = new Map<string, InformationRequest>();
  notices: Notice[] = [];
  conversations = new Map<string, AssistantMessage[]>();
  operations = new Map<string, Operation & { body: string }>();
  events: StreamEvent[] = [];
  private needs = new Map<string, Need>();
  get need(): Need {
    return (
      this.needs.get(this.session?.companyId ?? '') ?? {
        purpose: 'Пополнение оборотных средств',
        amount: '300000000',
        months: 12,
      }
    );
  }
  set need(value: Need) {
    this.needs.set(this.session?.companyId ?? '', value);
  }
  private faults = new Set<string>();
  constructor(
    public scenario: Scenario = 'success',
    private autoProgress = true,
  ) {}
  emit(type: StreamEvent['type'], resourceId?: string) {
    this.events.push({ id: String(this.events.length + 1), type, resourceId });
  }
  private fail(code: number, message: string): never {
    throw new Failure(code, message);
  }
  private app(id: string) {
    const a = this.applications.get(id);
    if (!a || a.companyId !== this.session?.companyId) this.fail(404, 'Заявка недоступна');
    return a;
  }
  private bump(a: Application, status: Status, title: string) {
    if (!canTransition(a.status, status)) this.fail(409, 'Переход недоступен');
    a.status = status;
    a.version++;
    a.history.push({ id: id(), title, at: now() });
    a.nextAction = null;
    this.emit('application', a.id);
  }
  private notice(a: Application, title: string, href: string) {
    this.notices.unshift({
      id: id(),
      title,
      text: `Заявка № ${a.id.slice(0, 8)}`,
      href,
      read: false,
      at: now(),
    });
  }
  progress(a: Application, afterRfi = false) {
    if (a.status === 'SUBMITTED') {
      this.bump(a, 'REVIEW', 'Заявка принята в рассмотрение');
      return;
    }
    if (a.status !== 'REVIEW') return;
    if (this.scenario === 'rfi' && !afterRfi) {
      const requestId = id();
      a.requestId = requestId;
      this.information.set(requestId, {
        id: requestId,
        applicationId: a.id,
        requestVersion: 1,
        requirementsVersion: 1,
        draftVersion: 1,
        financialVersion: a.financialVersion,
        editableFields: ['revenue'],
        message: 'Уточните выручку за отчётный период. Остальные показатели менять не требуется.',
        dueAt: new Date(Date.now() + 3 * 86400000).toISOString(),
        documentRequired: true,
        finance: { ...a.draft.finance },
        confirmed: false,
      });
      this.bump(a, 'NEEDS_INFO', 'Запрошено уточнение выручки');
      a.nextAction = {
        label: 'Ответить на запрос',
        href: `/applications/${a.id}/information/${requestId}`,
      };
      this.notice(a, 'Нужны дополнительные сведения', a.nextAction.href);
    } else if (this.scenario === 'manual') {
      this.bump(a, 'MANUAL', 'Заявка передана специалисту');
      this.notice(a, 'Идёт ручная проверка', `/applications/${a.id}/status`);
    } else if (this.scenario === 'declined') {
      this.bump(a, 'DECLINED', 'По демосценарию принято отрицательное решение');
      this.notice(a, 'Рассмотрение завершено', `/applications/${a.id}/status`);
    } else {
      const offerId = id();
      a.offerId = offerId;
      this.offers.set(offerId, {
        id: offerId,
        applicationId: a.id,
        version: 1,
        amount: a.need.amount,
        months: a.need.months,
        rate: '24,5',
        expiresAt: new Date(Date.now() + 7 * 86400000).toISOString(),
        status: 'AVAILABLE',
      });
      this.bump(a, 'APPROVED', 'Подготовлено демонстрационное предложение');
      a.nextAction = { label: 'Посмотреть предложение', href: `/offers/${offerId}` };
      this.notice(a, 'Предложение готово', a.nextAction.href);
    }
  }
  private schedule(a: Application, afterRfi = false) {
    if (this.autoProgress) {
      setTimeout(() => this.progress(a, afterRfi), 1300);
      setTimeout(() => this.progress(a, afterRfi), 3000);
    }
  }
  private version(req: Request, version: number) {
    if (req.headers.get('If-Match') !== `"${version}"`)
      this.fail(412, 'Данные изменились в другой сессии. Сопоставьте версии.');
  }
  async dispatch(req: Request): Promise<Response> {
    try {
      return await this.route(req);
    } catch (e) {
      if (e instanceof Failure)
        return Response.json(
          { message: e.message },
          {
            status: e.code,
            headers: e.code === 503 || e.code === 429 ? { 'Retry-After': '2' } : {},
          },
        );
      throw e;
    }
  }
  private async route(req: Request): Promise<Response> {
    const url = new URL(req.url),
      path = url.pathname,
      method = req.method;
    const respond = (data: unknown, status = 200) => Response.json(data, { status });
    if (path === '/api/access/demo-login' && method === 'POST') {
      const body = (await req.json()) as { name: string };
      if (!body.name?.trim()) this.fail(422, 'Введите имя');
      this.session = {
        actor: body.name,
        companyId: null,
        contextVersion: 1,
        csrfToken: id(),
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
        companies,
      };
      return respond(this.session);
    }
    if (!this.session || Date.parse(this.session.expiresAt) <= Date.now())
      this.fail(401, 'Войдите в демонстрационный кабинет');
    if (method !== 'GET' && req.headers.get('X-CSRF-Token') !== this.session.csrfToken)
      this.fail(403, 'Сессия изменилась. Обновите страницу.');
    if (path === '/api/session') return respond(this.session);
    if (path === '/api/access/logout') {
      this.session = null;
      return new Response(null, { status: 204 });
    }
    if (path === '/api/companies') return respond(companies);
    if (path === '/api/session/company') {
      const b = (await req.json()) as { companyId: string };
      if (!companies.some((c) => c.id === b.companyId)) this.fail(403, 'Компания недоступна');
      this.session.companyId = b.companyId;
      this.session.contextVersion++;
      return respond(this.session);
    }
    if (!this.session.companyId) this.fail(403, 'Выберите компанию');
    if (
      method !== 'GET' &&
      req.headers.get('X-Company-Context') !== String(this.session.contextVersion)
    )
      this.fail(409, 'Контекст компании изменился');
    if (path === '/api/sync')
      return respond({ complete: true, cursor: String(this.events.length) });
    if (path === '/api/needs') {
      if (method === 'PUT') this.need = (await req.json()) as Need;
      return respond(this.need);
    }
    if (path === '/api/products')
      return respond(
        products.map((p) => ({
          ...p,
          eligible:
            BigInt(url.searchParams.get('amount') ?? this.need.amount) <= BigInt(p.maxAmount) &&
            BigInt(url.searchParams.get('amount') ?? this.need.amount) >= BigInt(p.minAmount) &&
            Number(url.searchParams.get('months') ?? this.need.months) <= p.maxMonths,
        })),
      );
    if (path.startsWith('/api/products/')) {
      const p = products.find((p) => p.id === path.split('/').at(-1));
      if (!p) this.fail(404, 'Продукт не найден');
      return respond(p);
    }
    if (path === '/api/feed/events') return new Response(null, { status: 204 });
    if (path.startsWith('/api/operations/by-key/')) {
      const operation = [...this.operations.entries()].find(
        ([key, operation]) =>
          key.startsWith(JSON.stringify([this.session!.actor, this.session!.companyId])) &&
          operation.key === path.split('/').at(-1),
      )?.[1];
      if (!operation) return respond(null);
      const { body, ...dto } = operation;
      void body;
      return respond(dto);
    }
    if (path === '/api/operations')
      return respond(
        [...this.operations.entries()]
          .filter(([key]) =>
            key.startsWith(JSON.stringify([this.session!.actor, this.session!.companyId])),
          )
          .map(([, value]) => {
            const { body, ...rest } = value;
            void body;
            return rest;
          }),
      );
    const rawBody = method !== 'GET' && method !== 'HEAD' ? await req.clone().text() : '';
    const commandKey = req.headers.get('Idempotency-Key');
    const key = commandKey
      ? `${JSON.stringify([this.session.actor, this.session.companyId])}:${path}:${commandKey}`
      : null;
    if (commandKey && path.startsWith('/api/operations')) return respond(null);
    if (key) {
      const prior = this.operations.get(key);
      if (prior) {
        if (prior.body !== path + rawBody) this.fail(409, 'Повтор команды с другим телом запрещён');
        return respond(prior.result);
      }
    }
    const command = (result: unknown, resourceId: string) => {
      if (!key) this.fail(422, 'Нужен ключ команды');
      this.operations.set(key, {
        key: commandKey!,
        body: path + rawBody,
        resourceId,
        status: 'COMPLETED',
        result: structuredClone(result),
      });
      return respond(result);
    };
    if (path === '/api/applications') {
      if (method === 'GET')
        return respond(
          [...this.applications.values()].filter((a) => a.companyId === this.session!.companyId),
        );
      const b = JSON.parse(rawBody) as { productId: string; need: Need };
      const product = products.find((p) => p.id === b.productId);
      if (
        !product ||
        BigInt(b.need.amount) > BigInt(product.maxAmount) ||
        b.need.months > product.maxMonths
      )
        this.fail(422, 'Продукт не подходит для выбранной потребности');
      const a: Application = {
        id: id(),
        companyId: this.session.companyId,
        productId: b.productId,
        need: b.need,
        status: 'DRAFT',
        version: 1,
        financialVersion: 1,
        draft: initialDraft(companies.find((c) => c.id === this.session!.companyId)!),
        history: [],
        createdAt: now(),
        nextAction: null,
      };
      a.history = [{ id: id(), title: 'Черновик создан', at: now() }];
      a.nextAction = { label: 'Продолжить заявку', href: `/applications/${a.id}/company` };
      this.applications.set(a.id, a);
      this.emit('application', a.id);
      return command(a, a.id);
    }
    const match = path.match(/^\/api\/applications\/([^/]+)(.*)$/);
    if (match) {
      const a = this.app(match[1]),
        tail = match[2];
      if (!tail) {
        if (method === 'GET') return respond(a);
        if (a.status !== 'DRAFT')
          this.fail(409, 'Отправленная заявка недоступна для редактирования');
        if (this.scenario === 'network' && !this.faults.has('save')) {
          this.faults.add('save');
          this.fail(503, 'Демонстрационный сбой сети. Ввод сохранён в памяти вкладки.');
        }
        if (this.scenario === 'conflict' && !this.faults.has('save')) {
          this.faults.add('save');
          a.version++;
          this.fail(412, 'Демонстрационный конфликт версий');
        }
        this.version(req, a.version);
        const b = JSON.parse(rawBody) as { draft: Draft };
        if (JSON.stringify(a.draft.finance) !== JSON.stringify(b.draft.finance))
          a.financialVersion++;
        a.draft = b.draft;
        a.version++;
        this.emit('application', a.id);
        return respond(a);
      }
      if (tail === '/submit') {
        this.version(req, a.version);
        const b = JSON.parse(rawBody) as {
          financialVersion: number;
          financialSnapshot: Finance;
          documentReferences: { documentId: string; objectVersion: number }[];
        };
        if (
          JSON.stringify(b.financialSnapshot) !== JSON.stringify(financialSnapshot(a.draft.finance))
        )
          this.fail(422, 'Финансовый снимок не совпадает с подтверждёнными данными');
        const docs = [...this.documents.values()].filter((d) => d.applicationId === a.id);
        if (docs.some((d) => d.status === 'SCANNING' || d.status === 'QUARANTINE'))
          this.fail(422, 'Дождитесь проверки документов');
        if (JSON.stringify(b.documentReferences) !== JSON.stringify(documentReferences(docs)))
          this.fail(412, 'Версии документов изменились');
        if (a.status !== 'DRAFT') this.fail(409, 'Заявка уже отправлена');
        if (b.financialVersion !== a.financialVersion)
          this.fail(412, 'Финансовая версия изменилась');
        if (
          Object.keys(financeErrors(a.draft.finance)).length ||
          !Object.values(a.draft.confirmed).every(Boolean) ||
          !a.draft.consents
        )
          this.fail(422, 'Подтвердите финансовые показатели и согласия');
        this.bump(a, 'SUBMITTED', 'Заявка отправлена');
        this.schedule(a);
        return command(a, a.id);
      }
      if (tail === '/documents')
        return respond([...this.documents.values()].filter((d) => d.applicationId === a.id));
      if (tail === '/upload-intents') {
        const b = JSON.parse(rawBody) as { name: string; size: number; type: string };
        if (
          b.size > 10 * 1024 * 1024 ||
          !['application/pdf', 'image/png', 'image/jpeg', 'text/plain'].includes(b.type)
        )
          this.fail(422, 'PDF, PNG, JPG или TXT до 10 МБ');
        const documentId = id();
        this.documents.set(documentId, {
          id: documentId,
          applicationId: a.id,
          name: b.name,
          size: b.size,
          type: b.type,
          objectVersion: 1,
          status: 'QUARANTINE',
          ocrStatus: 'PENDING',
          canDownload: false,
        });
        return respond({
          url: `/api/uploads/${documentId}`,
          documentId,
          maxBytes: 10 * 1024 * 1024,
        });
      }
      if (tail === '/ocr-confirmations') {
        const b = JSON.parse(rawBody) as {
          documentId: string;
          objectVersion: number;
          extractionId: string;
          finance: Finance;
          confirmed: Draft['confirmed'];
        };
        this.version(req, a.financialVersion);
        const d = this.documents.get(b.documentId);
        if (
          !d ||
          d.applicationId !== a.id ||
          d.objectVersion !== b.objectVersion ||
          d.extractionId !== b.extractionId ||
          d.status !== 'CLEAN' ||
          d.ocrStatus !== 'READY'
        )
          this.fail(409, 'Источник распознавания изменился');
        if (
          !Object.values(b.confirmed).every(Boolean) ||
          Object.keys(financeErrors(b.finance)).length
        )
          this.fail(422, 'Проверьте и подтвердите все значения');
        a.draft.finance = b.finance;
        a.draft.confirmed = b.confirmed;
        a.financialVersion++;
        a.version++;
        return respond(a);
      }
      const rmatch = tail.match(/^\/information\/([^/]+)(\/respond)?$/);
      if (rmatch) {
        const r = this.information.get(rmatch[1]);
        if (!r || r.applicationId !== a.id) this.fail(404, 'Запрос не найден');
        if (method === 'GET') return respond(r);
        if (rmatch[2]) {
          this.version(req, r.requestVersion);
          const b = JSON.parse(rawBody) as InformationRequest & {
            documentReferences: { documentId: string; objectVersion: number }[];
          };
          if (
            b.documentReferences?.some((ref) => {
              const d = this.documents.get(ref.documentId);
              return (
                !d ||
                d.applicationId !== a.id ||
                d.objectVersion !== ref.objectVersion ||
                d.status !== 'CLEAN'
              );
            })
          )
            this.fail(412, 'Версия документа изменилась');
          if (r.documentRequired && !b.documentReferences?.length)
            this.fail(422, 'Прикрепите подтверждающий документ');
          if (
            b.requestVersion !== r.requestVersion ||
            b.requirementsVersion !== r.requirementsVersion ||
            b.draftVersion !== r.draftVersion ||
            b.financialVersion !== r.financialVersion
          )
            this.fail(412, 'Версии запроса изменились');
          if (a.status !== 'NEEDS_INFO' || !r.confirmed) this.fail(422, 'Подтвердите ответ');
          if (
            r.documentRequired &&
            ![...this.documents.values()].some(
              (d) => d.applicationId === a.id && d.status === 'CLEAN',
            )
          )
            this.fail(422, 'Прикрепите документ и дождитесь проверки');
          for (const field of r.editableFields) a.draft.finance[field] = r.finance[field];
          a.financialVersion++;
          this.bump(a, 'REVIEW', 'Ответ на уточнение принят');
          this.schedule(a, true);
          return command(a, a.id);
        }
        this.version(req, r.draftVersion);
        const b = JSON.parse(rawBody) as InformationRequest;
        if (
          b.requestVersion !== r.requestVersion ||
          b.requirementsVersion !== r.requirementsVersion ||
          b.financialVersion !== r.financialVersion
        )
          this.fail(412, 'Требования или финансовая версия изменились');
        for (const field of Object.keys(financeFields) as (keyof Finance)[])
          if (!r.editableFields.includes(field) && b.finance[field] !== r.finance[field])
            this.fail(422, 'Поле не запрашивалось банком');
        if (Object.keys(financeErrors(b.finance)).length)
          this.fail(422, 'Проверьте финансовые значения');
        r.finance = b.finance;
        r.confirmed = b.confirmed;
        r.draftVersion++;
        r.financialVersion++;
        return respond(r);
      }
    }
    if (path.startsWith('/api/uploads/')) {
      const d = this.documents.get(path.split('/').at(-1)!);
      if (!d) this.fail(404, 'Файл не найден');
      this.app(d.applicationId);
      const bytes = await req.arrayBuffer();
      if (bytes.byteLength > 10 * 1024 * 1024) this.fail(422, 'Файл слишком большой');
      this.fileContents.set(d.id, bytes);
      const unsafe =
        d.name.includes('unsafe') ||
        new TextDecoder().decode(bytes).includes('EICAR-STANDARD-ANTIVIRUS-TEST-FILE');
      d.status = 'SCANNING';
      this.emit('document', d.applicationId);
      setTimeout(() => {
        d.status = unsafe ? 'FAILED' : 'CLEAN';
        d.canDownload = d.status === 'CLEAN';
        d.ocrStatus = this.scenario === 'ocr-failed' || d.status === 'FAILED' ? 'FAILED' : 'READY';
        d.extractionId = id();
        d.values = { ...initialFinance, revenue: '12500000' };
        this.emit('document', d.applicationId);
      }, 1800);
      return new Response(null, { status: 204 });
    }
    if (path.startsWith('/api/documents/')) {
      const d = this.documents.get(path.split('/')[3]);
      if (!d) this.fail(404, 'Файл недоступен');
      this.app(d.applicationId);
      if (d.status !== 'CLEAN' || !d.canDownload) this.fail(403, 'Файл ещё не прошёл проверку');
      return new Response(this.fileContents.get(d.id) ?? 'Демонстрационный файл', {
        headers: { 'Content-Type': d.type, 'Content-Disposition': 'attachment' },
      });
    }
    const omatch = path.match(/^\/api\/offers\/([^/]+)(.*)$/);
    if (omatch) {
      const o = this.offers.get(omatch[1]);
      if (!o) this.fail(404, 'Предложение не найдено');
      const a = this.app(o.applicationId);
      if (method === 'GET') return respond(o);
      this.version(req, o.version);
      if (Date.parse(o.expiresAt) < Date.now()) this.fail(409, 'Срок действия предложения истёк');
      if (omatch[2] === '/accept' && o.status === 'AVAILABLE') {
        o.status = 'ACCEPTED';
        o.version++;
        this.bump(a, 'ACCEPTED', 'Условия приняты');
      } else if (omatch[2] === '/complete' && o.status === 'ACCEPTED') {
        o.status = 'COMPLETED';
        o.version++;
        this.bump(a, 'COMPLETED', 'Демонстрация, деньги не перечисляются');
      } else this.fail(409, 'Действие недоступно в текущем состоянии');
      this.emit('offer', o.id);
      return command(o, o.id);
    }
    if (path === '/api/inbox')
      return respond(
        this.notices.filter((n) => {
          const a = [...this.applications.values()].find((a) => n.text.includes(a.id.slice(0, 8)));
          return a?.companyId === this.session!.companyId;
        }),
      );
    if (path.startsWith('/api/inbox/')) {
      const n = this.notices.find((n) => n.id === path.split('/')[3]);
      if (n) n.read = true;
      return new Response(null, { status: 204 });
    }
    if (path.startsWith('/api/assistant/')) {
      const conversationKey =
        this.session.actor + ':' + this.session.companyId + ':' + path.split('/').at(-1);
      const history = this.conversations.get(conversationKey) ?? [];
      if (method === 'GET') return respond(history);
      const b = JSON.parse(rawBody) as { text: string };
      history.push({ id: id(), role: 'user', text: b.text });
      const personal = /одобр|скор|риск|ставк/i.test(b.text);
      const search = /ссылк|источник/i.test(b.text);
      const answer: AssistantMessage = {
        id: id(),
        role: 'assistant',
        state: personal ? 'INSUFFICIENT_EVIDENCE' : search ? 'SEARCH_ONLY' : 'ANSWER',
        text: personal
          ? 'Я не могу оценить вероятность одобрения или объяснить персональную риск-оценку. Решение и условия появятся в статусе заявки.'
          : search
            ? 'Генерация ответа недоступна для этого запроса. Вот разрешённые источники.'
            : 'Для отправки заявки проверьте сведения о компании, заполните восемь финансовых показателей и подтвердите согласия. Документы можно добавить на шаге «Документы». Если появится запрос уточнений, ответьте в той же заявке.',
        sources: personal
          ? []
          : [
              { title: 'Как заполнить заявку', href: '/help/application' },
              { title: 'Финансовые показатели', href: '/help/finance' },
            ],
      };
      history.push(answer);
      this.conversations.set(conversationKey, history);
      return respond(answer);
    }
    // Неподдерживаемый маршрут не подменяется успешной заглушкой.
    this.fail(404, 'Маршрут отсутствует во временном контракте');
  }
}
export const demoMoney = { fromKopecks, toKopecks };
