from __future__ import annotations

from collections import defaultdict

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .routers import (
    accounts,
    audit,
    auth,
    channels,
    exports,
    history,
    llm,
    logs,
    metrics,
    playlists,
    projects,
    proxies,
    settings,
    tasks,
    users,
)
from .deps import get_db
from .models.core import Account, Channel, Project, ProjectStatus, Task, TaskStatus

app = FastAPI(title="TG Commenting Combiner")
templates = Jinja2Templates(directory="tgac/api/templates")


def _project_cards(db: Session, limit: int = 5) -> list[dict]:
    projects = (
        db.query(Project)
        .order_by(Project.created_at.desc())
        .limit(limit)
        .all()
    )
    if not projects:
        return []

    project_ids = [project.id for project in projects]

    def _counts(model, column, *filters) -> dict[int, int]:
        query = db.query(column, func.count(model.id)).filter(column.in_(project_ids))
        for condition in filters:
            query = query.filter(condition)
        return dict(query.group_by(column).all())

    account_counts = _counts(Account, Account.project_id)
    channel_counts = _counts(Channel, Channel.project_id)
    task_counts = _counts(Task, Task.project_id)
    active_task_counts = _counts(
        Task,
        Task.project_id,
        Task.status == TaskStatus.ON,
    )

    status_labels = {
        ProjectStatus.ACTIVE.value: "Активен",
        ProjectStatus.PAUSED.value: "На паузе",
        ProjectStatus.ARCHIVED.value: "Архив",
    }

    status_styles = defaultdict(
        lambda: "bg-slate-200 text-slate-600",
        {
            ProjectStatus.ACTIVE.value: "bg-emerald-100 text-emerald-700",
            ProjectStatus.PAUSED.value: "bg-amber-100 text-amber-700",
            ProjectStatus.ARCHIVED.value: "bg-slate-200 text-slate-600",
        },
    )

    cards: list[dict] = []
    for project in projects:
        project_id = project.id
        cards.append(
            {
                "id": project_id,
                "name": project.name,
                "status": project.status.value,
                "status_label": status_labels.get(project.status.value, project.status.value),
                "status_class": status_styles[project.status.value],
                "created_at": project.created_at,
                "accounts": account_counts.get(project_id, 0),
                "channels": channel_counts.get(project_id, 0),
                "tasks": task_counts.get(project_id, 0),
                "active_tasks": active_task_counts.get(project_id, 0),
            }
        )

    return cards


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    summary = {
        "projects_total": db.query(func.count(Project.id)).scalar() or 0,
        "accounts_total": db.query(func.count(Account.id)).scalar() or 0,
        "channels_total": db.query(func.count(Channel.id)).scalar() or 0,
        "tasks_total": db.query(func.count(Task.id)).scalar() or 0,
        "active_tasks": db.query(func.count(Task.id))
        .filter(Task.status == TaskStatus.ON)
        .scalar()
        or 0,
    }

    context = {
        "summary": summary,
        "projects": _project_cards(db),
    }
    return templates.TemplateResponse(request, "index.html", context)


def include_routers(application: FastAPI) -> None:
    for router in [
        auth.router,
        audit.router,
        users.router,
        projects.router,
        accounts.router,
        proxies.router,
        channels.router,
        playlists.router,
        tasks.router,
        logs.router,
        llm.router,
        metrics.router,
        history.router,
        exports.router,
        settings.router,
    ]:
        application.include_router(router)


include_routers(app)
