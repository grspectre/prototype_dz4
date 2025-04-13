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
        from_attributes=True,
    )


# Course schemas
class CourseBase(BaseModel):
    name: str


class CourseCreate(CourseBase):
    pass


class Course(CourseBase):
    id: int

    model_config = ConfigDict(
        from_attributes=True,
    )


# Grade schemas
class GradeBase(BaseModel):
    student_id: int
    course_id: int
    score: int = Field(..., ge=0, le=100)

    @field_validator("score")
    def validate_score(cls, v):
        if v < 0 or v > 100:
            raise ValueError("Score must be between 0 and 100")
        return v


class GradeCreate(GradeBase):
    pass


class Grade(GradeBase):
    id: int

    model_config = ConfigDict(
        from_attributes=True,
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
        from_attributes=True,
    )


# Расширенные схемы для получения связанных данных
class StudentWithGrades(Student):
    grades: List[Grade] = []

    model_config = ConfigDict(
        from_attributes=True,
    )


class CourseWithGrades(Course):
    grades: List[Grade] = []

    model_config = ConfigDict(
        from_attributes=True,
    )


class FacultyWithStudents(Faculty):
    students: List[Student] = []

    model_config = ConfigDict(
        from_attributes=True,
    )


class ImportCSVResponse(BaseModel):
    status: bool
    message: str

    model_config = ConfigDict(
        from_attributes=True,
    )


# Score models
class ScoreBase(BaseModel):
    first_name: str
    last_name: str
    faculty: str
    course: str
    score: int


class ScoreResponse(ScoreBase):
    id: int


class ScoreListResponse(BaseModel):
    items: List[ScoreResponse]
    total: int


class ScoreCreate(ScoreBase):
    pass


# Query parameters for filtering promotions
class ScoreFilterParams(BaseModel):
    faculty: Optional[str] = None
    course: Optional[str] = None
    skip: Optional[int] = 0
    limit: Optional[int] = 100


class ErrorResponse(BaseModel):
    detail: str
