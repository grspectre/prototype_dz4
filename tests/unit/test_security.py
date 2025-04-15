import pytest
import pytest_asyncio
import datetime
import string
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.db.base import User, UserToken
from app.core.security import (
    is_valid_uuid, 
    get_credential_exception, 
    get_token, 
    get_token_if_not_expired, 
    get_current_user, 
    get_hash, 
    create_access_token, 
    get_password_hash, 
    verify_password
)

class TestIsValidUuid:
    def test_valid_uuid(self):
        valid_uuid = "c9bf9e57-1685-4c89-bafb-ff5af830be8a"
        assert is_valid_uuid(valid_uuid) is True

    def test_invalid_uuid_format(self):
        invalid_uuid = "c9bf9e58"
        assert is_valid_uuid(invalid_uuid) is False

    def test_invalid_uuid_string(self):
        invalid_uuid = "not-a-uuid"
        assert is_valid_uuid(invalid_uuid) is False

    def test_different_version(self):
        # UUID version 1
        uuid_v1 = "a8098c1a-f86e-11da-bd1a-00112444be1e"
        assert is_valid_uuid(uuid_v1, version=1) is True
        assert is_valid_uuid(uuid_v1, version=4) is False

class TestGetCredentialException:
    def test_exception_properties(self):
        exception = get_credential_exception()
        assert isinstance(exception, HTTPException)
        assert exception.status_code == 401
        assert exception.detail == "Could not validate credentials"
        assert exception.headers == {"WWW-Authenticate": "Bearer"}

class TestGetToken:
    @pytest_asyncio.fixture
    async def mock_db(self):
        mock = AsyncMock(spec=AsyncSession)
        return mock

    @pytest_asyncio.fixture
    def mock_credentials(self):
        credentials = MagicMock()
        credentials.credentials = str(uuid4())
        return credentials

    @pytest_asyncio.fixture
    def mock_token(self):
        token = MagicMock(spec=UserToken)
        token.token_id = str(uuid4())
        token.user_id = 1
        token.expires_at = datetime.datetime.now() + datetime.timedelta(days=1)
        return token

    async def test_get_token_success(self, mock_db, mock_credentials, mock_token):
        # Setup mock query response
        mock_response = MagicMock()  # Changed from AsyncMock to MagicMock
        mock_response.scalar_one_or_none.return_value = mock_token
        mock_db.execute.return_value = mock_response

        # Execute function
        result = await get_token(mock_db, mock_credentials)

        # Verify result
        assert result == mock_token
        mock_db.execute.assert_called_once()

    async def test_get_token_invalid_uuid(self, mock_db):
        # Create credentials with invalid UUID
        invalid_credentials = MagicMock()
        invalid_credentials.credentials = "not-a-valid-uuid"

        # Function should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await get_token(mock_db, invalid_credentials)
        
        assert exc_info.value.status_code == 401
        # Ensure DB was never queried
        mock_db.execute.assert_not_called()

    async def test_get_token_not_found(self, mock_db, mock_credentials):
        # Setup mock query response for token not found
        mock_response = MagicMock()  # Changed from AsyncMock to MagicMock
        mock_response.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_response

        # Function should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await get_token(mock_db, mock_credentials)
        
        assert exc_info.value.status_code == 401
        mock_db.execute.assert_called_once()

class TestGetTokenIfNotExpired:
    @pytest_asyncio.fixture
    async def mock_db(self):
        mock = AsyncMock(spec=AsyncSession)
        return mock

    @pytest_asyncio.fixture
    def mock_credentials(self):
        credentials = MagicMock()
        credentials.credentials = str(uuid4())
        return credentials

    @pytest_asyncio.fixture
    def mock_valid_token(self):
        token = MagicMock(spec=UserToken)
        token.token_id = str(uuid4())
        token.user_id = 1
        token.expires_at = datetime.datetime.now() + datetime.timedelta(days=1)
        token.is_expired.return_value = False
        return token

    @pytest_asyncio.fixture
    def mock_expired_token(self):
        token = MagicMock(spec=UserToken)
        token.token_id = str(uuid4())
        token.user_id = 1
        token.expires_at = datetime.datetime.now() - datetime.timedelta(days=1)
        token.is_expired.return_value = True
        return token

    async def test_get_token_valid(self, mock_db, mock_credentials, mock_valid_token):
        # Setup mock query response
        mock_response = MagicMock()  # Changed from AsyncMock to MagicMock
        mock_response.scalar_one_or_none.return_value = mock_valid_token
        mock_db.execute.return_value = mock_response

        # Execute function
        result = await get_token_if_not_expired(mock_db, mock_credentials)

        # Verify result
        assert result == mock_valid_token
        mock_db.execute.assert_called_once()
        mock_valid_token.is_expired.assert_called_once()

    async def test_get_token_expired(self, mock_db, mock_credentials, mock_expired_token):
        # Setup mock query response
        mock_response = MagicMock()  # Changed from AsyncMock to MagicMock
        mock_response.scalar_one_or_none.return_value = mock_expired_token
        mock_db.execute.return_value = mock_response

        # Function should raise exception for expired token
        with pytest.raises(HTTPException) as exc_info:
            await get_token_if_not_expired(mock_db, mock_credentials)
        
        assert exc_info.value.status_code == 401
        mock_db.execute.assert_called_once()
        mock_expired_token.is_expired.assert_called_once()

    async def test_get_token_not_found(self, mock_db, mock_credentials):
        # Setup mock query response for token not found
        mock_response = MagicMock()  # Changed from AsyncMock to MagicMock
        mock_response.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_response

        # Function should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await get_token_if_not_expired(mock_db, mock_credentials)
        
        assert exc_info.value.status_code == 401
        mock_db.execute.assert_called_once()

