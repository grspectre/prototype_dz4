# app/api/endpoints/user.py
from fastapi import APIRouter, Depends, Security, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import Annotated

from app.core.security import create_access_token, get_token, get_token_if_not_expired, get_password_hash, verify_password
from app.db.session import get_db
from app.db.base import User, UserToken, get_user_by_id
from app.schemas.user import UserCreate, UserRead, Token, ChangePassword

router = APIRouter()

ACCESS_TOKEN_EXPIRE_MINUTES = 30


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate, 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Register a new user"""
    query = select(User).filter(User.username == user_in.username)
    response = await db.execute(query)
    db_user = response.scalar_one_or_none()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    query = select(User).filter(User.email == user_in.email)
    response = await db.execute(query)
    db_user = response.scalar_one_or_none()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password and create salt
    hashed_password, salt = get_password_hash(user_in.password)
    
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        name=user_in.name,
        last_name=user_in.last_name,
        password=hashed_password,
        salt=salt
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    query = select(User).filter(User.username == form_data.username)
    response = await db.execute(query)
    db_user = response.scalar_one_or_none()
    if not db_user or not verify_password(form_data.password, db_user.password, db_user.salt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token, expires_at = create_access_token(
        data={"sub": str(db_user.user_id), "roles": [role.value for role in db_user.roles]},
        expires_delta=access_token_expires
    )
    
    # Store token in database
    token = UserToken(
        user_id=db_user.user_id,
        expired_at=expires_at,
        token_id=str(access_token)
    )
    db.add(token)
    await db.commit()
    return {"access_token": str(access_token), "token_type": "bearer", "expires_at": expires_at}


@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    current_token: Annotated[UserToken, Security(get_token)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    user = await get_user_by_id(db, current_token.user_id)
    """Refresh access token"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token, expires_at = create_access_token(
        data={"sub": str(user.user_id), "roles": [role.value for role in user.roles]},
        expires_delta=access_token_expires
    )

    current_token.token_id = access_token
    current_token.expired_at = expires_at

    await db.commit()
    
    return {"access_token": str(access_token), "token_type": "bearer", "expires_at": expires_at}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: ChangePassword,
    current_token: Annotated[UserToken, Security(get_token_if_not_expired)],
    db: Annotated[Session, Depends(get_db)]
):
    user = await get_user_by_id(db, current_token.user_id)
    """Change user password"""
    if not verify_password(password_data.old_password, user.password, user.salt):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password"
        )
    
    # Hash new password
    hashed_password, salt = get_password_hash(password_data.new_password)
    
    user.password = hashed_password
    user.salt = salt
    
    await db.commit()
    await db.refresh(user)
    
    query = delete(UserToken).where(UserToken.user_id == user.user_id)
    await db.execute(query)
    await db.commit()
    
    return {"detail": "Password updated successfully"}
