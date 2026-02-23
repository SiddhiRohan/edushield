# QuantumLeap - seed database with sample data
import asyncio
from passlib.context import CryptContext
from sqlalchemy import select
from .database import init_db, async_session
from .models import Person, FinancialInfo, Class, Grade, Enrollment

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed():
    await init_db()
    async with async_session() as session:
        # Check if already seeded
        r = await session.execute(select(Person).limit(1))
        if r.scalar_one_or_none():
            print("Database already seeded. Skip.")
            return

        # Persons: 1 admin, 2 teachers, 3 students
        admin = Person(
            username="admin",
            password_hash=pwd_context.hash("admin123"),
            role="admin",
            full_name="Admin User",
        )
        t1 = Person(
            username="teacher1",
            password_hash=pwd_context.hash("teach1"),
            role="teacher",
            full_name="Alice Teacher",
        )
        t2 = Person(
            username="teacher2",
            password_hash=pwd_context.hash("teach2"),
            role="teacher",
            full_name="Bob Teacher",
        )
        s1 = Person(
            username="student1",
            password_hash=pwd_context.hash("stu1"),
            role="student",
            full_name="Charlie Student",
        )
        s2 = Person(
            username="student2",
            password_hash=pwd_context.hash("stu2"),
            role="student",
            full_name="Diana Student",
        )
        s3 = Person(
            username="student3",
            password_hash=pwd_context.hash("stu3"),
            role="student",
            full_name="Eve Student",
        )
        session.add_all([admin, t1, t2, s1, s2, s3])
        await session.flush()  # get IDs

        # Classes
        c1 = Class(name="Introduction to AI", code="CS101")
        c2 = Class(name="Data Privacy", code="CS102")
        c3 = Class(name="Ethics in Tech", code="PHIL201")
        session.add_all([c1, c2, c3])
        await session.flush()

        # Enrollments: s1 in c1,c2; s2 in c2,c3; s3 in c1,c3
        session.add_all([
            Enrollment(person_id=s1.id, class_id=c1.id),
            Enrollment(person_id=s1.id, class_id=c2.id),
            Enrollment(person_id=s2.id, class_id=c2.id),
            Enrollment(person_id=s2.id, class_id=c3.id),
            Enrollment(person_id=s3.id, class_id=c1.id),
            Enrollment(person_id=s3.id, class_id=c3.id),
        ])

        # Grades (teacher can see these)
        session.add_all([
            Grade(person_id=s1.id, class_id=c1.id, grade_value="A"),
            Grade(person_id=s1.id, class_id=c2.id, grade_value="B"),
            Grade(person_id=s2.id, class_id=c2.id, grade_value="A"),
            Grade(person_id=s2.id, class_id=c3.id, grade_value="B+"),
            Grade(person_id=s3.id, class_id=c1.id, grade_value="B"),
            Grade(person_id=s3.id, class_id=c3.id, grade_value="A"),
        ])

        # Financial: student payments and teacher salaries
        session.add_all([
            FinancialInfo(person_id=s1.id, kind="student_payment", amount=5000.0, description="Fall 2025"),
            FinancialInfo(person_id=s2.id, kind="student_payment", amount=5000.0, description="Fall 2025"),
            FinancialInfo(person_id=s3.id, kind="student_payment", amount=5000.0, description="Fall 2025"),
            FinancialInfo(person_id=t1.id, kind="employee_salary", amount=75000.0, description="Annual"),
            FinancialInfo(person_id=t2.id, kind="employee_salary", amount=72000.0, description="Annual"),
        ])
        await session.commit()
    print("Seed completed.")


if __name__ == "__main__":
    asyncio.run(seed())
