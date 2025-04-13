# app/api/endpoints/user.py
import os
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Path,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.base import User, get_score_by_id, Student, Faculty, Course, Grade
from app.schemas.schemas import (
    ImportCSVResponse,
    ScoreListResponse,
    ScoreResponse,
    ScoreCreate,
    ErrorResponse,
    ScoreFilterParams,
)
from app.db.repository import ScoreRepository
from app.core.security import get_current_user

router = APIRouter()


@router.post(
    "/import-csv",
    response_model=ImportCSVResponse,
    status_code=status.HTTP_200_OK
)
async def import_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Импорт данных из CSV-файла"""
    repo = ScoreRepository(db)
    try:
        file_location = f"temp_{file.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(file.file.read())

        count = await repo.import_from_csv(file_location)
        os.remove(file_location)
        m = f"Imported records: {count}"
        params = dict(
            status=True,
            message=m,
        )
        return ImportCSVResponse.model_validate(params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{score_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def delete_score(
    score_id: int = Path(..., title="The ID of the promotion to delete"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    score = await get_score_by_id(db, score_id)

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Score with ID {score_id} not found",
        )

    db.delete(score)
    await db.flush()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "",
    response_model=ScoreResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    },
)
async def create_score(
    score: ScoreCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ScoreRepository(db)
    grade = repo.add_score(
        score.first_name,
        score.last_name,
        score.faculty,
        score.course,
        score.score
    )
    await db.commit()

    params = score.model_dump()
    params["id"] = grade.id
    return ScoreResponse.model_validate(params)


@router.get(
    "",
    response_model=ScoreListResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    },
)
async def list_scores(
    filter_params: ScoreFilterParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    List all scores with filtering options.
    Can filter by faculty or course.
    """
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload

    # Modified query to select Grade objects (not Student objects)
    # and load the required relationships
    query = select(Grade).options(
        selectinload(Grade.student).selectinload(Student.faculty),
        selectinload(Grade.course),
    )

    count_query = select(func.count(Grade.id))

    # Apply filters
    if filter_params.faculty:
        query = query.join(Grade.student).join(Student.faculty)
        count_query = count_query.join(Grade.student).join(Student.faculty)
        condition = Faculty.name == filter_params.faculty
        query = query.where(condition)
        count_query = count_query.where(condition)

    if filter_params.course:
        query = query.join(Grade.course)
        count_query = count_query.join(Grade.course)
        # Fix typo: filter_params.faculty -> filter_params.course
        condition = Course.name == filter_params.course
        query = query.where(condition)
        count_query = count_query.where(condition)

    # Pagination
    total = await db.execute(count_query)
    total_count = total.scalar() or 0

    query = query.offset(filter_params.skip).limit(filter_params.limit)

    # Execute query
    result = await db.execute(query)
    grades = result.scalars().all()

    # Convert Grade objects to ScoreResponse objects
    score_responses = [
        ScoreResponse(
            id=grade.id,
            first_name=grade.student.first_name,
            last_name=grade.student.last_name,
            faculty=grade.student.faculty.name,
            course=grade.course.name,
            score=grade.score,
        )
        for grade in grades
    ]

    return ScoreListResponse(items=score_responses, total=total_count)
