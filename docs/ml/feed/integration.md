# Интеграция ленты с backend и frontend

Назначение: интеграция ленты с backend и frontend.

Статус реализации: отдельный локальный ML-сервис; публичный backend и frontend не поставляются. Статус проверки документации — в [verification.md](verification.md).

Актуальность: 22.10.2026. Исходный проверяемый снимок: `ml/feed-recommendations` / [`829c1c09bb24`](https://github.com/Tonitrus1/ALFA-HACK-2026/commit/829c1c09bb248f03d730f25526de3b11712370bd). Среда исторических runtime-проверок: macOS arm64, Python 3.12.13. При этой миграции сервисы повторно не запускались.

## Статус интеграции и ответственность сервисов

ML runtime, каталог, ranking/fallback и клиент-пример реализованы. Публичные endpoints, устойчивое хранилище пользователя, транзакционные exposures/cursors и интерфейс пока не поставляются. Reference helpers показывают семантику, а не заменяют backend. Скоринг — независимая ветка и процесс.

## Адреса, авторизация и идентификаторы

FEED — `http://127.0.0.1:8002`, заголовок `X-Service-Token`. Не Bearer. Backend создаёт requestId и exposureId, Idempotency-Key совпадает с requestId; каталог/набор IDs закреплены digest. Пользовательский контекст проверяет backend. Браузер не знает внутренний токен.

## Источники контрактов

[Public OpenAPI](../../architecture/contracts/public.openapi.json) — design 1.4.1; [internal OpenAPI](../../architecture/contracts/internal.openapi.json) — общая внутренняя граница; [runtime OpenAPI](../../../ml/feed/openapi.json) — фактическая служба FEED. Runtime поддерживает только FEED, не PRODUCT; `getSavedFeed` — обязанность публичного backend, не вызов ML. [Postman](../../architecture/contracts/requests.postman_collection.json) — шаблоны контракта, не прошедшая E2E-коллекция.

| Операция | Вход | Выход | Авторизация | Ошибки | Пример |
|---|---|---|---|---|---|
| POST /internal/v2/rankings | Типизированный профиль, candidates, exposure и digests | Перестановка exact candidates + explanations | X-Service-Token; Idempotency-Key=requestId | 403/409/422/503 | [запрос](../../../ml/feed/examples/purchase-cost.request.json), [ответ](../../../ml/feed/examples/purchase-cost.response.json) |
| GET /health | Без тела | ready, catalog и releaseId | X-Service-Token | 403/503 | [smoke](../../../reports/feed-http-smoke.json) |
| GET/PUT /api/v1/feed/preferences | Опрос в user/company | Профиль и preferencesVersion | Публичный backend; контекст/CSRF | По public OpenAPI; ещё не реализовано | [preferences](../../../ml/feed/examples/preferences.json) |
| GET /api/v1/feed | Компания и optional cursor | Порция до шести + exposure/cursor | Публичный backend; контекст | 409 FEED_SELECTION_EXPIRED и public errors | [feed](../../../ml/feed/examples/purchase-cost.feed.json) |
| GET /api/v1/feed/saved | Компания и optional saved cursor | SavedFeed, savedVersion | Публичный backend; контекст | 409 FEED_SAVED_EXPIRED | [saved](../../../ml/feed/examples/saved-cards.json) |
| POST /api/v1/recommendation-feedback | VIEW/CLICK/HELPFUL/NOT_INTERESTED и exposure | Принятие события backend | Публичный backend; контекст/CSRF | Конфликт clientEventId:409 | [feedback](../../../ml/feed/examples/feedback-helpful.json) |

## Последовательность вызовов

Backend аутентифицирует user/company, читает профиль и текущее состояние карточек, закрепляет каталог и создаёт exposure. Исключает скрытые/подтверждённые VIEW/issued, вызывает ranking для оставшегося множества, проверяет exact permutation и digests, транзакционно сохраняет до шести фактически выданных карточек и cursor. Возвращает frontend полный текст/SVG и userReaction. Отправка карточки сама по себе не создаёт VIEW.

## Запросы и ответы

Канонический источник: `docs/architecture/contracts/internal.openapi.json`, операция `POST /internal/v2/rankings`, ветка `scope=FEED`. Runtime-описание отдельного приложения: `ml/feed/openapi.json`. Разделение по внутренним процессам: FEED направляйте на 8002; Risk API — на 8001. PRODUCT эта служба не принимает.

Обязательны `requestId`, `scope`, `exposureId`, `candidateIds`, `candidateSetDigest`, `catalogVersion`, `catalogDigest`, `profile`. Заголовок `Idempotency-Key` равен `requestId`. Примеры запросов и фактических ответов — `ml/feed/examples/`.

`profile` содержит только:

| Поле | Значения |
| --- | --- |
| task | PURCHASE, CASH_GAP, EQUIPMENT, EXPANSION, EXPLORING |
| help | AMOUNT, OPTIONS, COST, APPLICATION |
| depth | BASICS, EXPLAINED, PRACTICAL |
| businessCategory | RETAIL, SERVICES, MANUFACTURING, WHOLESALE, HOSPITALITY, OTHER |
| applicationStage | DRAFT, SUBMITTED, NEEDS_INFORMATION, REVIEW, DECISION |

Все поля необязательны, допускают null. Иные поля и свободный текст запрещены. `profile={}` допустим и даёт вводный RULES. `applicationStage` приходит только от явно выбранной заявки; отсутствие выбора не заполняйте данными случайной или последней заявки. Backend отображает свои категории/стадии в этот список, не передавая причины решения. Неизвестное значение лучше пропустить.

`topicReactions` — словарь кодов тем из каталога в `{helpful: int>=0, notInterested: int>=0}`. Это агрегаты последней принятой реакции каждого пользователя на карточку в выбранной компании, а не сырые события и не суммы за все нажатия. Нет хранения/дедупликации событий в ML.

`candidateIds` — уникальный непустой список опубликованных карточек, уже разрешённых backend. Предел контракта 100, текущий каталог 36. Из списка заранее исключаются скрытые, подтверждённые просмотры и все уже выданные в текущей подборке ID. ML возвращает перестановку ровно этого списка и не скрывает/добавляет карточки самостоятельно. Если кандидатов нет, backend возвращает конец ленты без вызова ML.

Дайджесты: UTF-8 JSON без пробелов, `ensure_ascii=False`, сортировка ключей объектов, запрет NaN. `catalogDigest = SHA256` всего `catalog/cards.json` в таком каноническом представлении; `candidateSetDigest = SHA256` канонического JSON отсортированного массива ID. Совместимый пример реализации: `ml/feed/catalog.py`. Не хешируйте исходное форматирование файла.

`candidateTexts` необязателен для FEED: тексты читаются из каталога. Если коллегам удобен прежний формат, передайте полный набор `{itemId, text}`, где text равен `title + '\n' + text` из каталога. Отсутствующий ID, подменённый/устаревший текст или лишний элемент дают 409. PRODUCT сохраняет прежние обязательные поля и тексты.

Ответ возвращает `requestId`, неизменённый `exposureId`, `candidateSetDigest`, `catalogDigest`, `releaseId`, `mode`, `reasonCategory`, все `rankedIds` и `explanations` по каждому ID. Backend проверяет идентичность запроса/exposure/digest и точную перестановку. Не используйте результат при потере, дубле или чужом ID. `FeedClient` в `ml/feed/integration.py` показывает такую проверку.



[Клиент-пример](../../../ml/feed/integration.py), [полный каталог](../../../ml/feed/catalog/cards.json). Код client является примером, backend должен дополнить его долговечным состоянием и своим общим deadline.

## Ошибки, timeout, retry, идемпотентность и fallback

- 403: неправильный внутренний токен.
- 409: несовместимый каталог, digest, текст, неизвестная карточка или несовпадающий Idempotency-Key.
- 422: пустое/неполное тело, пустые/повторные кандидаты, недопустимые поля/значения.
- 503 с `fallbackAction=RULES`: нет модели, нарушена целостность комплекта или ошибка inference.

`GET /health` также требует токен и возвращает 503 до готовности модели. Все ответы содержат `Cache-Control: no-store`. Ошибка загрузки/работы E5 затрагивает только этот процесс. Для пустого профиля правила доступны и при отказе модели.

ML не хранит requestId, пользователей и результаты. Повтор одного и того же входа детерминирован. Запрет повторного использования requestId с другим содержимым и долговечная идемпотентность лежат на backend.

Повтор публичного cursor должен читать сохранённую порцию, а не повторять ранжирование и создавать новый exposure. Служба ML не хранит журнал requestId, поэтому заголовок Idempotency-Key — проверка идентичности вызова, не гарантия долговечного exactly-once. Backend отвечает за транзакционную дедупликацию/снимки и общий deadline. При timeout/503 применяются правила того же каталога; 403/409/422 нельзя маскировать успешным MODEL.

## Совместимость версий и digests

Каталог должен совпадать у backend и ML по version/digest; тексты/SVG публикуются из одной версии. При изменении опроса или каталога обычный cursor истекает. Saved cursor дополнительно связан с savedVersion. Ответ проверяется по requestId/scope/exposure/candidateSetDigest/catalogDigest и перестановке без потерь/дубликатов. [Runtime schemas](../../../ml/feed/schemas.py) и [тесты контрактов](../../../ml/feed/tests/test_contracts.py) — исполняемые примеры.

## Обязанности backend и frontend

Канонический публичный API: `docs/architecture/contracts/public.openapi.json`.

1. `GET/PUT /api/v1/feed/preferences` читает/заменяет три ответа для `(user, company)`. PUT допускает пропуск/null, пропущенные поля очищаются. Атомарно увеличивается preferencesVersion и начинается новая подборка. Авторизация компании, X-Company-Context и CSRF остаются правилами общего backend.
2. `GET /api/v1/feed` начинает подборку; `?cursor=...` возвращает очередную порцию до шести. Backend создаёт exposure до вызова ML, получает все rankedIds, берёт первые шесть и сохраняет фактически выданные ID/версии/порядок. Не записывает VIEW при отправке.
3. Backend публикует полный каталог и SVG из одной версии. `FeedCard` содержит contentId, version, title, text, topic, depth, illustration, reasonCategory, reason. Полный текст берётся из каталога; targetPath не обязателен. Обязательный userReaction содержит текущую HELPFUL/NOT_INTERESTED или null; backend заполняет его из состояния текущего пользователя/компании, не из ML. `feed_cards` показывает сборку. Обязательные действия заявки остаются отдельным nextAction.
4. Exposure принадлежит пользователю, компании и порции, имеет неизменяемый набор фактически выданных карточек. ID, которые ML ранжировал, но backend не показал, не разрешают feedback. Сначала атомарно сохраните порцию/exposure/issued, затем отправляйте ответ.
5. Cursor — непрозрачная ссылка на серверный снимок: user, company, selection, preferencesVersion, catalogVersion, номер порции. Чужой cursor не раскрывает данные. Старый после изменения опроса/каталога даёт 409 FEED_SELECTION_EXPIRED. Повтор возвращает тот же сохранённый exposure, порядок и следующий cursor без ранжирования. Согласованное исключение: актуально скрытые карточки исключаются без замены; порция может стать короче или пустой. Пример `replay_page`.
6. Для следующего нового cursor backend транзакционно резервирует порцию, повторно ранжирует только оставшихся кандидатов с актуальными реакциями. Уже выданные карточки не переставляются. Конкурентные запросы одного cursor должны получить один снимок; не создавайте два exposure. После конца — cards=[], hasMore=false, без nextCursor. UI показывает «Новых карточек пока нет», изменение интересов и просмотр полезного на той же главной.
7. `POST /api/v1/recommendation-feedback` сохраняет VIEW/CLICK/HELPFUL/NOT_INTERESTED через существующую операцию `recordRecommendationFeedback`. Проверяйте exposure и реально выданный itemId в этом user/company. Уникальность clientEventId — внутри этого контекста; точный повтор без эффекта, повтор ID с другим содержимым — 409.
8. HELPFUL и NOT_INTERESTED заменяют предыдущую реакцию карточки. Повтор того же действия с новым eventId не меняет агрегат. Порядок определяется принятием на сервере в транзакции, client occurredAt используется как аналитическая метка. HELPFUL снимает прежнее скрытие и сохраняет полезное; NOT_INTERESTED убирает из полезного и скрывает. UI убирает карточку сразу после принятия реакции. Переключение компании не переносит реакции/историю.
9. VIEW фиксируется, когда не менее 50% карточки видно непрерывно не менее 1000 мс. При потере видимости таймер обнуляется. Это технический сигнал видимости, не доказательство прочтения. HELPFUL/NOT_INTERESTED сами по себе не подменяются VIEW. Подтверждённые VIEW сохраняются между посещениями; issued без VIEW действует только в текущей подборке.
10. `FeedbackProjection` — проверяемый образец семантики для коллег, не production-хранилище. Перенос требует БД, транзакций, уникальных ограничений, серверного порядка событий, проверки прав и версий. Его не импортирует ML server.

### Чтение полезных карточек

`GET /api/v1/feed/saved?companyId=...&cursor=...` с обязательным `X-Company-Context` возвращает `SavedFeed`: cards (до шести), exposureId, catalogVersion, catalogDigest, savedVersion, hasMore и nextCursor только при продолжении. Публичный backend ещё должен реализовать эту операцию; ML endpoint для неё не требуется.

Возвращаются только опубликованные карточки с последней реакцией HELPFUL для текущего пользователя и выбранной компании. Каждая карточка содержит userReaction=HELPFUL. VIEW и выдача в обычной подборке не исключают сохранённое. Порядок: последнее действительное переключение в HELPFUL первым; при равенстве — contentId по возрастанию. Повтор HELPFUL с новым clientEventId не переносит карточку наверх.

savedVersion начинается с 0, меняется атомарно при изменении состава/порядка сохранений. VIEW/CLICK и повтор той же реакции версию не меняют. Cursor связан с user/company/catalogVersion/catalogDigest/savedVersion и сохранённым снимком страницы. При актуальных версиях повтор возвращает ту же страницу, exposure и следующий cursor. Изменение сохранений или каталога инвалидирует cursor: 409 FEED_SAVED_EXPIRED; UI перечитывает первую порцию. Чужой cursor не раскрывает данные. Пустой список: cards=[], hasMore=false, без nextCursor.

Перед отправкой backend сохраняет отдельный exposure с фактически выданными карточками, чтобы существующий POST recommendation-feedback мог проверить реакции из полезного. Это не создаёт VIEW и не пополняет issued обычной ленты. Для сохранённой карточки reasonCategory=SAVED_HELPFUL и reason=«Вы отметили этот материал как полезный.»; это не объяснение модели. NOT_INTERESTED удаляет карточку из полезного и инвалидирует прежние cursor.

Для обычной ленты replay сохраняет контент, порядок, exposure и nextCursor, исключает актуально скрытое без замены и обновляет userReaction. Для saved изменение состава/порядка инвалидирует saved cursor. Это разные режимы; не смешивайте их состояния.

## Сквозные сценарии приёмки

Пропуск каждого вопроса, разные профили, изменение опроса/истечение cursor; последовательные шестёрки и конец; replay с тем же exposure; скрытие и смена реакций; дубли/конфликт eventId; VIEW только при 50% видимости непрерывно 1000 мс; чтение полезного; изоляция компаний/пользователей; отсутствие выбранной заявки; ML error → RULES. Проверить совместно с реальными backend/frontend. Эта E2E-приёмка пока не выполнена. [Verification](verification.md).
