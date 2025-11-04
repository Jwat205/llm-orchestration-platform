# LLM Platform Helm Chart

This Helm chart deploys a comprehensive, enterprise-grade LLM API platform with all the advanced features including streaming responses, function calling, embeddings, vector search, analytics, security, and more.

## Features

- **Core Services**: Django admin backend, FastAPI inference API
- **Advanced LLM Features**: Streaming responses, function calling, multi-model support
- **Embeddings & Search**: Vector storage, semantic search, document processing
- **Enterprise Security**: RBAC, SSO, audit logging, encryption
- **Analytics & Monitoring**: Real-time dashboards, performance metrics, alerting
- **Billing & Payments**: Multiple pricing models, Stripe integration
- **Scalability**: Auto-scaling, load balancing, GPU support
- **Observability**: Comprehensive logging, distributed tracing

## Prerequisites

- Kubernetes 1.19+
- Helm 3.8.0+
- PV provisioner support in the underlying infrastructure
- GPU nodes (optional, for GPU-accelerated inference)

## Installing the Chart

```bash
# Add repository
helm repo add llm-platform https://your-repo.github.io/helm-charts

# Install with default values (development)
helm install my-llm-platform llm-platform/llm-platform

# Install with production values
helm install my-llm-platform llm-platform/llm-platform -f values-prod.yaml

# Install with custom values
helm install my-llm-platform llm-platform/llm-platform \\
  --set postgresql.enabled=true \\
  --set redis.enabled=true \\
  --set monitoring.enabled=true
```

## Configuration

### Basic Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount.django` | Number of Django replicas | `2` |
| `replicaCount.fastapi` | Number of FastAPI replicas | `3` |
| `replicaCount.fastapiGpu` | Number of FastAPI GPU replicas | `1` |

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.django.repository` | Django image repository | `llm-platform/django-service` |
| `image.django.tag` | Django image tag | `latest` |
| `image.fastapi.repository` | FastAPI image repository | `llm-platform/fastapi-service` |
| `image.fastapi.tag` | FastAPI image tag | `latest` |

### Service Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `service.type` | Kubernetes service type | `ClusterIP` |
| `service.django.port` | Django service port | `8000` |
| `service.fastapi.port` | FastAPI service port | `8001` |

### Ingress Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.hosts` | Ingress hosts configuration | See values.yaml |

### Persistence Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `persistence.enabled` | Enable persistent volumes | `true` |
| `persistence.storageClass` | Storage class for PVCs | `fast-ssd` |
| `persistence.postgres.size` | PostgreSQL storage size | `100Gi` |
| `persistence.models.size` | Model cache storage size | `500Gi` |

### Database Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Deploy PostgreSQL | `true` |
| `config.database.name` | Database name | `llm_platform_dev` |
| `config.database.user` | Database user | `llm_user` |
| `config.database.password` | Database password | `dev_password` |

### Redis Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Deploy Redis | `true` |
| `config.redis.password` | Redis password | `dev_redis_password` |

### GPU Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `gpu.enabled` | Enable GPU support | `true` |
| `gpu.nodeSelector` | GPU node selector | `accelerator: nvidia-tesla-v100` |

### Monitoring Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `monitoring.enabled` | Enable monitoring stack | `true` |
| `monitoring.prometheus.enabled` | Enable Prometheus | `true` |
| `monitoring.grafana.enabled` | Enable Grafana | `true` |

### Security Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `security.rbac.enabled` | Enable RBAC | `true` |
| `security.networkPolicies.enabled` | Enable network policies | `false` |
| `security.podSecurityPolicy.enabled` | Enable pod security policies | `false` |

## Examples

### Development Deployment

```bash
helm install llm-dev llm-platform/llm-platform \\
  --set config.django.debug=true \\
  --set config.monitoring.logLevel=DEBUG \\
  --set autoscaling.django.enabled=false \\
  --set autoscaling.fastapi.enabled=false
```

### Production Deployment

```bash
helm install llm-prod llm-platform/llm-platform \\
  -f values-prod.yaml \\
  --set config.django.secretKey="your-production-secret-key" \\
  --set config.database.password="secure-production-password" \\
  --set config.redis.password="secure-redis-password"
```

### GPU-Enabled Deployment

```bash
helm install llm-gpu llm-platform/llm-platform \\
  --set gpu.enabled=true \\
  --set replicaCount.fastapiGpu=3 \\
  --set gpu.nodeSelector.accelerator="nvidia-a100"
```

### High Availability Deployment

```bash
helm install llm-ha llm-platform/llm-platform \\
  --set replicaCount.django=5 \\
  --set replicaCount.fastapi=10 \\
  --set postgresql.primary.persistence.size=1Ti \\
  --set redis.master.persistence.size=200Gi
```

## Upgrading

```bash
# Upgrade to new version
helm upgrade my-llm-platform llm-platform/llm-platform

# Upgrade with new values
helm upgrade my-llm-platform llm-platform/llm-platform -f new-values.yaml
```

## Uninstalling

```bash
# Uninstall the release
helm uninstall my-llm-platform

# Uninstall and delete PVCs
helm uninstall my-llm-platform
kubectl delete pvc -l app.kubernetes.io/instance=my-llm-platform
```

## Services Overview

### Core Services

- **Django Service**: Admin interface, user management, billing
- **FastAPI Service**: Main API endpoints, LLM inference
- **FastAPI GPU Service**: GPU-accelerated inference for heavy models

### Additional Services

- **Graph Service**: Knowledge graph processing and queries
- **Document Processor**: Document parsing and chunking
- **Training Service**: Model fine-tuning and training
- **Billing Service**: Payment processing and subscription management
- **Security Service**: Authentication, authorization, audit logging
- **Monitoring Service**: Metrics collection and analysis

### External Dependencies

- **PostgreSQL**: Primary database
- **Redis**: Caching and session storage
- **Prometheus**: Metrics collection
- **Grafana**: Monitoring dashboards
- **Elasticsearch**: Log aggregation (optional)
- **Jaeger**: Distributed tracing (optional)

## Networking

The chart creates the following network endpoints:

- `api.llm-platform.com` - Main API endpoints
- `admin.llm-platform.com` - Django admin interface
- `graph-api.llm-platform.com` - Graph service API
- `monitoring.llm-platform.com` - Monitoring dashboards

## Storage

The chart provisions the following persistent volumes:

- PostgreSQL data: 100Gi (default) / 500Gi (production)
- Redis data: 50Gi (default) / 100Gi (production)
- Model cache: 500Gi (default) / 2Ti (production)
- Embeddings: 1Ti (production only)
- Documents: 500Gi (optional)
- Logs: 200Gi (optional)
- Backups: 1Ti (optional)

## Troubleshooting

### Common Issues

1. **Pod not starting**: Check resource limits and node capacity
2. **GPU not detected**: Verify GPU drivers and device plugin
3. **Database connection failed**: Check database credentials and connectivity
4. **Ingress not working**: Verify ingress controller and DNS configuration

### Debugging Commands

```bash
# Check pod status
kubectl get pods -l app.kubernetes.io/instance=my-llm-platform

# Check logs
kubectl logs -l component=fastapi -f

# Check resources
kubectl describe pod <pod-name>

# Check configuration
kubectl get configmap my-llm-platform-config -o yaml
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Make your changes
4. Test with different configurations
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.