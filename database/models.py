# QuantumLeap - database models
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship, declarative_base
import enum


Base = declarative_base()


class Role(str, enum.Enum):
    admin = "admin"
    teacher = "teacher"
    student = "student"


class Person(Base):
    __tablename__ = "persons"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False)  # admin, teacher, student
    full_name = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Person(id={self.id}, username={self.username}, role={self.role})>"


class FinancialInfo(Base):
    __tablename__ = "financial_info"
    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    kind = Column(String(20), nullable=False)  # student_payment | employee_salary
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person", backref="financial_records")

    def __repr__(self):
        return f"<FinancialInfo(id={self.id}, person_id={self.person_id}, kind={self.kind})>"


class Class(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    code = Column(String(32), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Class(id={self.id}, code={self.code})>"


class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    grade_value = Column(String(10), nullable=True)  # A, B, C, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person", backref="grades")
    class_ = relationship("Class", backref="grades")

    def __repr__(self):
        return f"<Grade(person_id={self.person_id}, class_id={self.class_id})>"


# Enrollment: which students are in which classes (for "students can access their own classes")
class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person", backref="enrollments")
    class_ = relationship("Class", backref="enrollments")
