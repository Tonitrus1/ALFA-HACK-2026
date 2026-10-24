# Docker и GitHub

Текущая версия использует простой вход по имени; регистрация и пароль отменены. Docker упаковывает только frontend и Nginx, не добавляет backend или банковские сервисы. По умолчанию запускается существующий MSW-режим.

## Запуск через Docker Desktop

На Windows установите [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/), включите Linux containers и запустите приложение. Установщик может потребовать включения WSL 2 и перезагрузки Windows. Наличие Docker Engine проверяется командой `docker info`.

Откройте PowerShell в папке с Dockerfile:

```powershell
docker compose up --build -d
```

Приложение: http://localhost:8080/login. Состояние: `docker compose ps`. Журнал: `docker compose logs -f frontend`. Остановка: `docker compose down`.

На компьютере не требуется Node.js: сборка выполняется внутри первого этапа образа. В финальном образе остаются Nginx и собранная статика. Зависимости фиксирует package-lock.json. `.env`, node_modules, отчёты и локальный dist не попадают в build context.

После изменения исходников повторите `docker compose up --build -d`. При занятом порте:

```powershell
$env:FRONTEND_PORT='8088'
docker compose up --build -d
```

Порт привязан к loopback и доступен только с этого компьютера. Для внешнего доступа настройте публикацию порта, HTTPS и настоящий backend отдельно.

## Обычные команды Docker без Compose

```powershell
docker build -t potok-frontend:local .
docker run --rm -p 127.0.0.1:8080:80 potok-frontend:local
```

Healthcheck: `/healthz`. Прямые переходы `/login`, `/workspace` и другие маршруты SPA возвращают index.html. Отсутствующий `/assets/*` возвращает 404. `/api/*` проксируется отдельно и никогда не заменяется HTML приложения. Для SSE выключена буферизация, установлен таймаут 75 секунд. Worker и HTML отдаются без долговременного кеша.

## Подключение backend

Vite-переменные фиксируются при сборке, поэтому одного `docker run -e VITE_API_MODE=...` недостаточно. Для согласованного temporary contract из INTEGRATION.md:

```powershell
$env:VITE_API_MODE='integrated'
$env:VITE_CONTRACT_ACK='provisional-v1'
$env:BACKEND_ORIGIN='http://host.docker.internal:8081'
docker compose up --build -d
```

`host.docker.internal` на Docker Desktop указывает на хост, не на сам контейнер. Для backend в другой службе Compose используйте её DNS-имя и подключите обе службы к общей сети. `BACKEND_ORIGIN` — адрес upstream без суффикса `/api` и без завершающего `/`; например `http://backend:8080`. Nginx сохраняет исходный путь `/api/...`, cookies и заголовки. Production cookies/CSRF, полномочия и SSE journal принадлежат backend. Для внешнего HTTPS задавайте Secure cookies на backend и TLS на reverse proxy.

Не передавайте секреты в VITE_* или build args. Доступность `/healthz` означает готовность веб-сервера; это не проверка состояния backend.

## Передать готовый Docker-образ файлом

Только после успешной сборки:

```powershell
docker save -o potok-frontend-image.tar potok-frontend:local
```

Получатель загружает его через `docker load -i potok-frontend-image.tar`, затем запускает `docker run --rm -p 127.0.0.1:8080:80 potok-frontend:local`. TAR образа не нужно коммитить в Git. ZIP с исходниками не является Docker-образом.

## GitHub: сохранить существующий репозиторий

Репозиторий: `https://github.com/Tonitrus1/ALFA-HACK-2026`. Frontend размещается в `frontend/`, ветка `frontend/docker-package`, изменения предлагаются через Pull Request в `main` по правилам CONTRIBUTING.md. Пароли/PAT не записывайте в файлы проекта и не передавайте в чат.

Чтобы продолжить разработку локально с историей репозитория:

```powershell
git clone --branch frontend/docker-package https://github.com/Tonitrus1/ALFA-HACK-2026.git
cd ALFA-HACK-2026/frontend
docker compose up --build -d
```

Не выполняйте force push и не создавайте новый корневой commit поверх существующей истории. Следующие задачи начинайте отдельной веткой от свежей `main` после объединения Pull Request.

Файлы, необходимые для коммита: `src/`, `public/`, `tests/`, `tools/`, `docker/`, `docs/`, `screenshots/`, package.json, package-lock.json, конфигурации TypeScript/Vite/ESLint/Playwright/Vitest/Prettier, index.html, README.md, `.env.example`, `.gitignore`, `.gitattributes`, `.dockerignore`, Dockerfile и compose.yaml.

Не коммитить: node_modules, dist, `.env`/`.env.*` кроме `.env.example`, тестовые отчёты, tsbuildinfo, ZIP/TAR, логи и credentials. Перед push просмотрите `git diff --cached --stat` и `git diff --cached`.

## Проверка готовности

Для проверки конфигурации и контейнера:

```powershell
docker compose config
docker compose build
docker compose up -d
docker compose ps
curl.exe -f http://localhost:8080/healthz
curl.exe -I http://localhost:8080/login
docker compose exec frontend nginx -t
```

Архитектура сборки следует [руководству Docker для React](https://docs.docker.com/guides/reactjs/) и [официальному образу Nginx](https://hub.docker.com/_/nginx).
