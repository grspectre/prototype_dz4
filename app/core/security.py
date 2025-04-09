import hashlib
import random
import string
import datetime
from uuid import uuid4, UUID
from app.db.base import User, UserToken, get_user_by_id
from fastapi import Depends, Security, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from app.db.session import get_db
from sqlalchemy import select

http_bearer = HTTPBearer()

def is_valid_uuid(uuid_to_test, version=4):
    """
    Check if uuid_to_test is a valid UUID.
    
     Parameters
    ----------
    uuid_to_test : str
    version : {1, 2, 3, 4}
    
     Returns
    -------
    `True` if uuid_to_test is a valid UUID, otherwise `False`.
    
     Examples
    --------
    >>> is_valid_uuid('c9bf9e57-1685-4c89-bafb-ff5af830be8a')
    True
    >>> is_valid_uuid('c9bf9e58')
    False
    """
    
    try:
        uuid_obj = UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test


def get_credential_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials = Security(http_bearer)
) -> UserToken:
    credentials_exception = get_credential_exception()

    if not is_valid_uuid(credentials.credentials):
        raise credentials_exception

    query = select(UserToken).filter(UserToken.token_id == credentials.credentials)
    response = await db.execute(query)
    token = response.scalar_one_or_none()
    if token is None:
        raise credentials_exception        
    return token


async def get_token_if_not_expired(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials = Security(http_bearer)
) -> UserToken:
    credentials_exception = get_credential_exception()

    if not is_valid_uuid(credentials.credentials):
        raise credentials_exception

    query = select(UserToken).filter(UserToken.token_id == credentials.credentials)
    response = await db.execute(query)
    token = response.scalar_one_or_none()
    if token is None or token.is_expired():
        raise credentials_exception        
    return token


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials = Security(http_bearer)
) -> User:
    credentials_exception = get_credential_exception()
    token = await get_token_if_not_expired(db, credentials)
    user = await get_user_by_id(db, token.user_id)
    if user is None:
        raise credentials_exception
    return user


def get_hash(pwd: str, salt: str) -> str:
    return hashlib.md5(f"{pwd}{salt}".encode("utf8")).hexdigest()


def create_access_token(data, expires_delta):
    return (uuid4(), datetime.datetime.now() + expires_delta)


def get_password_hash(pwd: str):
    salt = ''.join(random.choices(string.digits + 'abcdef', k=32))
    return get_hash(pwd,  salt), salt


def verify_password(password: str, hash: str, salt: str):
    return hash == get_hash(password, salt)
