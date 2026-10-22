# Временный API-контракт provisional-v1

**Это предложение для согласования, а не документация существующего backend.** Исходные `contracts/public.openapi.json`, `contracts/state-machine.json`, runtime policy и technology adapters из GitHub недоступны. Типы вручную находятся в `src/shared/types/domain.ts`, клиент — в `src/shared/api/client.ts`, мок той же модели — в `src/mocks/store.ts`.

## Транспорт и контекст

Один origin, пути `/api/*`. JSON-запросы с `credentials: include`. Сервер управляет cookie HttpOnly/SameSite, компаниями и правами. Frontend получает Session `{ actor, companyId, contextVersion, csrfToken, expiresAt, companies }` и держит токен только в памяти. Мутации передают `X-CSRF-Token` и `X-Company-Context`. `If-Match: "<version>"` используется для CAS; значимые POST-команды дополнительно имеют `Idempotency-Key`.

Ошибка: `{ message: string, fields?: Record<string,string> }`. Ожидаются 401, 403, 404, 409, 412, 422, 429, 503. Retry-After поддерживает секунды и HTTP-date. Не-JSON и файловые ошибки превращаются в безопасный общий текст. Доступность cookie и CSRF не может обеспечиваться самим SPA.

## Маршруты

| Метод     | Временный путь                                         | Назначение / версия                                                                |
| --------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| POST      | `/api/access/demo-login`                               | Только демонстрационный вход `{name}`; production IAM согласовать отдельно         |
| POST      | `/api/access/logout`                                   | Завершение сессии                                                                  |
| GET       | `/api/session`                                         | Сессия, контекст и разрешённые компании                                            |
| GET       | `/api/companies`                                       | Разрешённые компании                                                               |
| POST      | `/api/session/company`                                 | Выбор серверного контекста `{companyId}`                                           |
| GET/PUT   | `/api/needs`                                           | Потребность текущей компании                                                       |
| GET       | `/api/products?amount=&months=`                        | Продукты и серверная пригодность                                                   |
| GET       | `/api/products/:id`                                    | Детали синтетического продукта                                                     |
| GET/POST  | `/api/applications`                                    | Заявки компании / идемпотентное создание                                           |
| GET/PATCH | `/api/applications/:id`                                | Чтение / сохранение DRAFT, application.version                                     |
| POST      | `/api/applications/:id/submit`                         | Версия заявки, финансовый снимок и documentReferences                              |
| GET       | `/api/applications/:id/documents`                      | Точные версии файлов и разрешения                                                  |
| POST      | `/api/applications/:id/upload-intents`                 | `{name,size,type}` → `{url,documentId,maxBytes}`                                   |
| PUT       | `/api/uploads/:id`                                     | Ограниченная бинарная загрузка на том же origin                                    |
| GET       | `/api/documents/:id/content`                           | Только CLEAN и canDownload                                                         |
| POST      | `/api/applications/:id/ocr-confirmations`              | financialVersion + objectVersion/extractionId и 8 подтверждений                    |
| GET/PATCH | `/api/applications/:id/information/:requestId`         | Чтение / сохранение draftVersion ответа                                            |
| POST      | `/api/applications/:id/information/:requestId/respond` | requestVersion + requirementsVersion + draftVersion + financialVersion + документы |
| GET       | `/api/offers/:id`                                      | Условия, срок, версия и статус                                                     |
| POST      | `/api/offers/:id/accept`                               | Идемпотентное принятие offer.version                                               |
| POST      | `/api/offers/:id/complete`                             | Демонстрационное оформление offer.version                                          |
| GET       | `/api/inbox`                                           | Сообщения текущей компании                                                         |
| POST      | `/api/inbox/:id/read`                                  | Отметить прочитанным                                                               |
| GET/POST  | `/api/assistant/:conversationId`                       | История / вопрос, timeout 65 с, AbortSignal                                        |
| POST      | `/api/feed/events`                                     | clientEventId, exposureId, itemId, VIEW/CLICK                                      |
| GET       | `/api/events`                                          | text/event-stream, Last-Event-ID, heartbeat                                        |
| GET       | `/api/sync?page=`                                      | barrier snapshot `{complete,cursor,nextPage?}`                                     |
| GET       | `/api/operations?windowDays=7`                         | Активные и завершённые операции текущей компании                                   |
| GET       | `/api/operations/by-key/:key`                          | Сверка результата команды после timeout                                            |

