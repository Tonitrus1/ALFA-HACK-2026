import { beforeEach, expect, it, vi } from 'vitest';
import { api } from '../src/shared/api/client';
import { request } from '../src/shared/api/http';
import { allowedSource } from '../src/features/assistant/Assistant';

vi.mock('../src/shared/api/http', async (original) => ({
  ...await original<typeof import('../src/shared/api/http')>(), request: vi.fn(),
}));

beforeEach(() => vi.mocked(request).mockReset());

const demo = {
  title: 'Статус DOCUMENTS_REQUIRED', type: 'KNOWLEDGE', document_id: 'demo', version: 1,
  metadata: { source_type: 'SYNTHETIC', is_synthetic: true },
};

it('hides old answers based on demo documents when reopening a conversation', async () => {
  vi.mocked(request).mockResolvedValue({ messages: [{
    client_message_id: 'old', message: 'Какие документы?', response: {
      message_id: 'answer', status: 'ANSWER', answer: 'Условия вымышлены.', citations: [demo],
    },
  }] });
  const messages = await api.conversation('general');
  expect(messages[1].text).toBe('Ответ скрыт: источник больше недоступен.');
  expect(messages[1].sources).toEqual([]);
});

it('links public knowledge to the original site and preserves web sources', async () => {
  vi.mocked(request).mockResolvedValue({
    message_id: 'public', status: 'ANSWER', answer: 'Проверьте перечень документов.', citations: [
      { ...demo, title: 'Банк России', metadata: {
        source_type: 'PUBLIC_NOTE', is_synthetic: false, source_url: 'https://cbr.ru/develop/msp/',
      } },
      { type: 'WEB', title: 'Альфа-Банк', url: 'https://alfabank.ru/sme/' },
    ],
  });
  const answer = await api.ask('general', 'Документы', new AbortController().signal);
  expect(answer.sources).toEqual([
    { title: 'Банк России', href: 'https://cbr.ru/develop/msp/' },
    { title: 'Альфа-Банк', href: 'https://alfabank.ru/sme/' },
  ]);
  expect(answer.sources?.every(s => allowedSource(s.href))).toBe(true);
  expect(allowedSource('/assistant/general/sources/demo/1')).toBe(false);
  expect(allowedSource('https://cbr.ru.example.com/demo')).toBe(false);
});
