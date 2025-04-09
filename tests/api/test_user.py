# tests/api/test_user.py
import pytest
import uuid
import logging
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import User, UserToken, UserRoles
from app.core.security import get_password_hash

LOGGER = logging.getLogger(__name__);

@pytest.fixture
async def test_user(async_session: AsyncSession):
    """Create a test user for login tests"""
    password = "testpassword123"
    hashed_password, salt = get_password_hash(password)
    
    user = User(
        username="testuser",
        email="test@example.com",
        name="Test",
        last_name="User",
        password=hashed_password,
        salt=salt,
        roles=[UserRoles.user]
    )
    
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    
    yield user, password  # Return both user object and raw password for testing
    
    # Cleanup
    await async_session.delete(user)
    await async_session.commit()


@pytest.fixture
async def admin_user(async_session: AsyncSession):
    """Create an admin user for tests requiring admin privileges"""
    password = "adminpassword123"
    hashed_password, salt = get_password_hash(password)
    
    user = User(
        username="adminuser",
        email="admin@example.com",
        name="Admin",
        last_name="User",
        password=hashed_password,
        salt=salt,
        roles=[UserRoles.admin, UserRoles.user]
    )
    
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    
    yield user, password
    
    # Cleanup
    await async_session.delete(user)
    await async_session.commit()


@pytest.fixture
async def user_token(async_session: AsyncSession, test_user):
    """Create a valid user token"""
    user, _ = test_user
    
    token = UserToken(
        token_id=uuid.uuid4(),
        user_id=user.user_id,
        expired_at=datetime.now() + timedelta(minutes=30)
    )
    
    async_session.add(token)
    await async_session.commit()
    await async_session.refresh(token)
    
    yield token
    
    # Cleanup
    await async_session.delete(token)
    await async_session.commit()


@pytest.fixture
async def expired_token(async_session: AsyncSession, test_user):
    """Create an expired user token"""
    user, _ = test_user
    
    token = UserToken(
        token_id=uuid.uuid4(),
        user_id=user.user_id,
        expired_at=datetime.now() - timedelta(minutes=5)  # Expired 5 minutes ago
    )
    
    async_session.add(token)
    await async_session.commit()
    await async_session.refresh(token)
    
    yield token
    
    # Cleanup
    await async_session.delete(token)
    await async_session.commit()


class TestUserRegistration:
    async def test_register_user_success(self, async_client: AsyncClient, async_session: AsyncSession):
        """Test successful user registration"""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "name": "New",
            "last_name": "User",
            "password": "password123"
        }
        
        response = await async_client.post("/api/v1/user/register", json=user_data)
        
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["username"] == user_data["username"]
        assert response_data["email"] == user_data["email"]
        assert response_data["name"] == user_data["name"]
        assert response_data["last_name"] == user_data["last_name"]
        assert "password" not in response_data
        assert "user_id" in response_data
        
        # Verify user was created in DB
        query = select(User).where(User.username == user_data["username"])
        result = await async_session.execute(query)
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        
        # Cleanup
        await async_session.delete(db_user)
        await async_session.commit()
    
    async def test_register_duplicate_username(self, async_client: AsyncClient, test_user):
        """Test registration fails with duplicate username"""
        user, _ = test_user
        
        user_data = {
            "username": user.username,  # Same username as existing test user
            "email": "different@example.com",
            "name": "New",
            "last_name": "User",
            "password": "password123"
        }
        
        response = await async_client.post("/api/v1/user/register", json=user_data)
        
        assert response.status_code == 400
        assert "Username already registered" in response.json()["detail"]
    
    async def test_register_duplicate_email(self, async_client: AsyncClient, test_user):
        """Test registration fails with duplicate email"""
        user, _ = test_user
        
        user_data = {
            "username": "differentuser",
            "email": user.email,  # Same email as existing test user
            "name": "New",
            "last_name": "User",
            "password": "password123"
        }
        
        response = await async_client.post("/api/v1/user/register", json=user_data)
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]