Типы DTO перечислены в domain.ts. Временные версии независимы: Application.version, financialVersion, requestVersion, requirementsVersion, draftVersion, objectVersion и Offer.version. Их нельзя заменять timestamp.

## Денежные значения

Потребность и предложение передают сумму строкой копеек. Черновик сохраняет **сырой ввод в рублях строками**, включая незавершённый ввод. При отправке создаётся отдельный подтверждённый `financialSnapshot` из восьми строк копеек через BigInt; пустое значение не становится нулём. Поля: revenue, netProfit, ebit, equity, totalAssets, currentAssets, currentLiabilities, totalDebt. **Названия временные: заменить реальными, когда будет OpenAPI.** Отрицательные netProfit/ebit/equity допустимы. Период — выбранный год, RUB, единицы RUB.

Документы отправляются точными `{documentId,objectVersion}`. QUARANTINE/SCANNING останавливают отправку. FAILED не попадает в снимок. CLEAN и OCR READY — независимые состояния. Подтверждение OCR включает extractionId и objectVersion, клиент явно сверяет все восемь значений.

## Демонстрационные переходы

Временная таблица `src/shared/lib/stateMachine.ts`:

`DRAFT → SUBMITTED → PROCESSING → OFFERED → ACCEPTED → COMPLETED`

Альтернативы из PROCESSING: MANUAL, DECLINED, NEEDS_INFORMATION. Ответ на RFI: NEEDS_INFORMATION → PROCESSING. В mock исходы задаёт сценарий, ML ничего не решает. MANUAL не равен DECLINED. Финал содержит «Демонстрация, деньги не перечисляются».

## Что запросить у backend-команды

1. Исходные OpenAPI, state-machine, runtime-policy, technology-adapters и версии контрактов. После получения сгенерировать типы/клиент и заменить provisional-v1.
2. Реальные восемь полей, единицы/периоды/nullable, финансовое подтверждение и CAS финансовых версий.
3. Cookie login и demo-login в отдельных контрактах, CSRF, company context, срок сессии, ошибки полномочий.
4. Статусы, authoritative nextAction, eligibility, формат пагинации всех списков.
5. Upload intent, лимиты, AV fail closed, objectVersion, OCR extraction/source/pages, разрешения на скачивание.
6. Поля/документы RFI и атомарные правила requestVersion/requirementsVersion/draftVersion/financialVersion.
7. SSE journal, retention курсора, barrier snapshot, gap/410, complete/nextPage и event envelopes.
8. Operation lookup/list, dedup 7 дней, replay до проверки состояния, 202/polling, неопределённый результат.
9. RAG DTO, разрешённые источники, отозванная история и CPU budget; реальные условия предложений и команды оформления.

## Подключение

Согласуйте временную модель либо замените adapter после генерации из реального контракта. Создайте `.env` с `VITE_API_MODE=integrated` и `VITE_CONTRACT_ACK=provisional-v1`. Флаг — явное подтверждение разработчика, что согласована именно эта временная модель; он не заменяет интеграционные испытания. MSW не запускается, запросы идут на тот же origin. Для локального backend укажите `BACKEND_ORIGIN=http://127.0.0.1:8080` до старта Vite. Для production используйте reverse proxy с SPA fallback на index.html и streaming `/api/events` без буферизации. Не помещайте секреты в VITE_*.

Integrated CPU-профиль, настоящие cookie/AV/OCR/RAG, долговечность и банковские операции в этой работе не проверены. Внешнюю приёмку по руководству проводить только после этих проверок.
