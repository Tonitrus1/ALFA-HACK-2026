# Фактическая приёмка интеграции

Дата: 22.10.2026. Локальная среда: macOS arm64, JDK 21.0.13, Python 3.12, отдельный PostgreSQL 17 и отдельные порты. Исходные стенды пользователя не изменялись.

- Backend unit/integration/architecture: 120 выполненных проверок без ошибок; opt-in live ML проверяется отдельным прогоном. Сводка `backend-tests.json`.
- Java backend -> bridge -> реальные CatBoost/E5/PG: 4 проверки, включая реальный RFI и backend balance tolerance. `backend-real-ml.xml`.
- Legacy Risk regression, включая исходный HTTP API: 31 PASS. `risk-regression.xml`.
- Feed regression с настоящей offline E5: 58 PASS. `feed-regression.xml`.
- Bridge contract tests: 4 PASS. `bridge-unit.xml`.
- Bridge real HTTP/PG/concurrency/failure tests: 4 PASS. `bridge-native.xml`.
- Public HTTP / OpenAPI / cookie-CSRF / изоляция компаний: PASS. `public-http.json`.
- Полный restart PG/ML/backend с сохранностью решения, cursor/exposure и feedback replay: PASS. `restart-http.json`.
- Остановка выделенного Feed: RULES и работа заявки с настоящим Risk, PASS. `feed-outage-http.json`.
- Остановка выделенного Risk: MANUAL, без автоматического отказа, PASS. `risk-outage-http.json`.
- Статическая исходная архитектура/контракты: 427 checks, PASS; это отдельная проверка спецификации.
- TypeScript API adapter: strict typecheck PASS. Полный существующий UI на provisional-v1 не принят.
- Новый PDF: все 9 страниц отрендерены и просмотрены; hashes и результат в `document-build.json`.

При одновременной загрузке нескольких E5-экземпляров один live Java-запрос превысил бюджет и корректно перешёл на RULES; повторный полный прогон без конкурирующей загрузки прошёл MODEL. Нагрузочные SLO, p95/p99 и ресурсные пределы этим не установлены.

**Linux Docker Compose: ожидается отдельный GitHub Actions run.** Docker отсутствует на этом Mac. Локальные результаты не означают Linux PASS. Workflow собирает чистые образы, готовит веса на Linux, проверяет public API, restart, отказы и запрет внешнего TCP; результат будет указан отдельным отчётом.

Первоначальные сбои проверки локали embedded PostgreSQL, ошибки новых тестов и недостающий FEED_BUNDLE исправлены перед финальными прогонами. Исторические отчёты в других папках не считаются доказательством этой интеграции.
