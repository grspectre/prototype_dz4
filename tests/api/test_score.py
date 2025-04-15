# tests/api/test_score.py
import pytest
import io
import csv
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Grade, Student, Faculty, Course, UserRoles
from app.core.security import get_password_hash


@pytest.fixture
async def test_data(async_session: AsyncSession):
    """Create test data for score tests"""
    # Create faculties
    cs_faculty = Faculty(name="Computer Science")
    math_faculty = Faculty(name="Mathematics")
    async_session.add_all([cs_faculty, math_faculty])
    await async_session.commit()

    # Create courses
    python_course = Course(name="Python Programming")
    database_course = Course(name="Database Systems")
    calculus_course = Course(name="Calculus")
    async_session.add_all([python_course, database_course, calculus_course])
    await async_session.commit()

    # Create students
    alice = Student(first_name="Alice", last_name="Smith", faculty_id=cs_faculty.id)
    bob = Student(first_name="Bob", last_name="Johnson", faculty_id=cs_faculty.id)
    charlie = Student(
        first_name="Charlie", last_name="Williams", faculty_id=math_faculty.id
    )
    async_session.add_all([alice, bob, charlie])
    await async_session.commit()

    # Create grades
    grade1 = Grade(student_id=alice.id, course_id=python_course.id, score=95)
    grade2 = Grade(student_id=alice.id, course_id=database_course.id, score=88)
    grade3 = Grade(student_id=bob.id, course_id=python_course.id, score=75)
    grade4 = Grade(student_id=charlie.id, course_id=calculus_course.id, score=92)
    async_session.add_all([grade1, grade2, grade3, grade4])
    await async_session.commit()

    # Return references to created objects for use in tests
    return {
        "faculties": {"cs": cs_faculty, "math": math_faculty},
        "courses": {
            "python": python_course,
            "database": database_course,
            "calculus": calculus_course,
        },
        "students": {"alice": alice, "bob": bob, "charlie": charlie},
        "grades": [grade1, grade2, grade3, grade4],
    }


@pytest.fixture
def admin_auth_headers(auth_headers):
    """Use the existing auth_headers fixture for admin user authentication"""
    return auth_headers


@pytest.fixture
async def create_csv_file():
    """Create a test CSV file for import testing"""

    def _create_csv(data):
        csv_file = io.StringIO()
        writer = csv.writer(csv_file)
        writer.writerow(["Фамилия", "Имя", "Факультет", "Курс", "Оценка"])
        for row in data:
            writer.writerow(row)
        csv_file.seek(0)
        content = csv_file.read()
        return io.BytesIO(content.encode("utf8"))

    return _create_csv


class TestImportCSV:
    async def test_import_csv_success(
        self, async_client: AsyncClient, create_csv_file, async_session: AsyncSession
    ):
        """Test successful CSV import"""
        # Prepare test data
        csv_data = [
            ["Brown", "David", "Physics", "Quantum Mechanics", "85"],
            ["Davis", "Emma", "Chemistry", "Organic Chemistry", "92"],
        ]
        csv_file = create_csv_file(csv_data)

        # Make the request
        files = {"file": ("test.csv", csv_file, "text/csv")}
        response = await async_client.post("/api/v1/score/import-csv", files=files)

        # Assertions
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)
        assert response_data["status"] is True
        assert "Imported records: 2" in response_data["message"]

        # Verify data was saved to database
        # Check faculty was created
        physics_faculty = await async_session.execute(
            select(Faculty).where(Faculty.name == "Physics")
        )
        physics_faculty = physics_faculty.scalar_one_or_none()
        print(physics_faculty)
        assert physics_faculty is not None

        # Check student was created
        count_students = await async_session.execute(select(func.count(Student.id)))
        count_students = count_students.scalar_one_or_none()
        assert count_students == 2

        # Check student was created
        david = await async_session.execute(
            select(Student)
            .where(Student.first_name == "David")
            .where(Student.last_name == "Brown")
        )
        david = david.scalar_one_or_none()
        assert david is not None
        assert david.faculty_id == physics_faculty.id

        # Check course was created
        quantum = await async_session.execute(
            select(Course).where(Course.name == "Quantum Mechanics")
        )
        quantum = quantum.scalar_one_or_none()
        assert quantum is not None

        # Check grade was created
        david_grade = await async_session.execute(
            select(Grade)
            .where(Grade.student_id == david.id)
            .where(Grade.course_id == quantum.id)
        )
        david_grade = david_grade.scalar_one_or_none()
        assert david_grade is not None
        assert david_grade.score == 85

    async def test_import_csv_invalid_format(self, async_client: AsyncClient):
        """Test CSV import fails with invalid CSV format"""
        # Create an invalid CSV file (missing required columns)
        csv_file = io.BytesIO(b"name,score\nJohn,85\nJane,92")
        csv_file.seek(0)

        # Make the request
        files = {"file": ("invalid.csv", csv_file, "text/csv")}
        response = await async_client.post("/api/v1/score/import-csv", files=files)

        # Assertions
        assert response.status_code == 500
        assert "detail" in response.json()


