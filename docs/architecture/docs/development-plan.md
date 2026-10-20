# План параллельной разработки

## 1. Честная оценка объёма

27 задач:25 MVP, 1 дополнительная интеграционная задача и 1 отдельная задача bank-target. Оценки - человеко-часы активной работы, не календарное обещание. Текущий итог формируется из tasks.json в конце документа. Первоначальные подробные планы сохранены в архиве; новый граф группирует их по проверяемым результатам.

Для расчёта capacity используем 10 эффективных рабочих часов на участника в день, включая локальную отладку и review. Три участника:48 ч→60 человеко-часов,72 ч→90; пять:48 ч→100,72 ч→150. Недостаток capacity не устраняется названием роли. Дополнительно нужен резерв 25% к базовой оценке. Ни один вариант не считается гарантией при неизвестной подготовке команды.

Рекомендация:5 человек/72 часа и готовые навыки Java/React/Python. 3 человека/48 часов не соответствуют согласованному полному ML-объёму. Для 3/72 и 5/48 есть высокий риск. Не сокращать ML молча: на checkpoint оформить фактическое отставание и согласовать срок либо неполную готовность. Честный частичный показ не равен завершённому согласованному MVP.

## 2. Независимые направления

После P01 frontend работает по MSW/примеру контракта; ML - по synthetic fixtures; backend - с контрактными doubles ML; integration собирает profile и release bundle. Стабилизация порта не требует ждать реальных обученных весов. Общие данные/DTO/состояния не придумываются в feature-ветках.

BACKEND: P03→P05→P08/P10→P15. FRONTEND: P04→P06→P09→P16. ML: P11/P12/P13/P14 после P02, порядок при одном специалисте: risk baseline, рекомендации, OCR, RAG. INTEGRATION: P01/P02, P07, ранние skeleton clients, P17/P21/P23 и P26; backend выполняет P25. P27 - отдельное необязательное подключение настоящих сервисов. QA_DEMO пишет сценарии с начала, формальная независимая приёмка P18-P20 после P17.

Для 3 участников backend совмещает integration, frontend - QA_DEMO; эти роли увеличивают занятость, а не дают дополнительную параллельность. Риск перегрузки ML один и при 3, и при 5 участниках: функции последовательно требуют около 30 часов активной работы плюс интеграция. Помощь integration с model packaging/KB ускоряет без разделения бизнес-владельца.

## 3. Контрольные точки

- **0-2 ч:** P01; единые API/ID, состояния, роли/владельцы, synthetic наборы и стенд.
- **До 12 ч:** вертикальный срез P07 с настоящей DB/сессией/сохранением и обозначенными model doubles. В seed уже подтверждённая demo-форма; новый обход confirm API не создаётся.
- **До 24 ч:** financial/RFI API, подготовленные CPU images/models, безопасный файл/job pipeline, интерфейсы подключения моделей.
- **До 36 ч:** стремиться к P17 и 4 реальным ML-функциям. Это целевая контрольная точка, не вывод из оценки, что все работы точно завершатся. При отставании - пересчитать остаток; прежде всего отложить P27 и дополнительную вёрстку, сохранив локальные адаптеры и весь именованный стек.
- **Для 48 ч:** freeze36 ч; оставшиеся 12 ч на проверку/сдачу. Если 4 ML-функции не работают, фиксировать неполноту; не переименовывать mock в model.
- **Для 72 ч:** freeze60 ч, регрессия/чистый запуск/репетиция до 68 ч, резерв на версию/доступ/непредвиденное до 72 ч.

Критический путь зависимостей рассчитывается автоматически. Он является нижней оценкой при неограниченном числе участников. Дополнительная ресурсная нижняя оценка учитывает последовательную работу всех ML-задач одним ML-специалистом. Реальное расписание должно учитывать сон/смены/переключения и ролевые совмещения.

## 4. Порядок снижения риска

Первым отложить настоящее подключение сервисов P27, registry UI/canary dashboards, расширенные типы документов, дообучение LLM и поведенческий ranker. Feast/Airflow/Qdrant/Redis и остальные технологии сохраняются в архитектуре, интерфейсах, каркасах и конфигурации даже при локальных привязках. Их SDK-реализации не выдаются за выполненные. Затем сократить polish, dashboard и дополнительные сценарии beyond acceptance. Для RAG оставить небольшой corpus и малую выбранную модель; для OCR - только одну форму; для риска - один baseline без model zoo.

Отказ отдельной модели обрабатывается безопасным fallback, но согласованный готовый MVP требует отдельного успешного прогона всех 4 ML-функций. Резервный SEARCH_ONLY не заменяет RAG-generation в критерии готовности. Корректность tenant isolation, persisted snapshot и защиты повторов не отключается ради показа.

