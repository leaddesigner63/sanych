
# Техническое задание для разработчика (Coder Spec)
**Проект:** SaaS «TG‑Комбайн для автокомментинга»  
**Домен:** `tg.vpn-gpt.store`  
**Дата:** 2025‑10‑16

---

## 0. Цель документа
Дать разработчику полный план работ: организовать репозиторий, поднять инфраструктуру, реализовать весь бэкенд/бот/воркеры/веб‑панель и обеспечить выпуск MVP с приёмкой.

---

## 1. Архитектура и стек

**Сервисы (процессы):**
1. **API+Admin UI** — FastAPI + Jinja2 + HTMX/Tailwind (порт 8080).
2. **Scheduler** — планирование задач (скан каналов, план комментинга, healthcheck).
3. **Worker** — исполнение задач (комментинг, подписка, healthcheck, autoreg шаги).
4. **Observer** — проверка видимости комментариев.
5. **TG‑бот** — aiogram/Telethon: аутентификация пользователей (login через /start payload) + уведомления.

**Язык/библиотеки:** Python 3.12, FastAPI, SQLAlchemy + Alembic, Telethon, aiogram, loguru/standard logging.  
**Хранение:** SQLite (WAL) v1, готовность к Postgres через `DB_URL`.  
**Очередь:** таблица `jobs` в БД (позже — Redis/Celery).  
**Веб:** Nginx + Let’s Encrypt (домен `tg.vpn-gpt.store`).  
**LLM:** OpenAI (генерация текстов профилей/контента; аватары не генерируем).

---

## 2. Репозиторий и дерево проекта

```
tgac/
├─ api/                      # FastAPI, UI, endpoints, schemas
│  ├─ main.py
│  ├─ deps.py
│  ├─ routers/               # users, projects, accounts, proxies, channels, playlists, tasks, logs, settings, auth, exports
│  ├─ services/              # business-logic: auth_flow, scheduler_core, comment_engine, observer, autoreg, sms, proxies, llm, limits, exports
│  ├─ models/                # SQLAlchemy models
│  ├─ schemas/               # Pydantic схемы
│  ├─ templates/             # Jinja2 (адаптивный UI, HTMX)
│  ├─ static/                # css/js/assets
│  └─ utils/                 # helpers (crypto, time, i18n, spintax)
├─ workers/
│  ├─ scheduler.py
│  ├─ worker.py
│  └─ observer.py
├─ bot/
│  ├─ app.py                 # aiogram bot
│  └─ handlers.py
├─ migrations/               # Alembic
├─ scripts/                  # deploy, certs, manage, demo data
├─ data/
│  ├─ db.sqlite3
│  └─ sessions/              # Telethon .session (шифрована)
├─ logs/
│  ├─ app.log
│  └─ events.jsonl
├─ .env.example
├─ README.md
├─ Makefile
└─ LICENSE
```

---

## 3. Переменные окружения (.env)

Обязательные:
```
ADMIN_TG_USERNAME=admin_username
TELEGRAM_BOT_TOKEN=...
TELEGRAM_DEEPLINK_TTL_MIN=10
OPENAI_API_KEY=...
SMS_ACTIVATE_API_KEY=...
BRIGHTDATA_USERNAME=...
BRIGHTDATA_PASSWORD=...
TZ=Europe/Amsterdam
BASE_URL=https://tg.vpn-gpt.store

DB_URL=sqlite:////absolute/path/tgac/data/db.sqlite3
SESSION_SECRET_KEY=base64_fernet_key

LOG_RETENTION_DAYS=7
MAX_CHANNELS_PER_ACCOUNT=50
COMMENT_COLLISION_LIMIT_PER_POST=1
MAX_ACTIVE_THREADS_PER_ACCOUNT=50
```

Опциональные: `WORKER_SHARDS`, `WORKER_SHARD`, `MAX_CONCURRENCY` и др.

---

## 4. Модель данных (минимум)

**users**
- id PK, username UNIQUE, telegram_id NULLABLE, role ENUM(admin|user), is_active BOOL, created_at
- quota_projects INT NULL (персональный лимит проектов; NULL = дефолт)

**projects**
- id PK, user_id FK, name, status ENUM(active|paused|archived), created_at
- UNIQUE(user_id, name)

