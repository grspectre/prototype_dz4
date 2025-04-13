import csv
from app.db.session import AsyncSession
from app.db.base import Faculty, Student, Course, Grade
from sqlalchemy import select


class ScoreRepository:
    session: AsyncSession

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_student(
        self,
        name: str,
        last_name: str,
        faculty: Faculty
    ) -> Student:
        query = select(Student).filter_by(
            last_name=last_name, first_name=name, faculty_id=faculty.id
        )
        response = await self.session.execute(query)
        student = response.scalar_one_or_none()

        if not student:
            student = Student(
                last_name=last_name, first_name=name, faculty_id=faculty.id
            )
            self.session.add(student)
            await self.session.flush()
            await self.session.refresh(student)
        return student

    async def get_faculty(self, name: str) -> Faculty:
        query = select(Faculty).filter_by(name=name)
        response = await self.session.execute(query)
        faculty = response.scalar_one_or_none()
        if not faculty:
            faculty = Faculty(name=name)
            self.session.add(faculty)
            await self.session.flush()
            await self.session.refresh(faculty)
        return faculty

    async def get_course(self, name: str) -> Course:
        query = select(Course).filter_by(name=name)
        response = await self.session.execute(query)
        course = response.scalar_one_or_none()
        if not course:
            course = Course(name=name)
            self.session.add(course)
            await self.session.flush()
            await self.session.refresh(course)
        return course

    async def add_or_update_grade(
        self, score: int, student: Student, course: Course
    ) -> Grade:
        query = select(Grade).filter_by(
            student_id=student.id,
            course_id=course.id
        )
        response = await self.session.execute(query)
        grade_obj = response.scalar_one_or_none()

        if not grade_obj:
            # Create new grade
            grade_obj = Grade(
                student_id=student.id,
                course_id=course.id,
                score=score
            )
            self.session.add(grade_obj)
        else:
            # Update existing grade
            grade_obj.score = score

        await self.session.flush()
        await self.session.refresh(grade_obj)
        return grade_obj

    async def import_from_csv(self, file_path, empty=False):
        count = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    faculty = await self.get_faculty(row["Факультет"])
                    student = await self.get_student(
                        row["Имя"], row["Фамилия"], faculty
                    )
                    course = await self.get_course(row["Курс"])
                    grd = int(row["Оценка"])
                    await self.add_or_update_grade(grd, student, course)
                    count += 1
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            raise e
        finally:
            await self.session.close()
        return count

    async def add_score(
        self, first_name: str,
        last_name: str,
        faculty: str,
        course: str,
        score: int
    ):
        faculty = await self.get_faculty(faculty)
        student = await self.get_student(first_name, last_name, faculty)
        course = await self.get_course(course)
        return await self.add_or_update_grade(score, student, course)
