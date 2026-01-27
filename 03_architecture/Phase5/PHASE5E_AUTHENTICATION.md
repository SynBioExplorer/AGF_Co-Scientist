# Phase 5E: Multi-User & Authentication

## Overview

Implement user authentication, workspace isolation, and role-based access control (RBAC) for multi-user production deployment.

**Branch:** `phase5/auth`
**Worktree:** `worktree-5e-auth`
**Dependencies:** Phase 5D (Frontend) for UI integration
**Estimated Duration:** 1 week

## Authentication Strategy

| Environment | Method |
|-------------|--------|
| Local Development | Simple JWT (email/password) |
| AWS Production | AWS Cognito via Amplify |

## Deliverables

### Files to Create

```
src/
├── auth/
│   ├── __init__.py
│   ├── models.py              # User, Workspace models
│   ├── jwt.py                 # JWT token handling
│   ├── cognito.py             # AWS Cognito integration
│   ├── middleware.py          # Auth middleware
│   ├── dependencies.py        # FastAPI dependencies
│   └── rbac.py                # Role-based access control
├── api/
│   └── auth_routes.py         # Auth endpoints

tests/
└── test_auth.py               # Authentication tests
```

### 1. User & Workspace Models (`src/auth/models.py`)

```python
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from datetime import datetime

class UserRole(str, Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    RESEARCHER = "researcher"
    VIEWER = "viewer"

class User(BaseModel):
    """User model."""
    id: str
    email: EmailStr
    name: str
    role: UserRole = UserRole.RESEARCHER
    workspace_ids: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    is_active: bool = True

class Workspace(BaseModel):
    """Workspace for isolating research goals."""
    id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    member_ids: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WorkspaceMembership(BaseModel):
    """User membership in workspace."""
    user_id: str
    workspace_id: str
    role: UserRole
    joined_at: datetime = Field(default_factory=datetime.utcnow)

# Request/Response models
class UserCreate(BaseModel):
    """User creation request."""
    email: EmailStr
    name: str
    password: str

class UserLogin(BaseModel):
    """Login request."""
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None

class WorkspaceCreate(BaseModel):
    """Workspace creation request."""
    name: str
    description: Optional[str] = None
```

### 2. JWT Token Handling (`src/auth/jwt.py`)

```python
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from ..config import get_settings

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class TokenData(BaseModel):
    """Decoded token data."""
    user_id: str
    email: str
    role: str
    workspace_ids: list[str]
    exp: datetime

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """Hash password."""
    return pwd_context.hash(password)

def create_access_token(
    user_id: str,
    email: str,
    role: str,
    workspace_ids: list[str],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token."""
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "workspace_ids": workspace_ids,
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

def create_refresh_token(user_id: str) -> str:
    """Create refresh token with longer expiry."""
    expire = datetime.utcnow() + timedelta(days=30)

    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

def decode_token(token: str) -> Optional[TokenData]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        return TokenData(
            user_id=payload["sub"],
            email=payload["email"],
            role=payload["role"],
            workspace_ids=payload.get("workspace_ids", []),
            exp=datetime.fromtimestamp(payload["exp"])
        )
    except JWTError:
        return None

def is_token_expired(token_data: TokenData) -> bool:
    """Check if token is expired."""
    return datetime.utcnow() > token_data.exp
```

### 3. AWS Cognito Integration (`src/auth/cognito.py`)

```python
import boto3
from typing import Optional
from pydantic import BaseModel

from ..config import get_settings

settings = get_settings()

class CognitoAuth:
    """AWS Cognito authentication handler."""

    def __init__(self):
        self.client = boto3.client(
            'cognito-idp',
            region_name=settings.aws_region
        )
        self.user_pool_id = settings.cognito_user_pool_id
        self.client_id = settings.cognito_client_id

    async def sign_up(
        self,
        email: str,
        password: str,
        name: str
    ) -> dict:
        """Register new user in Cognito."""
        response = self.client.sign_up(
            ClientId=self.client_id,
            Username=email,
            Password=password,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'name', 'Value': name},
            ]
        )
        return response

    async def confirm_sign_up(
        self,
        email: str,
        confirmation_code: str
    ) -> dict:
        """Confirm user registration."""
        response = self.client.confirm_sign_up(
            ClientId=self.client_id,
            Username=email,
            ConfirmationCode=confirmation_code
        )
        return response

    async def sign_in(
        self,
        email: str,
        password: str
    ) -> Optional[dict]:
        """Authenticate user and get tokens."""
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': email,
                    'PASSWORD': password,
                }
            )

            auth_result = response.get('AuthenticationResult', {})
            return {
                'access_token': auth_result.get('AccessToken'),
                'refresh_token': auth_result.get('RefreshToken'),
                'id_token': auth_result.get('IdToken'),
                'expires_in': auth_result.get('ExpiresIn'),
            }
        except self.client.exceptions.NotAuthorizedException:
            return None
        except self.client.exceptions.UserNotFoundException:
            return None

    async def refresh_tokens(self, refresh_token: str) -> Optional[dict]:
        """Refresh access token."""
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token,
                }
            )

            auth_result = response.get('AuthenticationResult', {})
            return {
                'access_token': auth_result.get('AccessToken'),
                'id_token': auth_result.get('IdToken'),
                'expires_in': auth_result.get('ExpiresIn'),
            }
        except Exception:
            return None

    async def get_user(self, access_token: str) -> Optional[dict]:
        """Get user info from access token."""
        try:
            response = self.client.get_user(AccessToken=access_token)
            attributes = {
                attr['Name']: attr['Value']
                for attr in response.get('UserAttributes', [])
            }
            return {
                'username': response.get('Username'),
                'email': attributes.get('email'),
                'name': attributes.get('name'),
                'sub': attributes.get('sub'),
            }
        except Exception:
            return None

    async def sign_out(self, access_token: str) -> bool:
        """Sign out user (invalidate tokens)."""
        try:
            self.client.global_sign_out(AccessToken=access_token)
            return True
        except Exception:
            return False
```