**accounts** (комментаторы)
- id PK, project_id FK, phone UNIQUE, session_enc BLOB, status ENUM(NEEDS_LOGIN,ACTIVE,BANNED,FLOOD_WAIT,DEAD), proxy_id FK NULL
- tags TEXT, notes TEXT, last_health_at, last_comment_at, created_at, updated_at

**proxies**
- id PK, project_id FK, name UNIQUE per project, scheme (http|socks5), host, port, username, password, last_check_at, is_working BOOL
- relation: 1 proxy → до 3 accounts (валидировать серверно)

**channels**
- id PK, project_id FK, title, username, tg_id BIGINT, link, active BOOL, created_at
- playlists_channels: M2M

**playlists**
- id PK, project_id FK, name, desc

**tasks**
- id PK, project_id FK, name, status(ON|OFF|PAUSED), mode ENUM(NEW_POSTS), config JSONB, created_at, updated_at

**task_assignments**
- id PK, task_id FK, account_id FK, assigned_at
- server check: суммарно активных каналов на account ≤ 50 (через карту ниже)

**account_channel_map**  (для быстрого контроля 50‑лимита)
- account_id FK, channel_id FK, PRIMARY KEY(account_id, channel_id)

**posts**
- id PK, channel_id FK, post_id BIGINT, published_at, detected_at, state
- UNIQUE(channel_id, post_id)

**comments**
- id PK, account_id FK, task_id FK, channel_id FK, post_id BIGINT, template TEXT, rendered TEXT, planned_at, sent_at
- result ENUM(SUCCESS|SKIPPED|ERROR), error_code, error_msg

**jobs**
- id PK, type ENUM(SCAN_CHANNELS|PLAN_COMMENTS|SEND_COMMENT|HEALTHCHECK|AUTOREG_STEP|SUBSCRIBE), payload JSON, priority INT, status
- run_after, locked_by, locked_at, tries, last_error, created_at

**settings**
- project_id FK NULL (NULL → глобальные), key PK(project_id,key), value TEXT

**audit_log**
- id PK, ts, actor(user_id|‘system’), action, meta JSON

Индексы по: `run_after/status`, `account_id`, `channel_id`, `post_id`, `project_id`.

---

## 5. Аутентификация (через Telegram‑бот)

**Флоу:**
1. `/auth/login` (GET UI) → генерируем `login_token` (nonce, TTL 10 мин), сохраняем в БД (status=pending).
2. Кнопка «Войти через Telegram» → deep‑link `https://t.me/<bot>?start=<login_token>`.
3. Бот `/start <login_token>`: получает `username` и `chat_id` → POST `/auth/telegram/exchange`:
   ```json
   { "login_token": "...", "username": "@user", "chat_id": 123456789 }
   ```
   Бэкенд: находит пользователя в БД (или админа в .env), связывает `telegram_id` (если пуст), помечает токен как `confirmed`, выпускает серверную сессию (cookie HttpOnly, SameSite=Lax).
4. Браузер параллельно опрашивает `/auth/telegram/poll?token=...`. При `confirmed` → 200 + Set‑Cookie сессии, редирект в кабинет.

**Выход:** `/auth/logout` очищает cookie.  
**Без пароля.**

---

## 6. Разделы UI (HTMX/Jinja)

- **Авторег**: задания на регистрацию (страна, партия, пол/язык), прогресс‑бар шагов, загрузка ZIP/CSV для массового редактирования профилей.
- **Аккаунты**: список/фильтры, привязка прокси, healthcheck, статусы, «Каналы в работе: X/50».
- **Прокси**: CRUD, проверка доступности, привязка 1→3, авто‑замена при падении.
- **Каналы**: CRUD, импорт списком, статус, плейлисты.
- **Плейлисты**: CRUD и состав.
- **Задания**: создание/редактирование (режим NEW_POSTS), назначение аккаунтов (массово, частично при лимите), пресеты Safe/Balanced/Boost.
- **Симулятор (dry‑run)**: прогон по последним N постам, что бы сделали (без отправки).
- **Логи/История**: tail‑stream, фильтры, экспорт CSV/JSONL.
- **Настройки**: пресеты, лимиты, окна, язык UI, уведомления, OpenAI ключ/лимиты (readonly, если из .env), sms‑activate/brightdata параметры.
- **Пользователи/Доступ (только админ)**: создание/блокировка пользователей, лимит проектов на пользователя.
- **Проекты**: CRUD проектов (workspaces), сводки.

