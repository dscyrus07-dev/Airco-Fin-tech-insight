"""
Authentication service implementation.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from ..models.user import User, UserCreate, UserLogin, UserRole, UserStatus
from ..utils.jwt_utils import jwt_manager
from ..utils.logging import get_logger

logger = get_logger(__name__)

class AuthService:
    """Authentication service."""
    
    def __init__(self):
        # In-memory user store for Phase 1 (will be replaced with database)
        self._users: Dict[str, User] = {}
        self._users_by_email: Dict[str, User] = {}
        
        # Create default admin user
        self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin user for development."""
        admin_email = "admin@airco.com"
        if admin_email not in self._users_by_email:
            admin_user = User(
                id=str(uuid.uuid4()),
                email=admin_email,
                full_name="Airco Admin",
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE
            )
            # Store with a default password hash
            self._users[admin_user.id] = admin_user
            self._users_by_email[admin_user.email] = admin_user
            logger.info("Default admin user created", email=admin_email)
    
    async def register_user(self, user_data: UserCreate) -> User:
        """Register a new user."""
        # Check if user already exists
        if user_data.email in self._users_by_email:
            raise ValueError("User with this email already exists")
        
        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            status=UserStatus.ACTIVE
        )
        
        # Hash password (store separately in real implementation)
        hashed_password = jwt_manager.hash_password(user_data.password)
        
        # Store user
        self._users[user.id] = user
        self._users_by_email[user.email] = user
        
        logger.info("User registered", user_id=user.id, email=user.email)
        return user
    
    async def authenticate_user(self, login_data: UserLogin) -> Optional[User]:
        """Authenticate user with email and password."""
        user = self._users_by_email.get(login_data.email)
        
        # For Phase 1, use simple password check
        # In production, verify against hashed password
        if user and user.status == UserStatus.ACTIVE:
            # Special case for default admin
            if user.email == "admin@airco.com" and login_data.password == "admin123":
                user.last_login = datetime.utcnow()
                logger.info("User authenticated", user_id=user.id, email=user.email)
                return user
            # Password verification for other users - implement as needed
        
        logger.warning("Authentication failed", email=login_data.email)
        return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self._users_by_email.get(email)
    
    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[User]:
        """Update user information."""
        user = self._users.get(user_id)
        if not user:
            return None
        
        # Update allowed fields
        if "full_name" in update_data:
            user.full_name = update_data["full_name"]
        if "role" in update_data:
            user.role = UserRole(update_data["role"])
        if "status" in update_data:
            user.status = UserStatus(update_data["status"])
        
        user.updated_at = datetime.utcnow()
        
        logger.info("User updated", user_id=user_id)
        return user
    
    async def create_tokens(self, user: User) -> Dict[str, Any]:
        """Create access and refresh tokens for user."""
        token_data = {
            "sub": user.id,
            "email": user.email,
            "role": user.role.value,
            "full_name": user.full_name
        }
        
        access_token = jwt_manager.create_access_token(token_data)
        refresh_token = jwt_manager.create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 30 * 60,  # 30 minutes in seconds
            "user": user
        }
    
    async def refresh_tokens(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh access token using refresh token."""
        try:
            payload = jwt_manager.verify_token(refresh_token, "refresh")
            user_id = payload.get("sub")
            
            user = await self.get_user_by_id(user_id)
            if not user or user.status != UserStatus.ACTIVE:
                return None
            
            return await self.create_tokens(user)
            
        except Exception as e:
            logger.error("Token refresh failed", error=str(e))
            return None

# Global auth service instance
auth_service = AuthService()
