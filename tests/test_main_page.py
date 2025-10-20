import os

from fastapi.testclient import TestClient

from tgac.api import deps, main
from tgac.api.deps import Base, SessionLocal
from tgac.api.models.core import (
    Account,
    AccountStatus,
    Channel,
    Project,
    ProjectStatus,
    Task,
    TaskMode,
    TaskStatus,
    User,
)


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_main_page_shows_summary(tmp_path):
    env_keys = ["TELEGRAM_BOT_TOKEN", "BASE_URL", "SESSION_SECRET_KEY", "DB_URL"]
    snapshot = {key: os.environ.get(key) for key in env_keys}

    db_path = tmp_path / "ui-dashboard.db"

    try:
        os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
        os.environ["BASE_URL"] = "https://example.test"
        os.environ["SESSION_SECRET_KEY"] = "secret"
        os.environ["DB_URL"] = f"sqlite:///{db_path}"

        deps._engine_instance = None  # type: ignore[attr-defined]
        engine = deps.get_engine()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        with SessionLocal(bind=engine) as session:
            user = User(username="owner")
            session.add(user)
            session.flush()

            project = Project(user_id=user.id, name="Alpha", status=ProjectStatus.ACTIVE)
            session.add(project)
            session.flush()

            accounts = [
                Account(
                    project_id=project.id,
                    phone="+7900000001",
                    session_enc=b"",
                    status=AccountStatus.ACTIVE,
                ),
                Account(
                    project_id=project.id,
                    phone="+7900000002",
                    session_enc=b"",
                    status=AccountStatus.NEEDS_LOGIN,
                ),
            ]
            session.add_all(accounts)

            channels = [
                Channel(project_id=project.id, title="Канал 1"),
                Channel(project_id=project.id, title="Канал 2"),
            ]
            session.add_all(channels)

            tasks = [
                Task(
                    project_id=project.id,
                    name="Warmup",
                    status=TaskStatus.ON,
                    mode=TaskMode.NEW_POSTS,
                ),
                Task(
                    project_id=project.id,
                    name="Archive",
                    status=TaskStatus.OFF,
                    mode=TaskMode.NEW_POSTS,
                ),
            ]
            session.add_all(tasks)
            session.commit()

        client = TestClient(main.app)
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "Всего проектов" in html
        assert "Alpha" in html
        assert 'data-testid="total-projects">1<' in html
        assert 'data-testid="total-accounts">2<' in html
        assert 'data-testid="active-tasks">1<' in html
        assert 'data-testid="total-channels">2<' in html
    finally:
        deps._engine_instance = None  # type: ignore[attr-defined]
        _restore_env(snapshot)
        if db_path.exists():
            db_path.unlink()