class TestDeleteScore:
    async def test_delete_score_success(
        self,
        async_client: AsyncClient,
        test_data,
        admin_auth_headers,
        async_session: AsyncSession,
    ):
        """Test successful score deletion"""
        # Choose a grade to delete
        grade_to_delete = test_data["grades"][0]

        # Make the request
        response = await async_client.delete(
            f"/api/v1/score/{grade_to_delete.id}", headers=admin_auth_headers
        )

        # Assertions
        assert response.status_code == 204

        # Verify grade was deleted from database
        grade_check = await async_session.execute(
            select(Grade).where(Grade.id == grade_to_delete.id)
        )
        deleted_grade = grade_check.scalar_one_or_none()
        assert deleted_grade is None

    async def test_delete_score_not_found(
        self, async_client: AsyncClient, admin_auth_headers
    ):
        """Test deletion fails with non-existent score ID"""
        # Use a non-existent ID
        non_existent_id = 9999

        # Make the request
        response = await async_client.delete(
            f"/api/v1/score/{non_existent_id}", headers=admin_auth_headers
        )

        # Assertions
        assert response.status_code == 404
        assert f"Score with ID {non_existent_id} not found" in response.json()["detail"]

    async def test_delete_score_unauthorized(
        self, async_client: AsyncClient, test_data
    ):
        """Test deletion fails without authentication"""
        # Choose a grade to delete
        grade_to_delete = test_data["grades"][0]

        # Make the request without auth headers
        response = await async_client.delete(f"/api/v1/score/{grade_to_delete.id}")

        # Assertions
        assert response.status_code == 403


class TestCreateScore:
    async def test_create_score_success(
        self, async_client: AsyncClient, admin_auth_headers, async_session: AsyncSession
    ):
        """Test successful score creation"""
        # Prepare score data
        score_data = {
            "first_name": "Frank",
            "last_name": "Miller",
            "faculty": "Economics",
            "course": "Macroeconomics",
            "score": 88,
        }

        # Make the request
        response = await async_client.post(
            "/api/v1/score", json=score_data, headers=admin_auth_headers
        )

        # Assertions
        assert response.status_code == 201
        created_score = response.json()
        assert created_score["first_name"] == score_data["first_name"]
        assert created_score["last_name"] == score_data["last_name"]
        assert created_score["faculty"] == score_data["faculty"]
        assert created_score["course"] == score_data["course"]
        assert created_score["score"] == score_data["score"]
        assert "id" in created_score

        # Verify data was saved to database
        # Check faculty was created
        econ_faculty = await async_session.execute(
            select(Faculty).where(Faculty.name == "Economics")
        )
        econ_faculty = econ_faculty.scalar_one_or_none()
        assert econ_faculty is not None

        # Check student was created
        frank = await async_session.execute(
            select(Student)
            .where(Student.first_name == "Frank")
            .where(Student.last_name == "Miller")
        )
        frank = frank.scalar_one_or_none()
        assert frank is not None
        assert frank.faculty_id == econ_faculty.id

        # Check course was created
        macro = await async_session.execute(
            select(Course).where(Course.name == "Macroeconomics")
        )
        macro = macro.scalar_one_or_none()
        assert macro is not None

        # Check grade was created
        frank_grade = await async_session.execute(
            select(Grade)
            .where(Grade.student_id == frank.id)
            .where(Grade.course_id == macro.id)
        )
        frank_grade = frank_grade.scalar_one_or_none()
        assert frank_grade is not None
        assert frank_grade.score == 88

    async def test_create_score_invalid_data(
        self, async_client: AsyncClient, admin_auth_headers
    ):
        """Test score creation fails with invalid data"""
        # Prepare invalid score data (missing required fields)
        invalid_score_data = {
            "first_name": "Frank",
            "last_name": "Miller",
            # Missing faculty
            "course": "Macroeconomics",
            "score": 88,
        }

        # Make the request
        response = await async_client.post(
            "/api/v1/score", json=invalid_score_data, headers=admin_auth_headers
        )

        # Assertions
        assert response.status_code == 422  # Validation error

    async def test_create_score_unauthorized(self, async_client: AsyncClient):
        """Test score creation fails without authentication"""
        score_data = {
            "first_name": "Frank",
            "last_name": "Miller",
            "faculty": "Economics",
            "course": "Macroeconomics",
            "score": 88,
        }

        # Make the request without auth headers
        response = await async_client.post("/api/v1/score", json=score_data)

        # Assertions
        assert response.status_code == 403


