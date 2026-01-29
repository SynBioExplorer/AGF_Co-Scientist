# Phase 5E: Authentication (DEFERRED)

> **Status:** DEFERRED - Not required for MVP
>
> This document is retained for future reference when multi-user support is needed.

## When to Implement

Consider implementing authentication when:
- Deploying to shared infrastructure
- Multiple scientists need workspace isolation
- Public cloud deployment with access control
- Audit logging requirements

## Planned Approach

### Local Development
- Simple API key authentication
- Single-user mode

### Production (Future)
- AWS Cognito for managed authentication
- JWT tokens with refresh
- Role-based access control (Admin, Researcher, Viewer)
- Workspace isolation

## Deferred Features

- User registration and login
- OAuth2 / JWT token management
- Workspace multi-tenancy
- Role-based permissions
- Session management

---

## Original Specification (For Reference)

The following is the original comprehensive plan, retained for future implementation.

### Authentication Strategy

| Environment | Method |
|-------------|--------|
| Local Development | Simple JWT (email/password) |
| AWS Production | AWS Cognito via Amplify |

### User Roles

| Role | Permissions |
|------|-------------|
| Admin | Full access, manage users/workspaces |
| Researcher | Create goals, provide feedback, chat |
| Viewer | Read-only access |

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | User registration |
| `POST /auth/login` | Login, returns JWT |
| `POST /auth/refresh` | Refresh access token |
| `GET /auth/me` | Get current user |
| `POST /auth/workspaces` | Create workspace |

### Environment Variables (When Implemented)

```bash
# JWT (Local auth)
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256

# AWS Cognito (Production)
AWS_REGION=ap-southeast-2
COGNITO_USER_POOL_ID=ap-southeast-2_xxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxx
AUTH_PROVIDER=local  # or "cognito"
```