### 4. Auth Middleware (`src/auth/middleware.py`)

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional

from .jwt import decode_token, is_token_expired
from .models import TokenData

class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware."""

    # Paths that don't require authentication
    PUBLIC_PATHS = [
        "/health",
        "/docs",
        "/openapi.json",
        "/auth/login",
        "/auth/register",
        "/auth/refresh",
    ]

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if any(request.url.path.startswith(path) for path in self.PUBLIC_PATHS):
            return await call_next(request)

        # Extract token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing authorization header")

        token = auth_header.split(" ")[1]

        # Decode and validate token
        token_data = decode_token(token)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid token")

        if is_token_expired(token_data):
            raise HTTPException(status_code=401, detail="Token expired")

        # Attach user info to request state
        request.state.user = token_data

        return await call_next(request)
```

### 5. FastAPI Dependencies (`src/auth/dependencies.py`)

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import List

from .jwt import decode_token, TokenData
from .models import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Get current authenticated user."""
    token_data = decode_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data

async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """Get current active user."""
    # Could add additional checks here (e.g., is_active)
    return current_user

def require_role(allowed_roles: List[UserRole]):
    """Dependency factory for role-based access."""
    async def role_checker(
        current_user: TokenData = Depends(get_current_user)
    ) -> TokenData:
        if current_user.role not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

def require_workspace_access(workspace_id: str):
    """Dependency factory for workspace access."""
    async def workspace_checker(
        current_user: TokenData = Depends(get_current_user)
    ) -> TokenData:
        if (
            current_user.role != UserRole.ADMIN.value
            and workspace_id not in current_user.workspace_ids
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this workspace"
            )
        return current_user
    return workspace_checker

# Convenience dependencies
require_admin = require_role([UserRole.ADMIN])
require_researcher = require_role([UserRole.ADMIN, UserRole.RESEARCHER])
require_viewer = require_role([UserRole.ADMIN, UserRole.RESEARCHER, UserRole.VIEWER])
```

### 6. RBAC (`src/auth/rbac.py`)

```python
from typing import Set
from .models import UserRole

# Permission definitions
class Permission:
    # Goals
    CREATE_GOAL = "goal:create"
    READ_GOAL = "goal:read"
    UPDATE_GOAL = "goal:update"
    DELETE_GOAL = "goal:delete"

    # Hypotheses
    READ_HYPOTHESIS = "hypothesis:read"
    PROVIDE_FEEDBACK = "hypothesis:feedback"

    # Chat
    SEND_MESSAGE = "chat:send"
    READ_CHAT = "chat:read"

    # Admin
    MANAGE_USERS = "users:manage"
    MANAGE_WORKSPACES = "workspaces:manage"

# Role to permissions mapping
ROLE_PERMISSIONS: dict[UserRole, Set[str]] = {
    UserRole.ADMIN: {
        Permission.CREATE_GOAL,
        Permission.READ_GOAL,
        Permission.UPDATE_GOAL,
        Permission.DELETE_GOAL,
        Permission.READ_HYPOTHESIS,
        Permission.PROVIDE_FEEDBACK,
        Permission.SEND_MESSAGE,
        Permission.READ_CHAT,
        Permission.MANAGE_USERS,
        Permission.MANAGE_WORKSPACES,
    },
    UserRole.RESEARCHER: {
        Permission.CREATE_GOAL,
        Permission.READ_GOAL,
        Permission.UPDATE_GOAL,
        Permission.READ_HYPOTHESIS,
        Permission.PROVIDE_FEEDBACK,
        Permission.SEND_MESSAGE,
        Permission.READ_CHAT,
    },
    UserRole.VIEWER: {
        Permission.READ_GOAL,
        Permission.READ_HYPOTHESIS,
        Permission.READ_CHAT,
    },
}