---

## 7. Бизнес‑логика: лимиты и пресеты

**Жёстко:** `MAX_CHANNELS_PER_ACCOUNT=50` — серверно при назначениях и при активации задач.  
**Пресеты (редактируемые):**
- `MAX_ACTIVE_THREADS_PER_ACCOUNT` (K, дефолт 50).
- `COMMENT_COLLISION_LIMIT_PER_POST` (N, дефолт 1).
- Ночной покой, окна после публикации (мин/макс), паузы между действиями, джиттер, «не быть первым», typing, вероятность пропуска, warm‑up 3 дня.
- Автоподписка on/off.
- Адаптивное замедление/автопауза при `error_rate >= 5%` (включая FLOOD).

---

## 8. Планировщик и исполнение

**Детектор постов:** подписка «читателя»/пула на каналы проекта, запись в `posts`.  
**Планировщик:** для новых `posts` + активных `tasks` рассчитывает, нужно ли комментировать (пресеты/лимиты), ставит `jobs: SEND_COMMENT` с `run_after` в окне.  
**Исполнитель:**
- Проверяет пару `(account, channel)` в `account_channel_map`.
- При необходимости ставит `SUBSCRIBE` → join канала/linked discussion (с ретраями/таймаутами).
- Имитации (reading/typing), отправка комментария, запись результата. FLOOD_WAIT → статус, перенос. WRITE_FORBIDDEN → исключение канала/поста.
**Observer:** 1 на 200 каналов, периодическая проверка видимости комментариев (visibility rate).

---

## 9. Авторег (sms‑activate + Bright Data)

**Шаги AUTOREG_STEP:**
1. Выделить номер (страна из задания), взять прокси (следуя правилу 1→3).  
2. Зарегистрировать ТГ аккаунт через Telethon (код из sms‑activate).  
3. Сохранить `.session` (шифровано Fernet ключом `SESSION_SECRET_KEY`).  
4. Сгенерировать LLM профили (имя, био, интересы, язык; без аватара) или применить предоставленный ZIP/CSV.  
5. Разогрев: подписки/чтение/реакции 24–72 ч.  
6. Привязать к проекту, статус `ACTIVE`.

**Фолбэки:** ретраи, смена номера/прокси при сбоях; журнал событий в `events.jsonl`.

---

## 10. Уведомления (через того же бота)

- Пользователь: события по своим проектам/аккаунтам; частота по настройке (дефолт 1/24ч).
- Админ: плюс «жизнь проекта» (ошибки сервисов).  
- Критические (сбой/незапланированная остановка) — всегда и сразу.

---

## 11. Экспорт/удаление и ретеншн

- Экспорт ZIP: `profiles.csv`, `channels.csv`, `tasks.json`, `logs.jsonl`, `metrics.csv` (+ каталоги).  
- Удаление: только в рамках своих проектов, с подтверждением (modal).  
- Ретеншн: логи/история — 7 дней; метрики по проекту/аккаунту — бессрочно (удаляются вместе с объектом); ручная очистка доступна.

---

## 12. API контракты (основные, JSON `{ok, data|error}`)

**Auth**
- `POST /auth/telegram/token` → `{login_token}` (создать токен, TTL 10 мин).
- `POST /auth/telegram/exchange` → body `{login_token, username, chat_id}` → `{ok:true}` + серверная сессия (cookie).
- `GET /auth/telegram/poll?token=...` → `{status: pending|confirmed}` (+ Set‑Cookie при confirmed).
- `POST /auth/logout`

**Users (admin)**
- `POST /admin/users` `{username, quota_projects?}`
- `GET /admin/users` / `PUT /admin/users/{id}` / `POST /admin/users/{id}/block`

**Projects**
- `GET /projects` / `POST /projects` / `PUT /projects/{id}` / `DELETE /projects/{id}`

**Accounts**
- `GET /accounts` (filters) / `POST /accounts` / `POST /accounts/import`
- `POST /accounts/{id}/proxy` / `POST /accounts/{id}/healthcheck`
- `POST /accounts/{id}/pause` / `POST /accounts/{id}/resume`

**Proxies**
- `GET /proxies` / `POST /proxies` / `POST /proxies/import` / `POST /proxies/{id}/check`

