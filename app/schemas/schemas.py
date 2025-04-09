from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional

# Faculty schemas
class FacultyBase(BaseModel):
    name: str

class FacultyCreate(FacultyBase):
    pass

class Faculty(FacultyBase):
    id: int
    
    model_config = ConfigDict(
        orm_mode=True,
    )

# Course schemas
class CourseBase(BaseModel):
    name: str

class CourseCreate(CourseBase):
    pass

class Course(CourseBase):
    id: int
    
    model_config = ConfigDict(
        orm_mode=True,
    )

# Grade schemas 
class GradeBase(BaseModel):
    student_id: int
    course_id: int
    score: int = Field(..., ge=0, le=100)  # Предполагаем, что оценка от 0 до 100
    
    @field_validator('score')
    def validate_score(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Score must be between 0 and 100')
        return v

class GradeCreate(GradeBase):
    pass

class Grade(GradeBase):
    id: int
    
    model_config = ConfigDict(
        orm_mode=True,
    )

# Student schemas
class StudentBase(BaseModel):
    first_name: str
    last_name: str
    faculty_id: int

class StudentCreate(StudentBase):
    pass

class Student(StudentBase):
    id: int
    
    model_config = ConfigDict(
        orm_mode=True,
    )

# Расширенные схемы для получения связанных данных
class StudentWithGrades(Student):
    grades: List[Grade] = []
    
    model_config = ConfigDict(
        orm_mode=True,
    )

class CourseWithGrades(Course):
    grades: List[Grade] = []
    
    model_config = ConfigDict(
        orm_mode=True,
    )

class FacultyWithStudents(Faculty):
    students: List[Student] = []
    
    model_config = ConfigDict(
        orm_mode=True,
    )