## 5. Definition of Done

Задача закрыта только при наличии указанных deliverable и doneWhen из tasks.json, PR review и профильных проверок. Общий MVP закрыт после P23, всех обязательных acceptance кроме TARGET_ONLY и проверок отключённых реальных провайдеров (для них NOT_EXECUTED), чистого запуска вторым участником и реальных model manifests. Существование этих требований не означает их выполнения в архитектурной работе.

## 6. Дополнительная интеграция

P25/P26 добавляют 9 человеко-часов к обязательному MVP; P11/P14 реализуют ML-порты в рамках своих оценок. P27 оценивается отдельно в 8 часов и подключает настоящие Redis-cache/Qdrant/MLflow при наличии времени и ресурсов. Реализация остальных полноценных сервисов в эти 8 часов не входит. Это оптимистичная оценка при знакомом стеке; при недостатке capacity сохраняются локальные реализации и честный статус архитектурных каркасов.

[Mapping, интерфейсы и критерии переключения](../docs/technology-adapters.md).

## 7. Реестр задач

### P01. Зафиксировать контракт и распределить модули

Владелец: INTEGRATION; оценка: 2 ч; зависимости: нет; профиль: mvp.

Результат: contracts + task ownership; technology ports + provider DTO semantics.

Готово, когда: 60 public ops typed; all schema refs resolve.

### P02. Закрепить платформу, модели и лицензии

Владелец: INTEGRATION; оценка: 3 ч; зависимости: P01; профиль: mvp.

Результат: dependency/model locks + notices.

Готово, когда: exact versions/digests/licenses; CPU images boot; Java BOM smoke.

### P03. Данные, миграции, сессия и права

Владелец: BACKEND; оценка: 3 ч; зависимости: P01; профиль: mvp.

Результат: PostgreSQL migrations + seed accounts.

Готово, когда: A/B tenant access denied; migrations twice safe.

### P04. Основа web и контрактные заглушки

Владелец: FRONTEND; оценка: 3 ч; зависимости: P01; профиль: mvp.

Результат: React routes + generated types + MSW.

Готово, когда: build; 3 products; no secrets in browser.

### P05. Вертикальный срез create/save/submit/status

Владелец: BACKEND; оценка: 3 ч; зависимости: P03; профиль: mvp.

Результат: persistent core API + simulator event.

Готово, когда: restart keeps draft; submit receipt dedup.

### P06. Web-путь первой заявки

Владелец: FRONTEND; оценка: 3 ч; зависимости: P04; профиль: mvp.

Результат: login/catalog/form/status.

Готово, когда: same UI works mock and server; next action visible.

### P07. Docker, healthchecks и первый общий smoke

Владелец: INTEGRATION; оценка: 1 ч; зависимости: P02, P05, P06; профиль: mvp.

Результат: CPU Compose + health order + smoke.

Готово, когда: fresh start end-to-end by hour 12 for 5-role team; six mandatory containers, explicit local bindings.

### P08. Финансовая форма и неизменяемые снимки

Владелец: BACKEND; оценка: 5 ч; зависимости: P05; профиль: mvp.

Результат: financial read/save/confirm + package refs.

Готово, когда: all 8; CAS; modified values invalidate confirmation.

### P09. Финансовый UI и запрос уточнений

Владелец: FRONTEND; оценка: 5 ч; зависимости: P06; профиль: mvp.

Результат: U08/U12 financial + RFI screens.

Готово, когда: no overwriting dirty input; unrequested values unchanged.

### P10. Документы, quarantine, AV и аренда

Владелец: BACKEND; оценка: 6 ч; зависимости: P05; профиль: mvp.

Результат: streamed upload + scanner + job lease.

Готово, когда: infected/error not CLEAN; limit 10MiB/5 pages; stale lease rejected.

### P11. Локальная risk-модель и feature transforms

Владелец: ML; оценка: 10 ч; зависимости: P02; профиль: mvp.

Результат: trained logistic baseline + manifests; SnapshotFeatureRepositoryAdapter (Feast boundary).

Готово, когда: 8 ratios; grouped split; score BANKRUPTCY_PROXY; no PD claim.

### P12. Semantic recommendations на E5

Владелец: ML; оценка: 5 ч; зависимости: P02; профиль: mvp.

Результат: CPU embeddings + catalog ranking.

Готово, когда: PRODUCT/FEED eligible permutations; no trained click-model claim.

### P13. OCR одной синтетической формы

Владелец: ML; оценка: 5 ч; зависимости: P02; профиль: mvp.

Результат: Tesseract rus+eng + fixed-layout parser.

