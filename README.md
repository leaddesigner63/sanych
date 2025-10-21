# TG Commenting Combiner (TGAC)

Этот репозиторий содержит каркас SaaS-платформы «TG-Комбайн для автокомментинга». Репозиторий включает сервисы FastAPI с Jinja2/HTMX UI, Telegram-бота, планировщик и воркеры, миграции, конфигурацию Nginx/systemd и вспомогательные скрипты для развёртывания.

## Структура

- `tgac/api` — приложение FastAPI с HTMX-интерфейсом, SQLAlchemy-моделями и бизнес-логикой.
- `tgac/workers` — процессы планировщика, воркера и наблюдателя очереди задач.
- `tgac/bot` — Telegram-бот на aiogram для авторизации и уведомлений.
- `tgac/migrations` — Alembic-конфигурация и базовая миграция схемы данных.
- `tgac/scripts` — конфигурации Nginx, systemd и скрипты управления.
- `tgac/data` — SQLite база и директория для Telethon-сессий.
- `tgac/logs` — каталоги для логов приложения и событий.
- `tests` — базовые автоматические тесты.

## Быстрый старт

1. Создайте и заполните `.env` на основе `.env.example` (см. пример значений и подсказки по генерации секретов).
2. Установите зависимости: `make setup` (используется `requirements.txt`).
3. Выполните миграции БД: `make migrate`.
4. Запустите API и UI: `make dev`. При необходимости запустите фоновые сервисы `make scheduler`, `make worker`, `make observer`, `make bot`.

Дополнительные команды смотрите в `Makefile`.

## Конфигурация окружения

Переменные окружения описаны в `.env.example`. При развёртывании на сервере выполните следующие шаги:

1. **Путь до проекта.** Предположим, код расположен в `/opt/tgac`. Создайте директории для БД и логов:

   ```bash
   sudo mkdir -p /opt/tgac/data /opt/tgac/logs
   sudo chown -R <user>:<group> /opt/tgac
   ```

2. **Заполните `.env`.** Скопируйте шаблон и откройте его для редактирования:

   ```bash
   cp /opt/tgac/.env.example /opt/tgac/.env
   nano /opt/tgac/.env
   ```

3. **Ключи и токены.**
   - `TELEGRAM_BOT_TOKEN` — создайте бота через @BotFather и скопируйте токен.
   - `SESSION_SECRET_KEY` — сгенерируйте новый ключ (Fernet base64) командой:

     ```bash
     python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
     ```

   - `OPENAI_API_KEY` — укажите ключ OpenAI (оставьте пустым, если генерация не используется).
   - `SMS_ACTIVATE_API_KEY`, `BRIGHTDATA_USERNAME`, `BRIGHTDATA_PASSWORD` — заполните при наличии интеграций.

4. **База данных.** Убедитесь, что `DB_URL` указывает на абсолютный путь:

   ```env
   DB_URL=sqlite:////opt/tgac/data/db.sqlite3
   ```

5. **Настройка домена.** Обновите `BASE_URL`, `TZ`, `LOG_LEVEL` под свою инфраструктуру.

6. **Секреты и права доступа.** Ограничьте доступ к файлу `.env`:

   ```bash
   chmod 600 /opt/tgac/.env
   ```

При изменении конфигурации перезапускайте соответствующие systemd-сервисы (`sudo systemctl restart tgac-api.service` и др.).

## Лицензия

Проект распространяется по лицензии MIT, текст доступен в файле `LICENSE`.
