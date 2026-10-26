# API и интеграционные контракты

## Действующая спецификация

- [OpenAPI 3.1](api/openapi.json): реализованные клиентские операции текущего backend.
- [Route inventory](api/route-inventory.json): method/path и Java-controller для сверки.
- [Postman](api/potok.postman_collection.json), окружения [local](api/local.postman_environment.json) / [demo](api/demo.postman_environment.json).
- Внутренние AI API: [Risk](../../ml/openapi.json), [Feed v1](../../ml/feed/openapi.json), [Feed v2](../../ml/feed_v2/openapi.json), [OCR](../../ml/ocr/openapi.json), [assistant](../../ml/assistant/openapi.json).

Старая `docs/architecture/contracts/public.openapi.json` — проектный контракт и библиотека общих схем. Она содержит ещё не реализованные операции. Новая спецификация использует сверенные общие DTO, исправляет runtime-различия и включает только allowlist действующих клиентских routes. Публичный backend API имеет префикс `/api/v1`. Внутренний ML API не предназначен для прямого вызова из браузера.

## Авторизация и контекст

1. `POST /api/v1/auth/login`, JSON `login/password`, заголовок `Origin`, точно разрешённый серверной конфигурацией. Возвращает Session и устанавливает `credit_session` (HttpOnly, SameSite=Strict; Secure зависит от HTTPS-профиля).
2. Все дальнейшие запросы отправляют cookie. Из ответа сессии берутся `csrfToken`, `companyId` и `contextVersion`.
3. Для изменения отправляется `X-CSRF-Token`. Контроллеры большинства бизнес-ресурсов требуют `X-Company-Context: <contextVersion>`. Это числовая версия выбранной компании, не строковый companyId.
4. Если предусмотрен query `companyId`, он должен соответствовать выбранной компании и её membership. Угадывание чужого applicationId/documentId доступа не даёт.
5. После `POST /api/v1/session/company` нужно обновить локальные токены/версию. Выход: `POST /api/v1/session/logout`, затем cookie недействителен и на сервере.

Публичные демоаккаунты `company-a` и `company-b` не блокируются на 15 минут после неверных паролей. Правильный пароль принимается сразу, включая старую блокировку в БД; успешный вход очищает её. Другие учётные записи сохраняют блокировку после пяти ошибок. Gateway ограничивает частоту входа: 30 запросов/мин на сетевой адрес, burst 20. При превышении возвращает `429 AUTH_RATE_LIMITED`, `Retry-After: 2`; это короткое ограничение запросов, а не блокировка аккаунта. За одним прокси адрес может быть общим. Сервисные ключи не заменяют browser cookie. Backend отдельно передаёт ассистенту trusted identity и контекст компании.

## Операции по группам

| Группа | Реализованное поведение |
|---|---|
| Access / catalog | Вход, сессия/выход/выбор компании, список и карточка доступной компании, список продуктов |
| Applications | Создать, прочитать список/заявку, PATCH черновика, submit, чтение StatusView |
| Financial | GET/PUT формы, подтверждение восьми полей, финансовый контейнер ответа на RFI |
| RFI | Список запросов, GET/PATCH черновика ответа, подтверждение финансов и отправка ответа |
| Documents | Требования, upload-intent, потоковая загрузка, отмена незавершённого upload, список/карточка, extraction, download-intent и потоковое скачивание |
| Decisions / offers | Чтение решения/оферты, accept и demo complete |
| Operations | Чтение результата принятой фоновой команды |
| Feed | GET/PUT предпочтений, персональная и сохранённая лента, идемпотентный feedback |
| Assistant | POST/GET сообщений диалога и чтение разрешённого источника |

Отдельный endpoint автоматического применения всего OCR отсутствует: UI переносит выбранные поля и подтверждает финансовую форму. Не включены проектные consent/withdraw/SSE/operator routes. Наличие статуса CANCELLED или EXPIRED в enum не подтверждает наличие соответствующих команд API.

## Версии, деньги и команды

`Money = {"amountMinor": 50000000, "currency": "RUB"}` означает 500 000 ₽. Backend принимает целые копейки, а интерфейс показывает рубли. Нельзя отправлять в `amountMinor` строку с разделителями разрядов.

- GET заявки и финансов возвращает ETag вида `"v2"`. Для PATCH и финансового PUT/confirm нужен `If-Match` актуальной версии. У финансов это **containerVersion**, а не statementVersion.
- Для submit нужны согласованные `expectedVersion`, `financialStatementVersion`, `requirementsVersion` и ссылки на документы. В DEMO допустимы пустые списки необязательных документов/consentRecordIds.
- Создание и бизнес-команды используют `Idempotency-Key`. Повтор одного тела с тем же ключом в той же области не создаёт второго бизнес-эффекта. Повтор с иным телом конфликтует.
- Submit/RFI response возвращают `202 CommandReceipt` с `operationId`/`statusUrl`. Принятие команды не равно готовому решению. Следует опрашивать operation/status.
- Accept/complete требуют `If-Match` версии оферты и такое же число в `expectedVersion`. После accept перечитать новую версию либо использовать версию из ответа перед complete.
- У списка/ленты cursor непрозрачный. Изменение контекста/предпочтений может сделать прежний cursor недействительным; клиент начинает чтение заново.

