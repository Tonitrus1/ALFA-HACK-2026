# UI + versioned Feed + synthetic manipulation proxy

Рабочая ветка: `integration/ui-feed-antifraud-mvp`, база `5b937b5b3e6761545a6f368ec134d2817d7b1ad7`.
Решения и причины backend изменений: `ui-feed-antifraud-decisions.md`.

## Подготовка и запуск

Зависимости и E5 скачиваются только при подготовке. В serving нет обучения или скачивания. Для сборки нужен Docker Compose и сеть к реестрам; после подготовки runtime использует local artifacts и внутреннюю сеть. Не передавайте реальные документы или финансовые данные.

```sh
python3 scripts/integration/configure.py
docker compose build
mkdir -p .local/feed-bundle
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 -v "$PWD/.local/feed-bundle:/bundle" --entrypoint python credit-mvp-feed:local -m feed.prepare --bundle /bundle --download
docker build --target preparation -f deploy/Dockerfile.feed -t credit-mvp-feed-tools:local .
mkdir -p reports/preparation
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/.local:/releases" -v "$PWD/reports/preparation:/evidence" --entrypoint python credit-mvp-feed-tools:local -m feed_v2.pipeline --work /releases/feed-v2-linux --reports /evidence/feed-v2 --model-source /releases/feed-bundle/model --users 500 --skip-http
export FEED_RELEASE=v2 FEED_RANKER=e5 FEED_BUNDLE_PATH=./.local/feed-v2-linux/e5 FRAUD_MODE=synthetic
docker compose up -d --wait --wait-timeout 300
```

UI и публичный API: `http://127.0.0.1:8080`. Demo account выбирается из серверного списка. В Compose опубликован только gateway. Веса E5, код и frozen CatBoost bundles должны быть заранее доступны на стенде вместе с построенными образами. Для холодного запуска в полностью автономной среде перенесите Docker images через `docker save/load`, обе папки bundle и исходники; `docker compose up --no-build --pull never` с теми же переменными. Не переносите `.env` в отчёты или Git.

`500` — размер воспроизводимого инженерного smoke, не полный исходный эксперимент. Для полного протокола используйте новый work/reports и `--users 5000`. Каталог/разметка не прошли независимую человеческую проверку. CatBoost не допущен в default: gates локального smoke false. Исходники нового Feed: `ml/feed_v2`; v1 не заменён. Сравнение трёх подходов и stress position/intent создаёт pipeline.

Явная экспериментальная демонстрация CatBoost:

```sh
export FEED_RELEASE=v2 FEED_RANKER=catboost FEED_BUNDLE_PATH=./.local/feed-v2-linux/catboost
docker compose up -d --wait --wait-timeout 300
```

Сбросьте `FEED_RANKER=e5` и путь к E5 bundle после демонстрации. Не переиспользуйте каталог от одного release с bundle другого. ML и backend получают единый `FEED_RELEASE`. Все суммы в публичном API — safe integer копейки; UI разбирает десятичный ввод через BigInt, без float multiplication. Отрицательные прибыль/EBIT/капитал разрешены, пустое поле отсутствует в JSON. Поле формы «Все обязательства» — totalLiabilitiesMinor, а не общий кредитный долг.

## Synthetic fraud

Пользователь явно выбрал серверные неизменяемые синтетические reference. В `integration.synthetic_reference` закреплены company/period/version/source/availableAt, statementDigest и полный recordDigest. Seed — только demo-профиль, `R__demo_synthetic_reference_seed.sql`. Изменение существующих строк запрещает SQL trigger; новые источники должны получать новую версию/ID. Источник не выведен из формы или предварительной выручки. Неподдерживаемый период не получает придуманного reference: обязательный proxy → MANUAL.

Модель `catboost-manipulation-v1` и feature code из `802f998` сохранены с исходными checksum. ML migration `V3__fraud.sql` не конфликтует с `V2__bridge.sql`. Новый backend input adapter принимает допуски и точные document references; delta-признаки проверены на parity с исходной трансформацией, значения не исправляются. В журнале закрепляются model/feature/adapter/reference digests. Bridge сверяет существующий Risk inference перед Fraud. Backend связывает оба с company/application/task/caseVersion/financial snapshot и сохраняет результат до решения.

Risk и Fraud не усредняются. `demo-policy-v1` остаётся основой: ранние RFI/eligibility/financial gates сохранены; отдельный manual-overlay действует перед предложением. Весь dual review ограничен шестью секундами, Fraud получает оставшийся бюджет; запоздалый ответ не создаёт предложение. Недоступность обязательного результата → MANUAL; высокий синтетический score → MANUAL. Native `synthetic-dual-policy-4` не является Java-policy.

Это исследовательский `SYNTHETIC_MANIPULATION_PROXY` на синтетике. На отдельном невиданном семействе recall=0. Пользовательская польза и банковское качество не установлены.

Отключение независимо от Risk:

```sh
export FRAUD_MODE=off
docker compose up -d --wait --wait-timeout 300
```

## Приёмка и откат

`bash scripts/integration/linux_acceptance.sh` последовательно повторяет базовую поставку, готовит v2 artifacts без сети, проверяет модели, UI в Chromium, отсутствие reference, Fraud/Feed/Risk outage, restart, network isolation и config rollback поверх тех же volumes. GitHub Actions сохраняет точный commit и evidence; локальный macOS запуск не подменяет Linux PASS.

Откат рекомендателя и synthetic proxy:

```sh
export FEED_RELEASE=v1 FEED_RANKER=e5 FEED_BUNDLE_PATH=./.local/feed-bundle FRAUD_MODE=off
docker compose up -d --wait --wait-timeout 300
```

Не запускайте `down -v`, не удаляйте таблицы/историю Flyway, не переписывайте V1/V2 и не очищайте пользовательские реакции. `ml-migrate` применяет только новую V3 с checksum-проверкой; init продолжает устанавливать исходные V1/V2. Backend Flyway добавляет V17 (offer commands), V18 (reference/attempt/result). Старые сохранённые responses никогда не реконструируются по новому каталогу: другой catalog digest → 409; после возвращения v1 повтор untouched cursor возвращает тот же content/order/exposure. Смена предпочтений/сохранений независимо инвалидирует их cursor. Бинарный rollback всей поставки проверяется отдельно от config rollback; не считать его проверенным по одному переключению модели.

## Границы UI

Сохранён исходный React/Ant Design UI: вход, выбор компании, каталог, черновик, финансы, документы, RFI, статус, предложение, принятие и демооформление, лента/предпочтения/полезное. Обязательные запросы идут в реальный backend; MSW не запускается. VIEW: >=50% непрерывно 1000мс в видимой вкладке. Потерянный ответ feedback повторяется с теми же body/clientEventId/Idempotency-Key.

Потребность до создания заявки и отметки ознакомления живут в памяти вкладки; UI не выдаёт их за серверное юридическое согласие. Редактирование company master data не поддерживается: название/ИНН read-only, деятельность/возраст относятся к заявке. Проверка продукта принадлежит backend, ставка не выдумывается. Приём/завершение предложения теперь сохраняются сервером, проверяют роль/версию/срок и воспроизводят ответ по ключу.

Чат и OCR будут подключены позже, места в интерфейсе сохранены. Сейчас они обозначены как «скоро»; вместо OCR работает ручной ввод. Inbox отсутствует; RFI и история доступны в заявке. SSE/barrier/operation-by-key не выдумываются: обновляются фактические read endpoints. Ручной input сохраняется в памяти формы при ошибке/конфликте, автоматического overwrite по новой CAS-версии нет.
