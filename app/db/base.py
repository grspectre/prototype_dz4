import enum
import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, select
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship, declarative_base
from app.db.session import AsyncSession
from datetime import datetime as dt

Base = declarative_base()


async def get_user_by_id(session: AsyncSession, idx):
    stmt = select(User).where(User.user_id == idx)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_token(session: AsyncSession, token_id: str):
    stmt = select(UserToken).where(UserToken.token_id == token_id)
    result = await session.execute(stmt)
    token = result.scalar_one_or_none()
    if token is None:
        return None
    return get_user_by_id(session, token.user_id)

class UserRoles(str, enum.Enum):
    admin = "admin"
    user = "user"

class UserToken(Base):
    __tablename__ = "user_tokens"

    token_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expired_at = Column(DateTime, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))

    user = relationship("User", back_populates="user_tokens")

    def is_expired(self) -> bool:
        return self.expired_at < dt.now()

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True)
    name = Column(String(100))
    last_name = Column(String(150))
    password = Column(String(64))
    salt = Column(String(32))
    roles = Column(ARRAY(Enum(UserRoles)), nullable=False, default=[UserRoles.user])
    email = Column(String, unique=True, index=True)
    
    user_tokens = relationship("UserToken", back_populates="user")


class Faculty(Base):
    __tablename__ = 'faculties'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    
    students = relationship("Student", back_populates="faculty")
    
    def __repr__(self):
        return f"<Faculty(name='{self.name}')>"

class Student(Base):
    __tablename__ = 'students'
    
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    faculty_id = Column(Integer, ForeignKey('faculties.id'), nullable=False)
    
    faculty = relationship("Faculty", back_populates="students")
    grades = relationship("Grade", back_populates="student")
    
    def __repr__(self):
        return f"<Student(last_name='{self.last_name}', first_name='{self.first_name}')>"

class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    
    grades = relationship("Grade", back_populates="course")
    
    def __repr__(self):
        return f"<Course(name='{self.name}')>"

class Grade(Base):
    __tablename__ = 'grades'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    score = Column(Integer, nullable=False)
    
    student = relationship("Student", back_populates="grades")
    course = relationship("Course", back_populates="grades")
    
    def __repr__(self):
        return f"<Grade(student_id={self.student_id}, course_id={self.course_id}, score={self.score})>"
