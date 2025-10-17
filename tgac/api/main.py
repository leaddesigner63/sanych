from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .routers import (
    accounts,
    auth,
    channels,
    exports,
    history,
    logs,
    metrics,
    playlists,
    projects,
    proxies,
    settings,
    tasks,
    users,
)

app = FastAPI(title="TG Commenting Combiner")
templates = Jinja2Templates(directory="tgac/api/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


def include_routers(application: FastAPI) -> None:
    for router in [
        auth.router,
        users.router,
        projects.router,
        accounts.router,
        proxies.router,
        channels.router,
        playlists.router,
        tasks.router,
        logs.router,
        metrics.router,
        history.router,
        exports.router,
        settings.router,
    ]:
        application.include_router(router)


include_routers(app)
