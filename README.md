
# tg-commenter (MVP)

Проект для мониторинга каналов/обсуждений в Telegram и "человечных" комментариев от отдельных аккаунтов.
Стек: FastAPI, PostgreSQL, Redis, Telethon, Docker.

## Быстрый старт
1. Скопируй `.env.example` в `.env` и заполни значения.
2. `docker compose -f infra/docker-compose.yml --env-file infra/.env up --build -d`
3. API: http://localhost:8000/docs
