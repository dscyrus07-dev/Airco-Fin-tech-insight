"""
User models for Auth Service.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from enum import Enum

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    PREMIUM = "premium"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class User(BaseModel):
    """User model representing authenticated user from Keycloak."""
    
    id: str = Field(..., description="User ID (sub claim)")
    email: EmailStr = Field(..., description="User email")
    name: Optional[str] = Field(None, description="User full name")
    given_name: Optional[str] = Field(None, description="User given name")
    family_name: Optional[str] = Field(None, description="User family name")
    preferred_username: Optional[str] = Field(None, description="User preferred username")
    roles: List[str] = Field(default_factory=list, description="User roles from Keycloak")
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True

class UserInfo(BaseModel):
    """User info response model."""
    
    id: str
    email: EmailStr
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    preferred_username: Optional[str] = None
    roles: List[str] = []
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True

class TokenValidationResponse(BaseModel):
    """Token validation response model."""
    
    valid: bool
    user: Optional[UserInfo] = None
    error: Optional[str] = None

# Legacy models for backward compatibility
class LegacyUser(BaseModel):
    """Legacy user model for database storage."""
    id: str = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    full_name: str = Field(..., description="User full name")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    status: UserStatus = Field(default=UserStatus.ACTIVE, description="User status")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UserCreate(BaseModel):
    """User creation model."""
    email: EmailStr
    full_name: str
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.USER

class UserLogin(BaseModel):
    """User login model."""
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    """User update model."""
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None

class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: LegacyUser

class TokenRefresh(BaseModel):
    """Token refresh model."""
    refresh_token: str

class UserResponse(BaseModel):
    """User response model."""
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    last_login: Optional[datetime] = None
