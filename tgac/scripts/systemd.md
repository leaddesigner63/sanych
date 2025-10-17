# systemd units

Сохраните файлы в `/etc/systemd/system/` и выполните `systemctl daemon-reload`.

## tgac-api.service
```
[Unit]
Description=TGAC API (Uvicorn)
After=network-online.target

[Service]
EnvironmentFile=/opt/tgac/.env
WorkingDirectory=/opt/tgac
Environment=PYTHONPATH=/opt/tgac
ExecStart=/opt/tgac/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

## tgac-scheduler.service
```
[Unit]
Description=TGAC Scheduler
After=tgac-api.service

[Service]
EnvironmentFile=/opt/tgac/.env
WorkingDirectory=/opt/tgac
Environment=PYTHONPATH=/opt/tgac
ExecStart=/opt/tgac/venv/bin/python -m workers.scheduler
Restart=always

[Install]
WantedBy=multi-user.target
```

## tgac-worker@.service
```
[Unit]
Description=TGAC Worker Instance %i
After=tgac-scheduler.service

[Service]
EnvironmentFile=/opt/tgac/.env
WorkingDirectory=/opt/tgac
Environment=PYTHONPATH=/opt/tgac
ExecStart=/opt/tgac/venv/bin/python -m workers.worker
Restart=always

[Install]
WantedBy=multi-user.target
```

## tgac-observer.service
```
[Unit]
Description=TGAC Observer
After=tgac-scheduler.service

[Service]
EnvironmentFile=/opt/tgac/.env
WorkingDirectory=/opt/tgac
Environment=PYTHONPATH=/opt/tgac
ExecStart=/opt/tgac/venv/bin/python -m workers.observer
Restart=always

[Install]
WantedBy=multi-user.target
```

## tgac-bot.service
```
[Unit]
Description=TGAC Telegram Bot
After=network-online.target

[Service]
EnvironmentFile=/opt/tgac/.env
WorkingDirectory=/opt/tgac
Environment=PYTHONPATH=/opt/tgac
ExecStart=/opt/tgac/venv/bin/python -m bot.app
Restart=always

[Install]
WantedBy=multi-user.target
```