class TestGetCurrentUser:
    @pytest_asyncio.fixture
    async def mock_db(self):
        mock = AsyncMock(spec=AsyncSession)
        return mock

    @pytest_asyncio.fixture
    def mock_credentials(self):
        credentials = MagicMock()
        credentials.credentials = str(uuid4())
        return credentials

    @pytest_asyncio.fixture
    def mock_token(self):
        token = MagicMock(spec=UserToken)
        token.token_id = str(uuid4())
        token.user_id = 1
        token.expires_at = datetime.datetime.now() + datetime.timedelta(days=1)
        token.is_expired.return_value = False
        return token

    @pytest_asyncio.fixture
    def mock_user(self):
        user = MagicMock(spec=User)
        user.id = 1
        user.username = "testuser"
        return user

    @patch("app.core.security.get_token_if_not_expired")
    @patch("app.core.security.get_user_by_id")
    async def test_get_current_user_success(self, mock_get_user, mock_get_token, 
                                           mock_db, mock_credentials, mock_token, mock_user):
        # Setup mocks
        mock_get_token.return_value = mock_token
        mock_get_user.return_value = mock_user

        # Execute function
        result = await get_current_user(mock_db, mock_credentials)

        # Verify result
        assert result == mock_user
        mock_get_token.assert_called_once()
        mock_get_user.assert_called_once_with(mock_db, mock_token.user_id)

    @patch("app.core.security.get_token_if_not_expired")
    @patch("app.core.security.get_user_by_id")
    async def test_get_current_user_not_found(self, mock_get_user, mock_get_token, 
                                             mock_db, mock_credentials, mock_token):
        # Setup mocks
        mock_get_token.return_value = mock_token
        mock_get_user.return_value = None

        # Function should raise exception when user not found
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_db, mock_credentials)
        
        assert exc_info.value.status_code == 401
        mock_get_token.assert_called_once()
        mock_get_user.assert_called_once_with(mock_db, mock_token.user_id)

    @patch("app.core.security.get_token_if_not_expired")
    async def test_get_current_user_token_expired(self, mock_get_token, mock_db, mock_credentials):
        # Setup mock to raise exception
        mock_get_token.side_effect = get_credential_exception()

        # Function should propagate the exception
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_db, mock_credentials)
        
        assert exc_info.value.status_code == 401
        mock_get_token.assert_called_once()

class TestGetHash:
    def test_hash_generation(self):
        # Test with known input and output
        password = "password123"
        salt = "abc123"
        expected_hash = "82877e693061077ae371f90e248db5b3"  # Precomputed MD5 hash
        
        result = get_hash(password, salt)
        assert result == expected_hash

    def test_different_passwords(self):
        # Different passwords with same salt should produce different hashes
        salt = "same_salt"
        hash1 = get_hash("password1", salt)
        hash2 = get_hash("password2", salt)
        assert hash1 != hash2

    def test_different_salts(self):
        # Same password with different salts should produce different hashes
        password = "same_password"
        hash1 = get_hash(password, "salt1")
        hash2 = get_hash(password, "salt2")
        assert hash1 != hash2

class TestCreateAccessToken:
    def test_token_generation(self):
        data = {"user_id": 1}
        expires_delta = datetime.timedelta(days=1)
        
        token_id, expires_at = create_access_token(data, expires_delta)
        
        # Check token_id is a valid UUID
        assert is_valid_uuid(str(token_id))
        
        # Check expiration time is roughly correct (allow 1 second margin)
        expected_expiry = datetime.datetime.now() + expires_delta
        difference = abs((expires_at - expected_expiry).total_seconds())
        assert difference < 1.0

class TestGetPasswordHash:
    def test_hash_and_salt_generation(self):
        password = "securepassword"
        
        hash_value, salt = get_password_hash(password)
        
        # Check salt is correct length and format
        assert len(salt) == 32
        assert all(c in string.digits + 'abcdef' for c in salt)
        
        # Check hash is a valid MD5 hash (32 hexadecimal characters)
        assert len(hash_value) == 32
        assert all(c in string.digits + 'abcdef' for c in hash_value)
        
        # Verify hash matches what we'd expect for this password and salt
        expected_hash = get_hash(password, salt)
        assert hash_value == expected_hash

class TestVerifyPassword:
    def test_valid_password(self):
        # Setup a known password, hash, and salt
        password = "correctpassword"
        salt = "knownSalt123"
        hash_value = get_hash(password, salt)
        
        # Verify password check
        assert verify_password(password, hash_value, salt) is True

    def test_invalid_password(self):
        # Setup a known password, hash, and salt
        correct_password = "correctpassword"
        wrong_password = "wrongpassword"
        salt = "knownSalt123"
        hash_value = get_hash(correct_password, salt)
        
        # Verify wrong password fails
        assert verify_password(wrong_password, hash_value, salt) is False
