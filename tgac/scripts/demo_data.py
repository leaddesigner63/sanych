from __future__ import annotations

from sqlalchemy.orm import Session

from ..api.deps import SessionLocal
from ..api.models.core import Project, User, UserRole


def create_demo() -> None:
    with SessionLocal() as session:  # type: Session
        admin = session.query(User).filter_by(username="admin").one_or_none()
        if not admin:
            admin = User(username="admin", role=UserRole.ADMIN)
            session.add(admin)
            session.commit()
        if not session.query(Project).filter_by(name="Demo Project").one_or_none():
            project = Project(user_id=admin.id, name="Demo Project")
            session.add(project)
            session.commit()


if __name__ == "__main__":  # pragma: no cover
    create_demo()
