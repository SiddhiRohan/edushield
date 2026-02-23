# QuantumLeap - Role-scoped data access (least privilege)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Person, FinancialInfo, Class, Grade, Enrollment
from iccp import (
    RESOURCE_PERSONS,
    RESOURCE_FINANCIAL,
    RESOURCE_GRADES,
    RESOURCE_CLASSES,
    IdentityScope,
)
from iccp.resources import RESOURCE_DESCRIPTORS


async def get_person_id_by_username(session: AsyncSession, username: str) -> int | None:
    r = await session.execute(select(Person.id).where(Person.username == username))
    return r.scalar_one_or_none()


async def get_classes_for_identity(session: AsyncSession, identity: IdentityScope, person_id: int) -> list[dict]:
    """Classes: admin/teacher all; student only their enrollments."""
    if identity.role == "admin" or identity.role == "teacher":
        r = await session.execute(select(Class))
        classes = r.scalars().all()
        return [{"id": c.id, "code": c.code, "name": c.name} for c in classes]
    # student: only classes they are enrolled in
    r = await session.execute(
        select(Class).join(Enrollment).where(Enrollment.person_id == person_id)
    )
    classes = r.scalars().unique().all()
    return [{"id": c.id, "code": c.code, "name": c.name} for c in classes]


async def get_grades_for_identity(session: AsyncSession, identity: IdentityScope, person_id: int) -> list[dict]:
    """Grades: admin all; teacher all; student only own (if we ever allow)."""
    if identity.role == "student":
        return []  # students cannot access grades per spec
    r = await session.execute(
        select(Grade, Person.username, Class.code)
        .join(Person, Grade.person_id == Person.id)
        .join(Class, Grade.class_id == Class.id)
    )
    rows = r.all()
    return [
        {"username": u, "class_code": c, "grade": g.grade_value}
        for g, u, c in rows
    ]


async def get_financial_for_identity(session: AsyncSession, identity: IdentityScope, person_id: int) -> list[dict]:
    """Financial: admin all; teacher only own salary; student none."""
    if identity.role == "student":
        return []
    if identity.role == "teacher":
        r = await session.execute(
            select(FinancialInfo).where(
                FinancialInfo.person_id == person_id,
                FinancialInfo.kind == "employee_salary",
            )
        )
        recs = r.scalars().all()
        return [{"kind": "employee_salary", "amount": rec.amount, "description": rec.description} for rec in recs]
    # admin: all
    r = await session.execute(
        select(FinancialInfo, Person.username).join(Person, FinancialInfo.person_id == Person.id)
    )
    rows = r.all()
    return [
        {"username": u, "kind": rec.kind, "amount": rec.amount, "description": rec.description}
        for rec, u in rows
    ]


async def get_persons_for_identity(session: AsyncSession, identity: IdentityScope) -> list[dict]:
    """Persons: admin only."""
    if identity.role != "admin":
        return []
    r = await session.execute(select(Person).where(True))
    persons = r.scalars().all()
    return [
        {"id": p.id, "username": p.username, "role": p.role, "full_name": p.full_name}
        for p in persons
    ]


async def gather_authorized_data(
    session: AsyncSession,
    identity: IdentityScope,
    authorized_resources: list[str],
    person_id: int,
) -> dict:
    """Fetch only data allowed by authorized_resources for this identity."""
    out = {}
    if RESOURCE_CLASSES in authorized_resources:
        out["classes"] = await get_classes_for_identity(session, identity, person_id)
    if RESOURCE_GRADES in authorized_resources:
        out["grades"] = await get_grades_for_identity(session, identity, person_id)
    if RESOURCE_FINANCIAL in authorized_resources:
        out["financial"] = await get_financial_for_identity(session, identity, person_id)
    if RESOURCE_PERSONS in authorized_resources:
        out["persons"] = await get_persons_for_identity(session, identity)
    return out
