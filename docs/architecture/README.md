# Кредитный кабинет: согласованный комплект HACKATHON-1.5

20 октября 2026 года. Начните с [офлайн-обзора](index.html), затем с аудита и руководства по Git/защите. Приложение не реализовано. Это спецификация. Публикация/приглашение жюри не выполнялись.

- [Адаптеры и полный стек](technology-adapters.pdf) - [Markdown](docs/technology-adapters.md).
- [Аудит](architecture-audit.pdf) - [Markdown](docs/architecture-audit.md).
- [Git и защита](git-and-jury-guide.pdf) - [Markdown](docs/git-and-jury-guide.md).
- [План разработки](development-plan.pdf) - [Markdown](docs/development-plan.md).
- [General](packages/general/general-guide.pdf) - [Markdown](packages/general/docs/guide.md).
- [Backend](packages/backend/backend-guide.pdf) - [Markdown](packages/backend/docs/guide.md).
- [Frontend](packages/frontend/frontend-guide.pdf) - [Markdown](packages/frontend/docs/guide.md).
- [Ml](packages/ml/ml-guide.pdf) - [Markdown](packages/ml/docs/guide.md).
- [Атлас схем](architecture-atlas.pdf), [редактируемый draw.io](architecture.drawio), [SVG](diagrams/).
- [Контрактные решения](docs/contract-decisions.md), [модель данных](docs/data-model.md), [приёмка](docs/acceptance.md).
- [Проверенные источники](docs/sources.md), [допущения и gates](docs/assumptions-and-gates.md).
- findings.json / tasks.json / acceptance-cases.json - машинные реестры.
- contracts/ - единственные редактируемые контракты; копии в пакетах генерируются.
- evidence/originals.zip - исходные файлы и генераторы, original-sha256.json - полная инвентаризация. Старые пакеты вне этой папки исторические.
- validation-report.json - результаты статических проверок; visual-review.json - отдельный визуальный протокол, привязанный к hashes PDF. Отсутствие/устаревание visual-review означает незавершённый просмотр.
- templates/ - шаблоны будущего репозитория приложения; не готовые настройки CI/доступа и не рабочий Docker-проект.

## Повторная сборка

Python3.12+. Создать отдельную среду и установить sources/requirements-render.txt. Шрифты и лицензия вложены; старые пакеты/приватные runtime-пути не нужны. Выполнить python sources/build.py, затем python sources/validate.py. Builder сохраняет канонические Markdown/контракты; аудит и реестр задач генерируются из sources/*template.md и JSON-реестров. Он и пересобирает только представления, копии и отчёты. Если зависимости установлены вне среды, допускается CREDIT_RENDER_DEPS с явным путём.

Изменять Markdown в docs/ и packages/*/docs/; для генерируемых audit/development-plan - sources/*template.md. Изменять JSON в contracts/, реестры tasks/findings/acceptance и геометрию sources/diagrams.json. Draw.io - редактируемый экспорт; при ручном редактировании экспортировать смысловые изменения обратно в источник геометрии до пересборки. Старые генераторы не управляют новым комплектом.

После изменения PDF нужен новый визуальный просмотр; старые hashes не подтверждают новую редакцию. Архив финальной поставки и SHA256SUMS создаются sources/package.py только после успешного validate и актуального visual review. Приложение, Docker-сборка, модели/веса и их метрики этим builder не создаются.