## Файлы

Сначала создать upload-intent с именем, заявленным MIME, размером, requirementId и requirementsVersion. Далее PUT байтов в `uploadUrl` с `X-Upload-Grant` и исходным MIME. Ограничение 10 MiB, PDF/JPEG/PNG. Метаданные MIME не заменяют проверку содержимого/антивирус.

Скачивание: создать download-intent, затем GET его URL с `X-Download-Grant`, cookie и контекстом. Grant не помещается в query string. OCR читает CLEAN-версию через отдельный внутренний job content endpoint, а не через открытый URL.

## Внутренние document jobs

Префикс `/internal/v1/document-jobs`, не публикуется gateway. ServiceIdentityInterceptor проверяет служебный токен и роль.

| Метод / путь | Назначение |
|---|---|
| `POST /claim` | Получить SCAN/EXTRACT lease; при отсутствии работы 204 |
| `POST /{jobId}/renew` | Продлить аренду с workerId/generation/leaseToken |
| `POST /{jobId}/scan-result` | Роль file-scanner, verdict CLEAN/REJECTED/ERROR и точная objectVersion |
| `POST /{jobId}/extraction-result` | Роль document-ocr, READY/FAILED, проверенные поля/страницы и версия движка |
| `GET /{jobId}/content` | Роль document-ocr, X-Worker-Id/X-Lease-Generation/X-Lease-Token, точный CLEAN content |

Устаревшее поколение не может опубликовать результат для текущей версии. Аренда не является обещанием exactly-once вызова LLM.

## Ассистент и динамические JSON

Browser отправляет `{clientMessageId, text}` в backend. Backend связывает conversationId с текущими session/company, проксирует в standalone assistant и возвращает его JSON **без преобразования snake_case в camelCase**. POST response описан схемой `Assistant_ChatResponse`. GET history/source остаются динамическими JSON, как в исходном OpenAPI модуля; документация не изобретает отсутствующую строгую DTO.

Возможны успешный ответ с источниками, SEARCH_ONLY без генерации, явная ошибка зависимости или `409 ASSISTANT_BUSY`. Readiness и наличие модели не считаются доказательством качественного ответа. В сообщениях запрещены реальные данные клиентов на публичном демо.

## Ошибки

Формат безопасной ошибки: `{code, message, correlationId, fieldErrors?}`. Внутренние score/reason codes, токены и provider errors не должны утекать клиенту.

| HTTP | Пример |
|---|---|
| 400 | Неверная схема/заголовки, пустой PATCH, несовпадение версий в одной команде |
| 401 | Нет сессии / неверные credentials |
| 403 | CSRF / Origin / запрещённое действие |
| 404 | Нет доступного ресурса, включая чужой tenant |
| 409 | Неактуальная версия/контекст, конфликт ключа, busy assistant |
| 429 | AUTH_RATE_LIMITED на gateway, повторить через Retry-After; учётная запись не блокируется |
| 415 | Неподдерживаемый MIME |
| 422 | Неприемлемые бизнес-значения, например preferences |
| 503 | Недоступность обязательного сервиса |

Сбой Risk обрабатывается кредитной логикой как MANUAL; сбой Feed допускает RULES. Поэтому не всякий отказ внутренней зависимости превращается в HTTP 503 клиентского сценария.

## Работа с коллекцией

Импортировать коллекцию и одно окружение. Для local вписать пароль из `.local/cabinet-access.md`; окружение demo уже содержит разрешённый публичный пароль company-a. Для company-b заменить login/password/companyId согласованно.

Сначала запускать только папку основного сценария. Cookie jar Postman сохраняет сессию; test scripts подхватывают CSRF, contextVersion, ID и версии. В Collection Runner поставить задержку 1000 ms между запросами: статус REVIEW/SUBMITTED опрашивается до 60 раз. Для MANUAL/NEEDS_INFO/DECLINED основной runner останавливается, дальнейшие действия описаны в [сценариях](demo.md).

Папки ленты и ассистента запускаются отдельно после входа. Коллекция меняет синтетические данные; документы передаются отдельным бинарным запросом по OpenAPI. Для проверки повторов ключ и тело нужно намеренно сохранить: автоматический `{{$guid}}` предназначен для новой команды.
