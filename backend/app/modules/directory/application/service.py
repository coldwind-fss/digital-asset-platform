from __future__ import annotations

from typing import TypeVar

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.platform.db.models import Company, Department, Person

Model = TypeVar("Model", Person, Department, Company)


def _page(statement: Select, session: Session, *, page: int, page_size: int) -> tuple[list[object], int]:
    total = int(session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    rows = list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all())
    return rows, total


def list_people(session: Session, *, q: str | None, page: int, page_size: int) -> tuple[list[Person], int]:
    statement = select(Person).order_by(Person.display_name.asc(), Person.id.asc())
    if q:
        needle = f"%{q.strip()}%"
        statement = statement.where(or_(Person.display_name.ilike(needle), Person.stable_external_id.ilike(needle)))
    rows, total = _page(statement, session, page=page, page_size=page_size)
    return [row for row in rows if isinstance(row, Person)], total


def list_departments(session: Session, *, q: str | None, page: int, page_size: int) -> tuple[list[Department], int]:
    statement = select(Department).order_by(Department.name.asc(), Department.id.asc())
    if q:
        statement = statement.where(Department.name.ilike(f"%{q.strip()}%"))
    rows, total = _page(statement, session, page=page, page_size=page_size)
    return [row for row in rows if isinstance(row, Department)], total


def list_companies(session: Session, *, q: str | None, page: int, page_size: int) -> tuple[list[Company], int]:
    statement = select(Company).order_by(Company.name.asc(), Company.id.asc())
    if q:
        statement = statement.where(Company.name.ilike(f"%{q.strip()}%"))
    rows, total = _page(statement, session, page=page, page_size=page_size)
    return [row for row in rows if isinstance(row, Company)], total