**Channels & Playlists**
- `GET /channels` / `POST /channels` / `POST /channels/import`
- `GET /playlists` / `POST /playlists` / `PUT /playlists/{id}` / `POST /playlists/{id}/assign_channels`

**Tasks**
- `GET /tasks` / `POST /tasks` (mode=NEW_POSTS, config) / `PUT /tasks/{id}` / `POST /tasks/{id}/toggle`
- `POST /tasks/{id}/assign` `{account_ids|filters}` → частичное применение при лимите 50
- `GET /tasks/{id}/stats`

**Logs/History/Export**
- `GET /logs/tail?lines=500` / `GET /history/account/{id}` / `GET /history/task/{id}`
- `POST /export/project/{id}` → ZIP download

Все эндпоинты — в рамках текущего проекта/пользователя (мульти‑тенантная изоляция), кроме `/admin/*` (только админ).

---

## 13. Telegram‑бот (aiogram)

Хендлеры:
- `/start <login_token>` — аутентификация: вызвать `/auth/telegram/exchange`, сохранить `username`, `chat_id`, ответить «Успешный вход, вернитесь в браузер».
- `/help` — краткая справка.
- Сервисные: получение уведомлений от API (webhook/long‑poll) — оповещать пользователей/админа.

Настройки: Webhook или long‑poll (подходит long‑poll).

---

## 14. Nginx и TLS (tg.vpn-gpt.store)

- A‑запись домена → VPS 45.92.174.166
- Серверный блок:
  - 80 → редирект на 443.
  - 443 → reverse proxy к `127.0.0.1:8080` (API+UI).
  - Включить `proxy_set_header Upgrade`/`Connection upgrade` для WebSocket/HTMX SSE при необходимости.
  - Let’s Encrypt (certbot) автопродление.

---

## 15. systemd юниты (пример)

`/etc/systemd/system/tgac-api.service`
```
[Unit]
Description=TGAC API (Uvicorn)
After=network-online.target

[Service]
EnvironmentFile=/path/to/tgac/.env
WorkingDirectory=/path/to/tgac
Environment=PYTHONPATH=/path/to/tgac
ExecStart=/path/to/tgac/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

`tgac-scheduler.service`, `tgac-worker@.service` (шард через `%i`), `tgac-observer.service`, `tgac-bot.service` — по аналогии.

---

## 16. Логи и метрики

- `logs/app.log` (ротация, уровень INFO/DEBUG через .env).
- `logs/events.jsonl` — одна запись на действие (аккаунт, канал, пост, результат, коды/тайминги).
- Метрики: counters (успех/ошибки, FLOOD, visibility), хранятся бессрочно (в БД), ретеншн логов/истории — 7 дней.

---

## 17. Тесты и приёмка

- Юнит‑тесты: utils, spintax, лимиты, парсинг конфигов, авторизация токенов.
- Интеграционные: login через бота (mock), планировщик, воркер, observer.
- Smoke: UI доступен, пресеты применяются, лимит 50 каналов соблюдается, автоподписка работает, экспорт ZIP формируется.
- Критерии приёмки — как в разделах MVP и «Критерии» из заказчика.

---

## 18. План работ (итерации)

1) Scaffold репо, Alembic, модели, auth‑флоу (бот + токены + cookie), UI каркас.  
2) Users/Projects/Settings, квоты проектов.  
3) Proxies/Accounts (импорт, health), session‑шифрование.  
4) Channels/Playlists, карта `account_channel_map`, валидаторы 50‑лимита.  
5) Tasks (NEW_POSTS), пресеты, Scheduler/Worker, авто‑подписка, комментинг.  
6) Observer, visibility rate, адаптивный троттлинг (5%).  
7) Авторег (sms‑activate + Bright Data), стейт‑машина, разогрев.  
8) Логи/История/Экспорт, уведомления, дашборды.  
9) Nginx + TLS, systemd, Makefile/скрипты, финальные тесты.

---

## 19. Замечания по безопасной эксплуатации
- Следить за ToS Telegram и провайдерами SMS/прокси; риски банов и недоступности номеров/прокси.  
- Хранить `.session` шифрованно, ключ — только из `.env`.

---

## 20. Готовые артефакты
- `.env.example`
- Makefile (`setup`, `migrate`, `run`, `fmt`, `lint`, `test`)
- Шаблоны systemd
- Nginx server block
- Демоданные для UI (фикстуры) — по желанию
