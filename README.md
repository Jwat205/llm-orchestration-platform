# Enterprise LLM API Platform

A comprehensive microservices-based platform for enterprise LLM integration, featuring multiple specialized services for AI model orchestration, billing, monitoring, and more.

## Architecture

This platform consists of multiple microservices:

- **FastAPI Service** (`fastapi_service/`) - High-performance AI inference service
- **Django Service** (`django_service/`) - Main backend API and admin interface
- **Frontend** (`frontend/`) - Web application interface
- **Billing Service** (`billing_service/`) - Usage tracking and billing management
- **Monitoring Service** (`monitoring-service/`) - System monitoring and metrics
- **Security Service** (`security-service/`) - Authentication and authorization
- **Graph Service** (`graph-service/`) - Knowledge graph operations
- **Document Processor** (`document-processor/`) - Document processing and embeddings

## Prerequisites

- Docker and Docker Compose
- Python 3.10+
- Node.js 16+ (for frontend)
- PostgreSQL 14+
- Redis 7+

## Quick Start

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd Local\ API\ Development
```

2. Copy the environment template:
```bash
cp .env.example .env
```

3. Update `.env` with your API keys and configuration

4. Start the services:
```bash
# Development environment
docker-compose -f docker-compose.dev.yml up -d

# Production environment
docker-compose -f docker-compose.prod.yml up -d
```

5. Access the services:
- FastAPI Service: http://localhost:8001
- Django Admin: http://localhost:8000/admin
- Frontend: http://localhost:3000
- API Documentation: http://localhost:8001/docs

## Project Structure

```
.
├── fastapi_service/       # FastAPI inference service
├── django_service/        # Django backend service
├── frontend/              # React/Next.js frontend
├── billing_service/       # Billing & usage tracking
├── monitoring-service/    # System monitoring
├── security-service/      # Security & auth
├── graph-service/         # Knowledge graph
├── document-processor/    # Document processing
├── shared/                # Shared utilities
├── infrastructure/        # IaC (Terraform, CloudFormation)
├── kubernetes/            # K8s manifests
├── helm-chart/            # Helm charts
├── tests/                 # Integration tests
└── scripts/               # Utility scripts
```

## Deployment

### Docker Compose

For local and small-scale deployments:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes

For production deployments:
```bash
kubectl apply -f kubernetes/
```

### AWS ECS

Use the provided infrastructure configurations:
```bash
cd infrastructure/terraform
terraform init
terraform apply
```

## Configuration

All configuration is managed through environment variables. See `.env.example` for a complete list of available options.

Key configuration areas:
- Database connections
- API keys (OpenAI, Anthropic, HuggingFace)
- Authentication settings
- Model configurations
- Monitoring and logging

## Testing

Run tests with:
```bash
# Python tests
pytest tests/

# Frontend tests
cd frontend && npm test
```

## Monitoring

Access monitoring dashboards:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (if configured)

## License

Proprietary - All Rights Reserved

## Support

For issues and questions, please open an issue in the repository.
