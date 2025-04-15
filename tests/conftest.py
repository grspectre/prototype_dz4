import pytest
import os
import sys
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.db.base import Base, UserToken, User
from app.main import app
from app.db.session import get_db
from fastapi import FastAPI
from app.core.security import create_access_token, get_password_hash
from datetime import timedelta
from sqlalchemy import select

if "DATABASE_URL" in os.environ:
    TEST_DATABASE_URL = os.environ["DATABASE_URL"]
else:
    TEST_DATABASE_URL = "postgresql+asyncpg://pws:pws@localhost:5432/db_dz_test"


@pytest.fixture(scope="function")
async def async_engine():
    """Create an async engine for testing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def async_session(async_engine):
    """Create an async session for testing."""
    async_session_maker = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session
        await session.rollback()  # Roll back any changes after the test


@pytest.fixture(scope="function")
async def override_get_db(async_session):
    """Override the get_db dependency to use the test session."""

    async def _override_get_db():
        try:
            yield async_session
        finally:
            await async_session.commit()  # Commit any changes for the test

    return _override_get_db


@pytest.fixture(scope="function")
async def async_client(app, override_get_db):
    """Create an async client for testing."""
    app.dependency_overrides[get_db] = override_get_db
    # For httpx AsyncClient to test against a FastAPI app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.app = app
        yield client
    app.dependency_overrides = {}


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Create a FastAPI app instance for testing."""
    from app.main import app

    return app


@pytest.fixture(autouse=True, scope="session")
def configure_sqlalchemy_for_tests():
    for mapper in Base.registry.mappers:
        if mapper.class_ == UserToken:
            mapper.confirm_deleted_rows = False
    yield


@pytest.fixture(scope="function")
async def session_user_token(async_session: AsyncSession) -> str:
    access_token = None
    login = "test_session"

    query = select(User).where(User.username == login)
    response = await async_session.execute(query)
    db_user = response.scalar_one_or_none()

    if db_user is None:
        email = "test_session@example.com"
        passwd = "testpassword"
        hashed_password, salt = get_password_hash(passwd)

        db_user = User(
            username=login,
            email=email,
            name="test_session",
            last_name="test_session",
            password=hashed_password,
            salt=salt,
        )

        async_session.add(db_user)
        await async_session.commit()
        await async_session.refresh(db_user)

        access_token_expires = timedelta(hours=2)

    query = select(UserToken).where(UserToken.user_id == db_user.user_id)
    response = await async_session.execute(query)
    token = response.scalar_one_or_none()

    if token is None:
        access_token, expires_at = create_access_token(
            data={
                "sub": str(db_user.user_id),
                "roles": [role.value for role in db_user.roles],
            },
            expires_delta=access_token_expires,
        )

        token = UserToken(user_id=db_user.user_id, expired_at=expires_at)
        async_session.add(token)
        await async_session.commit()
        await async_session.refresh(token)

        access_token = token.token_id
    return access_token


@pytest.fixture(scope="function")
async def session_user(async_session: AsyncSession) -> User:
    login = "test_session"

    query = select(User).where(User.username == login)
    response = await async_session.execute(query)
    db_user = response.scalar_one_or_none()

    if db_user is None:
        email = "test_session@example.com"
        passwd = "testpassword"
        hashed_password, salt = get_password_hash(passwd)

        db_user = User(
            username=login,
            email=email,
            name="test_session",
            last_name="test_session",
            password=hashed_password,
            salt=salt,
        )

        async_session.add(db_user)
        await async_session.commit()
        await async_session.refresh(db_user)
    return db_user


@pytest.fixture(scope="function")
def auth_headers(session_user_token: str) -> dict:
    return {"Authorization": f"Bearer {session_user_token}"}
