from typing import List, Optional
from pydantic import BaseModel, EmailStr, UUID4, ConfigDict
from datetime import datetime
from app.db.base import UserRoles

class UserBase(BaseModel):
    username: str
    email: EmailStr
    name: str
    last_name: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    last_name: Optional[str] = None

class UserRead(UserBase):
    user_id: UUID4
    roles: List[UserRoles]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )

class UserLogin(BaseModel):
    username: str
    password: str

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime

class TokenPayload(BaseModel):
    sub: str
    roles: List[str]
    exp: int
