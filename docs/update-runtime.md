# Обновление работающего Docker-стенда

Финальная версия находится в `main`, единым итоговым commit, тег `submission-2026-10-26-r2`. Предыдущий релиз и его тег заменены по решению владельца. Обычный `git pull --ff-only` со старой истории не подходит. Прямой `switch -C main origin/main` работает также после исходного single-branch клонирования серверной ветки.

Выполните **в папке репозитория на сервере**:

```sh
# Сохранить локальные правки отслеживаемых файлов. .env остаётся на месте.
git stash push -m "server-before-final-main"
git fetch origin '+refs/heads/main:refs/remotes/origin/main'
git switch -C main origin/main

# Узнать и проверить исходную конфигурацию работающего Docker-проекта.
python3 scripts/update_runtime.py --dry-run
# Пересобрать и пересоздать только backend и gateway, дождаться health.
python3 scripts/update_runtime.py
```

Если это **Selectel overlay с `.env.selectel`**, две последние команды:

```sh
python3 scripts/update_runtime.py --env-file .env.selectel --dry-run
python3 scripts/update_runtime.py --env-file .env.selectel
```

При нескольких установках добавьте `--project ИМЯ` из `docker compose ls`. Если Docker требует root, добавьте `sudo` перед `python3 scripts/update_runtime.py`.

Скрипт читает labels работающего backend и сохраняет Compose project, список/порядок конфигурационных файлов и записанный env-файл. Он проверяет, что это backend именно текущего checkout, затем выполняет `config --quiet`, `build backend gateway` и `up -d --no-deps --force-recreate --wait backend gateway`. Остальные сервисы и volumes не удаляются. При обновлении возможен короткий перерыв доступа к backend/gateway. Существующий ngrok-процесс продолжает направлять запросы на тот же порт.

Пароли и `.env` не надо менять. Не запускайте `down -v`. Сохранённые tracked-правки остаются в `git stash list`; не применяйте их обратно автоматически поверх новой конфигурации. Не меняйте имя Compose-проекта.

## Что меняется во входе

- Два синтетических демоаккаунта `company-a` и `company-b` принимают правильный пароль сразу после ошибок.
- Старый `locked_until` не мешает правильному паролю демоаккаунта и очищается после успешного входа. SQL-очистка вручную не требуется.
- Неверный пароль по-прежнему возвращает `401 INVALID_CREDENTIALS` без сессии.
- Для остальных credentials сохранены пять ошибок / 15 минут.
- Nginx ограничивает частоту запросов ко входу: 30/min по сетевому адресу, burst 20. Превышение даёт JSON `429 AUTH_RATE_LIMITED` и `Retry-After: 2`. За прокси сетевой адрес может быть общим. Это не 15-минутная блокировка аккаунта.

Перезагрузите страницу входа и войдите действующим паролем. Старый текст о 15 минутах после обновления исчезает: он поступал из backend.
