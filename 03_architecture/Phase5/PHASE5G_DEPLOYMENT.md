# Phase 5G: Deployment (DEFERRED)

> **Status:** DEFERRED - Focus on local development first
>
> This document is retained for future reference when production deployment is needed.

## Current Approach

For MVP, run locally:

```bash
# Backend
uvicorn src.api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

## When to Implement

Consider production deployment when:
- System validated with real research workflows
- Multi-user access required
- High availability needed
- External collaborator access

## Planned Infrastructure (Future)

| Component | Technology |
|-----------|------------|
| Frontend Hosting | AWS Amplify |
| Backend Hosting | AWS ECS or Lambda |
| Database | AWS RDS (PostgreSQL) |
| Vector Store | pgvector on RDS |
| Caching | AWS ElastiCache (Redis) |

## Deferred Features

- Docker containerization
- Kubernetes manifests
- CI/CD pipelines (GitHub Actions)
- AWS CloudFormation/Terraform
- Domain and SSL configuration
- Auto-scaling configuration

---

## Original Specification (For Reference)

The following is the original comprehensive plan, retained for future implementation.

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ AWS Amplify  │    │ API Gateway  │    │  ECS / Lambda    │  │
│  │  (React UI)  │───▶│  (WebSocket) │───▶│  (FastAPI)       │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│                                                 │                │
│                           ┌─────────────────────┼───────────┐   │
│                           ▼                     ▼           ▼   │
│                    ┌──────────┐          ┌──────────┐  ┌──────┐ │
│                    │   RDS    │          │ElastiCache│  │  S3  │ │
│                    │(Postgres)│          │  (Redis)  │  │      │ │
│                    └──────────┘          └──────────┘  └──────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Files to Create (When Implemented)

```
Dockerfile                    # FastAPI backend
docker-compose.yml            # Local development
docker-compose.prod.yml       # Production-like local
deploy/
├── aws/
│   ├── cloudformation/       # Infrastructure as code
│   ├── scripts/              # Deploy/rollback scripts
│   └── task-definition.json  # ECS task definition
.github/
└── workflows/
    ├── ci.yml                # Lint, test, build
    └── deploy-production.yml # Deploy on tag
```

### Production Checklist (When Implementing)

- [ ] AWS account and IAM configured
- [ ] ECR repository created
- [ ] RDS PostgreSQL instance created
- [ ] ElastiCache Redis cluster created
- [ ] Secrets in AWS Secrets Manager
- [ ] ECS cluster and service created
- [ ] API Gateway configured
- [ ] Amplify app deployed (frontend)
- [ ] CloudWatch alarms set up
- [ ] DNS configured (Route 53)
- [ ] SSL certificates (ACM)