Готово, когда: 8 fields with signs/units/pages; manual confirm; no silent repair.

### P14. RAG на опубликованном корпусе

Владелец: ML; оценка: 10 ч; зависимости: P02; профиль: mvp.

Результат: E5 retrieval + local Qwen generation; NumpyVectorIndexAdapter + LlamaCppGenerationAdapter (Qdrant/vLLM boundaries).

Готово, когда: sources subset; no source => refusal; generation timeout => SEARCH_ONLY.

### P15. Backend-адаптеры ML, RFI и решений

Владелец: BACKEND; оценка: 6 ч; зависимости: P08; профиль: mvp.

Результат: risk/ranking/RAG clients + simulator policy.

Готово, когда: contract doubles usable before models; finance-only RFI; model outage=>MANUAL.

### P16. Лента, RAG-виджет, документы и предложение

Владелец: FRONTEND; оценка: 6 ч; зависимости: P09; профиль: mvp.

Результат: U03/U13/U15/U16 + feedback.

Готово, когда: ranking metadata; pinned next action; source links authorized.

### P17. Общая интеграция четырёх ML-функций

Владелец: INTEGRATION; оценка: 6 ч; зависимости: P10, P11, P12, P13, P14, P15, P16, P25, P26; профиль: mvp.

Результат: real ML in integrated CPU profile.

Готово, когда: no mock presented as model; GPU optional; health/degradation measured; all required bindings reported truthfully, no hidden double.

### P18. Security и отказные сценарии

Владелец: QA_DEMO; оценка: 5 ч; зависимости: P17; профиль: mvp.

Результат: negative E2E + failure evidence.

Готово, когда: cross-company, CSRF, malicious files, prompt injection, stale versions fail safely.

### P19. Восстановление, UX и ресурсы обычного ПК

Владелец: QA_DEMO; оценка: 4 ч; зависимости: P17; профиль: mvp.

Результат: restart test + keyboard test + resource report.

Готово, когда: draft/operation persistent; no mandatory external network; RAG measured CPU.

### P20. Независимая проверка чистого запуска

Владелец: QA_DEMO; оценка: 3 ч; зависимости: P18, P19; профиль: mvp.

Результат: launch report on clean machine.

Готово, когда: second person follows README without author help.

### P21. Документация, API collection и лицензии

Владелец: INTEGRATION; оценка: 4 ч; зависимости: P07; профиль: mvp.

Результат: README + notices + request collection; provider manifest and jury technology evidence table.

Готово, когда: all six jury criteria mapped to evidence.

### P22. Репетиция защиты и резервный показ

Владелец: QA_DEMO; оценка: 3 ч; зависимости: P17, P21; профиль: mvp.

Результат: 5-minute demo + local fallback + video.

Готово, когда: interactive scenario replay; simulated steps explicitly labelled.

### P23. Заморозка, регрессия и версия сдачи

Владелец: INTEGRATION; оценка: 2 ч; зависимости: P20, P22; профиль: mvp.

Результат: release manifest + immutable tag/hash.

Готово, когда: CI green; no edits after deadline version; private access checked; archive actual selected providers/evidence, not just architecture names.

### P24. Промышленная платформа и допуск

Владелец: INTEGRATION; оценка: 0 ч; зависимости: P23; профиль: bank-target.

Результат: bank-target roadmap, not hackathon implementation.

Готово, когда: all external gates independently closed.

### P25. Локальные адаптеры backend и выбор провайдеров

Владелец: BACKEND; оценка: 4 ч; зависимости: P03; профиль: mvp.

Результат: SessionStore/Cache/EventTransport/ObjectStore ports and composition root.

Готово, когда: durable sessions/outbox/files; bounded cache; unknown binding fails; no security fallback.

### P26. ML-платформа через локальные адаптеры и общий протокол проверки

Владелец: INTEGRATION; оценка: 5 ч; зависимости: P02; профиль: mvp.

Результат: manifest registry, offline job journal, quality report, metrics/evidence bindings; ML reviews interfaces.

Готово, когда: P11/P14 own feature/vector/generation implementations; local common-contract tests; no synthetic metrics or canned model answers.

### P27. Дополнительное подключение Redis, Qdrant и MLflow

Владелец: INTEGRATION; оценка: 8 ч; зависимости: P17; профиль: optional-integrations.

Результат: real SDK adapters and optional service profile with locks.

Готово, когда: same common tests + actual service failure tests + measured resource report; if omitted say SPECIFIED, not integrated.

Базовая оценка: **112 человеко-часа**; с резервом 25% - **140.0 человеко-часа**. P27 - ещё 8 часов отдельной необязательной интеграции; не включена в обязательную сумму. P24 - отдельный неоценённый промышленный этап.