def has_permission(role: UserRole, permission: str) -> bool:
    """Check if role has permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())

def get_permissions(role: UserRole) -> Set[str]:
    """Get all permissions for role."""
    return ROLE_PERMISSIONS.get(role, set())
```

### 7. Auth Routes (`src/api/auth_routes.py`)

```python
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from ..auth.models import (
    UserCreate, UserLogin, TokenResponse,
    User, WorkspaceCreate, Workspace
)
from ..auth.jwt import (
    create_access_token, create_refresh_token,
    hash_password, verify_password, decode_token
)
from ..auth.dependencies import get_current_user, require_admin
from ..storage import storage

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=User)
async def register(user_data: UserCreate):
    """Register new user."""
    # Check if email exists
    existing = await storage.get_user_by_email(user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = User(
        id=f"user_{hash(user_data.email) % 10**8}",
        email=user_data.email,
        name=user_data.name,
    )

    # Store user with hashed password
    hashed_pw = hash_password(user_data.password)
    await storage.create_user(user, hashed_pw)

    return user

@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    # Get user
    user = await storage.get_user_by_email(form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Verify password
    stored_hash = await storage.get_user_password_hash(user.id)
    if not verify_password(form_data.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Create tokens
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
        workspace_ids=user.workspace_ids
    )
    refresh_token = create_refresh_token(user.id)

    # Update last login
    await storage.update_user_last_login(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=86400  # 24 hours
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Refresh access token."""
    token_data = decode_token(refresh_token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user = await storage.get_user(token_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
        workspace_ids=user.workspace_ids
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=86400
    )

@router.get("/me", response_model=User)
async def get_me(current_user = Depends(get_current_user)):
    """Get current user info."""
    user = await storage.get_user(current_user.user_id)
    return user

@router.post("/workspaces", response_model=Workspace)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    current_user = Depends(get_current_user)
):
    """Create new workspace."""
    workspace = Workspace(
        id=f"ws_{hash(workspace_data.name) % 10**8}",
        name=workspace_data.name,
        description=workspace_data.description,
        owner_id=current_user.user_id,
        member_ids=[current_user.user_id]
    )

    await storage.create_workspace(workspace)

    # Add workspace to user
    await storage.add_user_to_workspace(current_user.user_id, workspace.id)

    return workspace

@router.post("/workspaces/{workspace_id}/members/{user_id}")
async def add_workspace_member(
    workspace_id: str,
    user_id: str,
    current_user = Depends(require_admin)
):
    """Add member to workspace (admin only)."""
    await storage.add_user_to_workspace(user_id, workspace_id)
    return {"status": "ok"}
```

### 8. Update API Main (`src/api/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth_routes import router as auth_router
from ..auth.middleware import AuthMiddleware

app = FastAPI(title="AI Co-Scientist API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-amplify-app.amplifyapp.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware (after CORS)
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(auth_router)
# ... other routers
```

### 9. Configuration Updates (`src/config.py`)

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # JWT
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"

    # AWS Cognito (for production)
    aws_region: str = "ap-southeast-2"
    cognito_user_pool_id: Optional[str] = None
    cognito_client_id: Optional[str] = None

    # Auth mode
    auth_provider: Literal["local", "cognito"] = "local"
```

## Frontend Integration

Update React app for authentication:

```typescript
// src/services/auth.ts
import api from './api';

export const login = async (email: string, password: string) => {
  const formData = new FormData();
  formData.append('username', email);
  formData.append('password', password);

  const { data } = await api.post('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });

  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);

  return data;
};

export const logout = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
};

// Add auth header to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

## Test Cases (`tests/test_auth.py`)

```python
import pytest
from src.auth.jwt import create_access_token, decode_token, hash_password, verify_password
from src.auth.models import UserRole

def test_password_hashing():
    """Test password hash and verify."""
    password = "secure_password_123"
    hashed = hash_password(password)

    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)

def test_jwt_token():
    """Test JWT creation and decoding."""
    token = create_access_token(
        user_id="user_001",
        email="test@example.com",
        role=UserRole.RESEARCHER.value,
        workspace_ids=["ws_001"]
    )

    decoded = decode_token(token)
    assert decoded is not None
    assert decoded.user_id == "user_001"
    assert decoded.email == "test@example.com"
    assert decoded.role == "researcher"

def test_rbac_permissions():
    """Test role-based permissions."""
    from src.auth.rbac import has_permission, Permission

    assert has_permission(UserRole.ADMIN, Permission.MANAGE_USERS)
    assert not has_permission(UserRole.VIEWER, Permission.CREATE_GOAL)
    assert has_permission(UserRole.RESEARCHER, Permission.CREATE_GOAL)
```

## Success Criteria

- [ ] User registration and login working
- [ ] JWT token generation and validation
- [ ] Role-based access control enforced
- [ ] Workspace isolation working
- [ ] AWS Cognito integration (optional)
- [ ] Frontend auth flow complete
- [ ] Token refresh mechanism
- [ ] All tests passing

## Environment Variables

```bash
# JWT (Local auth)
JWT_SECRET_KEY=your-super-secret-key-change-this
JWT_ALGORITHM=HS256

# AWS Cognito (Production)
AWS_REGION=ap-southeast-2
COGNITO_USER_POOL_ID=ap-southeast-2_xxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxx

# Auth mode
AUTH_PROVIDER=local  # or "cognito"
```
