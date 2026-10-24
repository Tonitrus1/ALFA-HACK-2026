> Общий запуск, реальный API и проверки: [README приложения](../README.md). В интеграционной ветке MSW не запускается. Описания provisional-v1 ниже — история исходной frontend-поставки.

# Существующий UI на фактическом backend API

UI перенесён из `/Users/user/Documents/Alfa_hack/frontend`; исходная папка не изменена. Сборка запускает настоящий API-клиент без MSW. `npm ci`, `npm run build`, `npm test`, `npm run test:e2e`. Для локальной разработки `BACKEND_ORIGIN=http://127.0.0.1:18080 npm run dev`; demo Origin 5173 разрешён. В Compose UI раздаёт общий gateway 8080.

Карта DTO и ошибок: `../docs/ui-feed-antifraud-decisions.md`. Полная подготовка и ограничения: `../docs/ui-feed-antifraud-runbook.md`. `docs/INTEGRATION.md` сохранён как исторический provisional-контракт исходного UI и не описывает текущий transport.

Playwright integrated config использует реальный backend и модели. Для Linux сначала `npx playwright install --with-deps chromium`; для локального macOS используется установленный Chrome. Сервер должен быть запущен заранее; mock mode в точке входа отсутствует. Чат и OCR появятся позже.
