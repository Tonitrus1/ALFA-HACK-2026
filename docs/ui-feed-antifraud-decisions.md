# Интеграция UI / Feed / synthetic fraud: решения до реализации

База: 5b937b5b3e6761545a6f368ec134d2817d7b1ad7. Ветка integration/ui-feed-antifraud-mvp.
AGENTS.md в checkout и родителях не обнаружен. Исходный checkout чист; frontend-источник копируется, не изменяется. Подтверждён Linux CI базы 39828525325; новая версия требует собственной приёмки.

## Экраны и фактический HTTP

| Экран / действие | Provisional UI | Реальный API / решение | Ошибки и версии |
|---|---|---|---|
| Вход | /api/access/demo-login, свободное имя | GET /demo/api/v1/accounts, POST /demo/api/v1/session с accountId | 403 Origin, 404 account; cookie HttpOnly, CSRF в памяти |
| Сессия / компания | /api/session, встроенные companies | /api/v1/session + /api/v1/companies (items, cursor), POST /api/v1/session/company | contextVersion и новый CSRF, 409 при смене из другой вкладки |
| Выход | несуществующий POST | Минимальный backend logout, отзыв серверной сессии | Нельзя реализовать безопасный logout удалением локального состояния |
| Потребность | /api/needs | Временный ввод до создания заявки, явно не серверное сохранение | Отдельного business-объекта need нет; после создания владеет application |
| Продукты | /api/products/:id и eligibility | /api/v1/products?companyId; выбор из серверного списка, eligibility подтверждает backend при create/submit | Никакого ML подбора кредитов, ставки не выдумываются |
| Черновик компании | произвольные companyName/address | Название и ИНН read-only; PATCH application.terms.business (activityDescription, businessAgeMonths) | If-Match "vN", 412; возраст не выводится из финансов |
| Финансы | totalDebt, строки рублей | totalLiabilities = все обязательства, отдельная форма /financial-statement | BigInt → safe integer копейки; пустое поле отсутствует, подписанные equity/profit/EBIT |
| Подтверждение / отправка | один фиктивный submit | PUT financial-statement → POST confirm → POST submit | Разные containerVersion/statementVersion; стабильный ключ каждой команды; не повторять PATCH с новой версией молча |
| Документы | упрощённые upload/content | document-requirements → documents/upload-intents → files/uploads; download-intents → files/downloads | Точные documentVersion/objectVersion, grants только заголовки; CLEAN gate |
| Статус | локальная state machine | GET application/status; сохраняем реальные статусы, серверный nextAction переводим в UI route | MANUAL отдельно от DECLINED; score/внутренние причины не показываются |
| RFI | /information/:id | /information-requests/:id/draft/financial-statement и /responses | Только запрошенные поля, requestVersion/requirementsVersion/draftVersion/statementVersion |
| Предложение | /api/offers | /api/v1/offers; пользователь выбрал добавить accept/complete в backend | Новое бизнес-состояние и CAS/идемпотентность принадлежат backend |
| Лента / полезное | статические статьи, случайный exposure | /api/v1/feed, /saved, /preferences, /recommendation-feedback | Серверный exposure, одинаковые eventId/key/time при повторах; VIEW 50% непрерывно 1000мс, только видимая вкладка |
| Inbox / ассистент / OCR | mock успешных ответов | Явная недоступность необязательных функций; RFI/история на экране заявки | Никаких фиктивных 200, OCR не нужен ручному обязательному сценарию; пользователь подтвердил, что чат и OCR будут подключены позже |
| SSE / операции | несуществующие sync/by-key | Poll реальных read endpoints; /api/v1/operations/:id по receipt | Не выдавать отсутствие операции за успешную команду |

## Feed релизы

Сохраняем E5/catalog v1; выборочный импорт ML-кода 87af049 в отдельный namespace, каталог v2 (72 карточки). E5 v2 и экспериментальный E5→CatBoost выбираются конфигурацией; автоматической promotion CatBoost нет. Runtime без загрузок/обучения. Проверка точной перестановки, catalog/candidate digests обязательна. Смена каталога инвалидирует старые cursor 409; сохранённый response никогда не пересобирается из нового контента. Rollback возвращает прежний каталог/модель поверх той же БД.

Агрегаты backend: последняя HELPFUL/NOT_INTERESTED по actor/company/card, сумма по темам. Это не CTR и не impression counts. Новому feature builder передаём только поддерживаемую семантику; симуляция не доказывает пользу реальным пользователям.

## Synthetic fraud и таблица решений

Пользователь выбрал серверные неизменяемые синтетические reference. Они независимы от пользовательской формы; источник SYNTHETIC_DEMO, фиксированное время доступности, версия, digest, компания и период. Нельзя создавать reference из preliminaryAnnualRevenue или копировать заявление.

| Условие | demo-policy-v1 | Согласованное расширение |
|---|---|---|
| Неполные данные / противоречие предварительной выручки | RFI до модели | Сохранить |
| Eligibility / нулевая выручка / отрицательный капитал / высокая долговая нагрузка | Действующий ранний исход | Сохранить порядок; policy synthetic-dual-policy-4 не переносится |
| Нужен inference, Risk отсутствует | MANUAL | Сохранить |
| Fraud включён как обязательный, reference/model/result отсутствует или не совпала identity | Не было fraud | MANUAL до предложения, отсутствие не равно нулю |
| Fraud высокий | Не было fraud | MANUAL; никогда самостоятельный DECLINED |
| Risk/Fraud совместимы, Fraud ниже порога | cap-first, затем Risk >= .5 → MANUAL | Прежняя Java policy; score не усредняются |
| Fraud отключён | Обычный Risk | Точный исход demo-policy-v1 |

Оба inference закрепляются за одной компанией/заявкой/попыткой/финансовым снимком; snapshot/release/provenance неизменяемы; общий deadline и CAS не допускают поздний результат. Миграции только новые номера; V2__bridge не изменяется. Исследовательское ограничение: recall=0 на отдельном невиданном семействе. Это SYNTHETIC_MANIPULATION_PROXY, не банковский антифрод.

## Обоснование backend изменений

1. Logout: отзыв HttpOnly сессии и полномочий требует сервера.
2. Accept/complete: пользователь явно запросил добавление; долговечное состояние предложения/дела, CAS и повторяемость нельзя доверить браузеру или ML.
3. Выбор версионированного каталога/immutable выдачи: контент ленты и курсоры являются долговечным бизнес-состоянием, ML возвращает только перестановку.
4. Synthetic reference и привязка review attempt: доверенное происхождение и неизменяемость обеспечивает backend; вычисление fraud остаётся ML.
5. Допуск fraud результата к решению: бизнес-политика принадлежит Java, ML не может подменять Risk score или outcome.
6. Допустимый Origin gateway: точный allowlist demo login дополняется адресами поставленного gateway; cookie/CSRF не обходятся.

## Проверка нового Feed до включения

Локально воспроизведён pipeline на 500 синтетических контекстах (fixed seeds из исходного commit): E5, CatBoost, Rules, стресс position/intent. Все promotion gates CatBoost false, включая humanReview; default остаётся E5. Это инженерный smoke размера, не повтор полного исторического исследования на 5000 контекстах и не пользовательский эксперимент. Linux выполняет свой pipeline из тех же исходников; артефакты macOS на Linux не переносятся как доказательство parity.
