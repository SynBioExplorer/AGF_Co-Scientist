# Phase 5G: Containerization & Deployment

## Overview

Containerize the application and set up deployment infrastructure for local development and AWS production.

**Branch:** `phase5/deployment`
**Worktree:** `worktree-5g-deployment`
**Dependencies:** All other Phase 5 components (final phase)
**Estimated Duration:** 0.5 weeks

## Deployment Architecture

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
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐                           │
│  │  CloudWatch  │    │   Cognito    │                           │
│  │  (Metrics)   │    │   (Auth)     │                           │
│  └──────────────┘    └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

## Deliverables

### Files to Create

```
.
├── Dockerfile                    # FastAPI backend
├── Dockerfile.frontend           # React frontend (optional)
├── docker-compose.yml            # Local development
├── docker-compose.prod.yml       # Production-like local
├── .dockerignore
├── deploy/
│   ├── aws/
│   │   ├── cloudformation/
│   │   │   ├── vpc.yml
│   │   │   ├── rds.yml
│   │   │   ├── ecs.yml
│   │   │   └── main.yml
│   │   ├── scripts/
│   │   │   ├── deploy.sh
│   │   │   └── rollback.sh
│   │   └── task-definition.json
│   └── k8s/                      # Optional Kubernetes
│       ├── namespace.yml
│       ├── deployment.yml
│       ├── service.yml
│       ├── ingress.yml
│       └── configmap.yml
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── deploy-staging.yml
│       └── deploy-production.yml
└── scripts/
    ├── build.sh
    ├── test.sh
    └── local-setup.sh
```

### 1. Backend Dockerfile (`Dockerfile`)

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser 02_Prompts/ ./02_Prompts/
COPY --chown=appuser:appuser 03_Architecture/schemas.py ./03_Architecture/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Docker Ignore (`.dockerignore`)

```
# Git
.git
.gitignore

# Python
__pycache__
*.py[cod]
*$py.class
*.so
.Python
.env
.venv
env/
venv/
.pytest_cache/
.mypy_cache/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Testing
.coverage
htmlcov/
tests/

# Documentation
*.md
docs/

# Build artifacts
dist/
build/
*.egg-info/

# Local development
docker-compose*.yml
Dockerfile*
.dockerignore

# Secrets (never include)
*.pem
*.key
secrets/
```

### 3. Local Development Docker Compose (`docker-compose.yml`)

```yaml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: coscientist-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/coscientist
      - REDIS_URL=redis://redis:6379
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-dev-secret-key}
      - ENVIRONMENT=development
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./src:/app/src:ro  # Hot reload in dev
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:15-alpine
    container_name: coscientist-db
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=coscientist
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./src/storage/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: coscientist-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Optional: pgAdmin for database management
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: coscientist-pgadmin
    ports:
      - "5050:80"
    environment:
      - PGADMIN_DEFAULT_EMAIL=admin@local.dev
      - PGADMIN_DEFAULT_PASSWORD=admin
    depends_on:
      - db
    profiles:
      - tools

volumes:
  postgres_data:
  redis_data:
```

### 4. Production Docker Compose (`docker-compose.prod.yml`)

```yaml
version: '3.8'

services:
  api:
    image: ${ECR_REGISTRY}/coscientist-api:${IMAGE_TAG:-latest}
    container_name: coscientist-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    logging:
      driver: awslogs
      options:
        awslogs-group: /ecs/coscientist
        awslogs-region: ap-southeast-2
        awslogs-stream-prefix: api
```

### 5. ECS Task Definition (`deploy/aws/task-definition.json`)

```json
{
  "family": "coscientist-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/coscientistTaskRole",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com/coscientist-api:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "LOG_LEVEL", "value": "INFO"}
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:ap-southeast-2:ACCOUNT_ID:secret:coscientist/database-url"
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:ap-southeast-2:ACCOUNT_ID:secret:coscientist/redis-url"
        },
        {
          "name": "GOOGLE_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:ap-southeast-2:ACCOUNT_ID:secret:coscientist/google-api-key"
        },
        {
          "name": "JWT_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:ap-southeast-2:ACCOUNT_ID:secret:coscientist/jwt-secret"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/coscientist",
          "awslogs-region": "ap-southeast-2",
          "awslogs-stream-prefix": "api"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

### 6. GitHub Actions CI (`/.github/workflows/ci.yml`)

```yaml
name: CI

