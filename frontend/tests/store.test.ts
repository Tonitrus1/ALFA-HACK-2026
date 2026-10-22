import { describe, expect, it } from 'vitest';
import { submissionBody } from '../src/shared/lib/submission';
import { DemoStore } from '../src/mocks/store';
import type { Application, InformationRequest, Offer, Scenario } from '../src/shared/types/domain';
async function setup(scenario: Scenario = 'success') {
  const store = new DemoStore(scenario, false);
  const call = async (
    path: string,
    method = 'GET',
    body?: unknown,
    version?: number,
    key?: string,
  ) => {
    const s = store.session;
    return store.dispatch(
      new Request('http://test/api' + path, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(s
            ? { 'X-CSRF-Token': s.csrfToken, 'X-Company-Context': String(s.contextVersion) }
            : {}),
          ...(version !== undefined ? { 'If-Match': `"${version}"` } : {}),
          ...(key ? { 'Idempotency-Key': key } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      }),
    );
  };
  await call('/access/demo-login', 'POST', { name: 'Тест' });
  await call('/session/company', 'POST', { companyId: 'atelier' });
  const a = (await (
    await call(
      '/applications',
      'POST',
      { productId: 'working-capital', need: store.need },
      undefined,
      'create-1',
    )
  ).json()) as Application;
  return { store, call, a };
}
async function submit(scenario: Scenario = 'success') {
  const ctx = await setup(scenario);
  const { a, call } = ctx;
  for (const key of Object.keys(a.draft.confirmed) as (keyof typeof a.draft.confirmed)[])
    a.draft.confirmed[key] = true;
  a.draft.consents = true;
  const saved = (await (
    await call(`/applications/${a.id}`, 'PATCH', { draft: a.draft }, a.version)
  ).json()) as Application;
  expect(
    (
      await call(
        `/applications/${a.id}/submit`,
        'POST',
        submissionBody(saved, []),
        saved.version,
        'submit-1',
      )
    ).status,
  ).toBe(200);
  return { ...ctx, a: ctx.store.applications.get(a.id)! };
}
describe('согласованный демосценарий', () => {
  it('проходит до COMPLETED и повторяет команду с тем же результатом', async () => {
    const { store, call, a } = await submit();
    store.progress(a);
    store.progress(a);
    expect(a.status).toBe('OFFERED');
    const offer = store.offers.get(a.offerId!)!;
    const accepted = (await (
      await call(`/offers/${offer.id}/accept`, 'POST', { version: 1 }, 1, 'accept-1')
    ).json()) as Offer;
    expect(accepted.status).toBe('ACCEPTED');
    const replay = (await (
      await call(`/offers/${offer.id}/accept`, 'POST', { version: 1 }, 1, 'accept-1')
    ).json()) as Offer;
    expect(replay).toEqual(accepted);
    expect(
      (await call(`/offers/${offer.id}/accept`, 'POST', { version: 999 }, 1, 'accept-1')).status,
    ).toBe(409);
    await call(`/offers/${offer.id}/complete`, 'POST', { version: 2 }, 2, 'complete-1');
    expect(a.status).toBe('COMPLETED');
  });
  it('блокирует устаревшее сохранение без overwrite', async () => {
    const { call, a, store } = await setup();
    const result = await call(
      `/applications/${a.id}`,
      'PATCH',
      { draft: { ...a.draft, companyName: 'Ошибочная запись' } },
      0,
    );
    expect(result.status).toBe(412);
    expect(store.applications.get(a.id)?.draft.companyName).not.toBe('Ошибочная запись');
  });
  it('требует восемь подтверждений', async () => {
    const { call, a } = await setup();
    expect(
      (await call(`/applications/${a.id}/submit`, 'POST', submissionBody(a, []), 1, 'submit'))
        .status,
    ).toBe(422);
  });
  it.each([
    ['manual', 'MANUAL'],
    ['declined', 'DECLINED'],
  ] as const)('%s — самостоятельный исход', async (scenario, status) => {
    const { store, a } = await submit(scenario);
    store.progress(a);
    store.progress(a);
    expect(a.status).toBe(status);
  });
  it('RFI меняет только запрошенные поля, сохраняет версии и ту же заявку', async () => {
    const { store, call, a } = await submit('rfi');
    store.progress(a);
    store.progress(a);
    expect(a.status).toBe('NEEDS_INFORMATION');
    const r = structuredClone(store.information.get(a.requestId!)!);
    r.finance.ebit = '1';
    expect(
      (await call(`/applications/${a.id}/information/${r.id}`, 'PATCH', r, r.draftVersion)).status,
    ).toBe(422);
    r.finance.ebit = a.draft.finance.ebit;
    r.finance.revenue = '13000000';
    r.confirmed = true;
    const saved = (await (
      await call(`/applications/${a.id}/information/${r.id}`, 'PATCH', r, r.draftVersion)
    ).json()) as InformationRequest;
    expect(saved.draftVersion).toBe(2);
    expect(saved.financialVersion).toBe(r.financialVersion + 1);
    expect(
      (
        await call(
          `/applications/${a.id}/information/${r.id}/respond`,
          'POST',
          {
            ...saved,
            draftVersion: 1,
            documentReferences: [{ documentId: 'missing', objectVersion: 1 }],
          },
          1,
          'rfi-old',
        )
      ).status,
    ).toBe(412);
    store.documents.set('rfi-doc', {
      id: 'rfi-doc',
      applicationId: a.id,
      name: 'Demo.txt',
      type: 'text/plain',
      size: 10,
      objectVersion: 1,
      status: 'CLEAN',
      ocrStatus: 'FAILED',
      canDownload: true,
    });
    expect(
      (
        await call(
          `/applications/${a.id}/information/${r.id}/respond`,
          'POST',
          { ...saved, documentReferences: [{ documentId: 'rfi-doc', objectVersion: 1 }] },
          1,
          'rfi-response',
        )
      ).status,
    ).toBe(200);
    store.progress(a, true);
    expect(a.status).toBe('OFFERED');
    expect(store.applications.size).toBe(1);
  });
  it('нельзя получить заявку другой компании', async () => {
    const { call, a } = await setup();
    await call('/session/company', 'POST', { companyId: 'coffee' });
    expect((await call(`/applications/${a.id}`)).status).toBe(404);
  });
  it('не выдаёт документ в карантине', async () => {
    const { call, a, store } = await setup();
    store.documents.set('unsafe', {
      id: 'unsafe',
      applicationId: a.id,
      name: 'x.txt',
      type: 'text/plain',
      size: 1,
      objectVersion: 1,
      status: 'QUARANTINE',
      ocrStatus: 'PENDING',
      canDownload: false,
    });
    expect((await call('/documents/unsafe/content')).status).toBe(403);
  });
});