class TestUserLogin:
    async def test_login_success(self, async_client: AsyncClient, test_user, async_session: AsyncSession):
        """Test successful login"""
        user, password = test_user
        
        form_data = {
            "username": user.username,
            "password": password
        }
        
        response = await async_client.post("/api/v1/user/login", data=form_data)
        
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert "expires_at" in token_data
        
        # Verify token was created in DB
        query = select(UserToken).where(UserToken.user_id == user.user_id)
        result = await async_session.execute(query)
        db_token = result.scalar_one()
        assert db_token is not None
        
        # Cleanup
        await async_session.delete(db_token)
        await async_session.commit()
    
    async def test_login_wrong_username(self, async_client: AsyncClient):
        """Test login fails with wrong username"""
        form_data = {
            "username": "nonexistent",
            "password": "password123"
        }
        
        response = await async_client.post("/api/v1/user/login", data=form_data)
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    async def test_login_wrong_password(self, async_client: AsyncClient, test_user):
        """Test login fails with wrong password"""
        user, _ = test_user
        
        form_data = {
            "username": user.username,
            "password": "wrongpassword"
        }
        
        response = await async_client.post("/api/v1/user/login", data=form_data)
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]


class TestTokenRefresh:
    async def test_refresh_token_success(self, async_client: AsyncClient, user_token, async_session: AsyncSession):
        """Test successful token refresh"""
        # Create authorization header
        headers = {"Authorization": f"Bearer {user_token.token_id}"}
        
        response = await async_client.post("/api/v1/user/refresh-token", headers=headers)
        
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert "expires_at" in token_data
        
        # Verify token was updated in DB
        query = select(UserToken).where(UserToken.user_id == user_token.user_id)
        result = await async_session.execute(query)
        updated_token = result.scalar_one()
        assert updated_token is not None
        assert str(updated_token.token_id) == token_data["access_token"]
    
    async def test_refresh_token_expired(self, async_client: AsyncClient, expired_token, async_session: AsyncSession):
        """Test token refresh fails with expired token"""
        headers = {"Authorization": f"Bearer {expired_token.token_id}"}
        
        response = await async_client.post("/api/v1/user/refresh-token", headers=headers)
        
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert "expires_at" in token_data
        
        # Verify token was updated in DB
        query = select(UserToken).where(UserToken.user_id == expired_token.user_id)
        result = await async_session.execute(query)
        updated_token = result.scalar_one()
        assert updated_token is not None
        assert str(updated_token.token_id) == token_data["access_token"]
    
    async def test_refresh_token_invalid(self, async_client: AsyncClient):
        """Test token refresh fails with invalid token"""
        headers = {"Authorization": f"Bearer {uuid.uuid4()}"}
        
        response = await async_client.post("/api/v1/user/refresh-token", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]


class TestChangePassword:
    async def test_change_password_success(self, async_client: AsyncClient, test_user, user_token, async_session: AsyncSession):
        """Test successful password change"""
        user, old_password = test_user
        new_password = "newpassword123"
        
        headers = {"Authorization": f"Bearer {user_token.token_id}"}
        password_data = {
            "old_password": old_password,
            "new_password": new_password
        }
        
        response = await async_client.post("/api/v1/user/change-password", json=password_data, headers=headers)
        
        assert response.status_code == 200
        assert "Password updated successfully" in response.json()["detail"]
        
        # Verify all user tokens were deleted
        query = select(UserToken).where(UserToken.user_id == user.user_id)
        result = await async_session.execute(query)
        tokens = result.scalars().all()
        assert len(tokens) == 0
        
        # Verify user can login with new password
        form_data = {
            "username": user.username,
            "password": new_password
        }
        
        login_response = await async_client.post("/api/v1/user/login", data=form_data)
        assert login_response.status_code == 200
        
        # Cleanup new token created by login
        query = delete(UserToken).where(UserToken.user_id == user.user_id)
        result = await async_session.execute(query)
    
    async def test_change_password_wrong_old_password(self, async_client: AsyncClient, user_token):
        """Test password change fails with incorrect old password"""
        headers = {"Authorization": f"Bearer {user_token.token_id}"}
        password_data = {
            "old_password": "wrongpassword",
            "new_password": "newpassword123"
        }
        
        response = await async_client.post("/api/v1/user/change-password", json=password_data, headers=headers)
        
        assert response.status_code == 400
        assert "Incorrect password" in response.json()["detail"]
    
    async def test_change_password_expired_token(self, async_client: AsyncClient, expired_token):
        """Test password change fails with expired token"""
        headers = {"Authorization": f"Bearer {expired_token.token_id}"}
        password_data = {
            "old_password": "testpassword123",
            "new_password": "newpassword123"
        }
        
        response = await async_client.post("/api/v1/user/change-password", json=password_data, headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    