on:
  push:
    branches: [main, phase5/*]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: '3.11'

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install ruff mypy

      - name: Run linter
        run: ruff check src/

      - name: Run type checker
        run: mypy src/ --ignore-missing-imports

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_coscientist
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_coscientist
          REDIS_URL: redis://localhost:6379
        run: |
          pytest tests/ -v --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  build:
    runs-on: ubuntu-latest
    needs: [lint, test]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: coscientist-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### 7. GitHub Actions Deploy (`/.github/workflows/deploy-production.yml`)

```yaml
name: Deploy to Production

on:
  push:
    tags:
      - 'v*'

env:
  AWS_REGION: ap-southeast-2
  ECR_REPOSITORY: coscientist-api
  ECS_CLUSTER: coscientist-cluster
  ECS_SERVICE: coscientist-api-service

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image
        id: build-image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.ref_name }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT

      - name: Update ECS task definition
        id: task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: deploy/aws/task-definition.json
          container-name: api
          image: ${{ steps.build-image.outputs.image }}

      - name: Deploy to ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ${{ steps.task-def.outputs.task-definition }}
          service: ${{ env.ECS_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true

      - name: Notify deployment
        if: always()
        run: |
          echo "Deployment ${{ job.status }}: ${{ github.ref_name }}"
```

### 8. Local Setup Script (`scripts/local-setup.sh`)

```bash
#!/bin/bash
set -e

echo "🚀 Setting up AI Co-Scientist locally..."

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed. Aborting." >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose is required but not installed. Aborting." >&2; exit 1; }

# Create .env if not exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp 03_Architecture/.env.example .env
    echo "⚠️  Please edit .env and add your API keys"
fi

# Build and start services
echo "Building Docker images..."
docker-compose build

echo "Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 10

# Check health
if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed"
    docker-compose logs api
    exit 1
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Services running:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo "Commands:"
echo "  - View logs: docker-compose logs -f"
echo "  - Stop: docker-compose down"
echo "  - Restart: docker-compose restart"
```

### 9. Build Script (`scripts/build.sh`)

```bash
#!/bin/bash
set -e

VERSION=${1:-latest}
REGISTRY=${ECR_REGISTRY:-"local"}

echo "Building coscientist-api:$VERSION..."

# Build image
docker build \
    --tag coscientist-api:$VERSION \
    --tag $REGISTRY/coscientist-api:$VERSION \
    --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
    --build-arg VERSION=$VERSION \
    .

echo "Build complete: coscientist-api:$VERSION"

# Optionally push to registry
if [ "$PUSH" = "true" ] && [ "$REGISTRY" != "local" ]; then
    echo "Pushing to $REGISTRY..."
    docker push $REGISTRY/coscientist-api:$VERSION
fi
```

### 10. Requirements File (`requirements.txt`)

```
# Core
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Database
asyncpg>=0.29.0
sqlalchemy>=2.0.0
redis>=5.0.0

# LLM
langchain>=0.1.0
langchain-google-genai>=0.0.6
langchain-openai>=0.0.5
langgraph>=0.0.20

# Auth
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6

# Observability
prometheus-client>=0.19.0
structlog>=24.1.0

# Utils
httpx>=0.26.0
aiofiles>=23.2.0
python-dotenv>=1.0.0

# PDF processing (Phase 5C)
pymupdf>=1.23.0
```

## Local Development Workflow

```bash
# 1. Clone repository
git clone <repo-url>
cd coscientist

# 2. Run setup script
chmod +x scripts/local-setup.sh
./scripts/local-setup.sh

# 3. Start developing
docker-compose logs -f api  # Watch logs

# 4. Run tests
docker-compose exec api pytest tests/ -v

# 5. Stop services
docker-compose down
```

## Production Deployment Checklist

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

## Success Criteria

- [ ] Docker image builds successfully
- [ ] Local docker-compose stack runs
- [ ] CI pipeline passes (lint, test, build)
- [ ] CD pipeline deploys to ECS
- [ ] Health checks passing
- [ ] Logs streaming to CloudWatch
- [ ] Zero-downtime deployments working

## Environment Variables

### Local Development
```bash
# .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/coscientist
REDIS_URL=redis://localhost:6379
GOOGLE_API_KEY=your-google-api-key
OPENAI_API_KEY=your-openai-api-key
TAVILY_API_KEY=your-tavily-api-key
JWT_SECRET_KEY=dev-secret-change-in-prod
ENVIRONMENT=development
```

### Production (AWS Secrets Manager)
- `coscientist/database-url`
- `coscientist/redis-url`
- `coscientist/google-api-key`
- `coscientist/openai-api-key`
- `coscientist/tavily-api-key`
- `coscientist/jwt-secret`