class TestListScores:
    async def test_list_scores_no_filters(self, async_client: AsyncClient, test_data):
        """Test listing all scores without filters"""
        # Make the request
        response = await async_client.get("/api/v1/score")

        # Assertions
        assert response.status_code == 200
        response_data = response.json()
        assert "items" in response_data
        assert "total" in response_data
        assert response_data["total"] == len(test_data["grades"])
        assert len(response_data["items"]) == len(test_data["grades"])

        # Verify data structure
        first_item = response_data["items"][0]
        assert "id" in first_item
        assert "first_name" in first_item
        assert "last_name" in first_item
        assert "faculty" in first_item
        assert "course" in first_item
        assert "score" in first_item

    async def test_list_scores_faculty_filter(
        self, async_client: AsyncClient, test_data
    ):
        """Test listing scores filtered by faculty"""
        # Filter by CS faculty
        cs_faculty = test_data["faculties"]["cs"]

        # Count expected results
        expected_count = 0
        for grade in test_data["grades"]:
            if grade.student.faculty_id == cs_faculty.id:
                expected_count += 1

        # Make the request
        response = await async_client.get(f"/api/v1/score?faculty={cs_faculty.name}")

        # Assertions
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["total"] == expected_count
        assert len(response_data["items"]) == expected_count

        # Check all items have the correct faculty
        for item in response_data["items"]:
            assert item["faculty"] == cs_faculty.name

    async def test_list_scores_course_filter(
        self, async_client: AsyncClient, test_data
    ):
        """Test listing scores filtered by course"""
        # Filter by Python course
        python_course = test_data["courses"]["python"]

        # Count expected results
        expected_count = 0
        for grade in test_data["grades"]:
            if grade.course_id == python_course.id:
                expected_count += 1

        # Make the request
        response = await async_client.get(f"/api/v1/score?course={python_course.name}")

        # Assertions
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["total"] == expected_count
        assert len(response_data["items"]) == expected_count

        # Check all items have the correct course
        for item in response_data["items"]:
            assert item["course"] == python_course.name

    async def test_list_scores_combined_filters(
        self, async_client: AsyncClient, test_data
    ):
        """Test listing scores with both faculty and course filters"""
        # Filter by CS faculty and Python course
        cs_faculty = test_data["faculties"]["cs"]
        python_course = test_data["courses"]["python"]

        # Count expected results
        expected_count = 0
        for grade in test_data["grades"]:
            if (
                grade.student.faculty_id == cs_faculty.id
                and grade.course_id == python_course.id
            ):
                expected_count += 1

        # Make the request
        response = await async_client.get(
            f"/api/v1/score?faculty={cs_faculty.name}&course={python_course.name}"
        )

        # Assertions
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["total"] == expected_count
        assert len(response_data["items"]) == expected_count

        # Check all items have the correct faculty and course
        for item in response_data["items"]:
            assert item["faculty"] == cs_faculty.name
            assert item["course"] == python_course.name

    async def test_list_scores_pagination(self, async_client: AsyncClient, test_data):
        """Test score listing with pagination"""
        # Set pagination parameters
        skip = 1
        limit = 2

        # Make the request
        response = await async_client.get(f"/api/v1/score?skip={skip}&limit={limit}")

        # Assertions
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data["items"]) <= limit

        # Get all scores for comparison
        all_response = await async_client.get("/api/v1/score")
        all_data = all_response.json()

        # Verify the items are the correct subset
        assert response_data["items"] == all_data["items"][skip : skip + limit]

    async def test_create_score(
        self, async_client: AsyncClient, test_data, auth_headers: dict
    ):
        """Test creating a new score"""
        # Get student and course to use
        student = test_data["students"]["alice"]
        course = test_data["courses"]["python"]
        faculty = test_data["faculties"]["cs"]

        # Data for new score
        score_data = {
            "score": 95,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "faculty": faculty.name,
            "course": course.name,
        }

        # Make the request
        response = await async_client.post(
            "/api/v1/score", json=score_data, headers=auth_headers
        )

        # Assertions
        assert response.status_code == 201
        created_score = response.json()
        assert created_score["score"] == score_data["score"]
        assert created_score["first_name"] == score_data["first_name"]
        assert created_score["last_name"] == score_data["last_name"]
        assert created_score["faculty"] == score_data["faculty"]
        assert created_score["course"] == score_data["course"]
        assert "id" in created_score

    async def test_delete_score(self, async_client: AsyncClient, test_data, auth_headers: dict):
        """Test deleting a score"""
        # Get a score to delete
        grade = test_data["grades"][0]

        # Make the request
        response = await async_client.delete(f"/api/v1/score/{grade.id}", headers=auth_headers)

        # Assertions
        assert response.status_code == 204
