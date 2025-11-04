# Kubernetes Deployment Guide

This guide covers deploying the LLM Platform on Kubernetes for production use.

## Prerequisites

- Kubernetes cluster (1.21+)
- Helm 3.7+
- kubectl configured for your cluster
- Persistent storage provisioner
- LoadBalancer or Ingress controller
- SSL certificates

## Quick Start

### 1. Install Using Helm

```bash
# Add the LLM Platform Helm repository
helm repo add llm-platform https://charts.llm-platform.com
helm repo update

# Install the platform
helm install llm-platform llm-platform/llm-platform \
  --namespace llm-platform \
  --create-namespace \
  --values values-production.yaml
```

### 2. Manual Installation

```bash
# Clone the repository
git clone https://github.com/your-org/llm-platform.git
cd llm-platform

# Deploy using kubectl
kubectl apply -f kubernetes/base/
kubectl apply -f kubernetes/services/
```

## Configuration

### Helm Values

Create a `values-production.yaml` file:

```yaml
# values-production.yaml
replicaCount:
  django: 3
  fastapi: 5
  fastapiGpu: 2

image:
  django:
    repository: your-registry/llm-platform/django-service
    tag: "v1.0.0"
  fastapi:
    repository: your-registry/llm-platform/fastapi-service
    tag: "v1.0.0"

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "1000"
  hosts:
    - host: api.your-domain.com
      paths:
        - path: /
          pathType: Prefix
          service: fastapi
    - host: admin.your-domain.com
      paths:
        - path: /
          pathType: Prefix
          service: django
  tls:
    - secretName: llm-platform-tls
      hosts:
        - api.your-domain.com
        - admin.your-domain.com

resources:
  django:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 500m
      memory: 1Gi
  fastapi:
    limits:
      cpu: 2000m
      memory: 4Gi
    requests:
      cpu: 1000m
      memory: 2Gi
  fastapiGpu:
    limits:
      cpu: 4000m
      memory: 16Gi
      nvidia.com/gpu: 1
    requests:
      cpu: 2000m
      memory: 8Gi
      nvidia.com/gpu: 1

autoscaling:
  django:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
  fastapi:
    enabled: true
    minReplicas: 5
    maxReplicas: 20
    targetCPUUtilizationPercentage: 60

persistence:
  enabled: true
  storageClass: "fast-ssd"
  postgres:
    size: 500Gi
  redis:
    size: 100Gi
  models:
    size: 1Ti

postgresql:
  enabled: true
  auth:
    postgresPassword: "secure_postgres_password"
    username: "llm_user"
    password: "secure_user_password"
    database: "llm_platform"
  primary:
    persistence:
      enabled: true
      size: 500Gi
      storageClass: "fast-ssd"
    resources:
      limits:
        cpu: 2000m
        memory: 4Gi
      requests:
        cpu: 1000m
        memory: 2Gi

redis:
  enabled: true
  auth:
    enabled: true
    password: "secure_redis_password"
  master:
    persistence:
      enabled: true
      size: 100Gi
      storageClass: "fast-ssd"
    resources:
      limits:
        cpu: 1000m
        memory: 2Gi
      requests:
        cpu: 500m
        memory: 1Gi

monitoring:
  enabled: true
  prometheus:
    enabled: true
  grafana:
    enabled: true
    adminPassword: "secure_grafana_password"

config:
  django:
    secretKey: "your-very-secure-django-secret-key"
    debug: false
  database:
    host: "llm-platform-postgresql"
    port: "5432"
    name: "llm_platform"
    user: "llm_user"
    password: "secure_user_password"
  redis:
    host: "llm-platform-redis-master"
    port: "6379"
    password: "secure_redis_password"
  api:
    rateLimit: "10000"
    maxTokens: "4096"
  models:
    defaultModel: "llama-2-7b"
    cacheSize: "50GB"
```

### Secrets Management

Create secrets for sensitive data:

```bash
# Database credentials
kubectl create secret generic llm-platform-db-secret \
  --from-literal=username=llm_user \
  --from-literal=password=secure_user_password \
  --namespace=llm-platform

# Django secret key
kubectl create secret generic llm-platform-django-secret \
  --from-literal=secret-key=your-very-secure-django-secret-key \
  --namespace=llm-platform

# API keys for external services
kubectl create secret generic llm-platform-api-keys \
  --from-literal=openai-api-key=your-openai-key \
  --from-literal=huggingface-token=your-hf-token \
  --namespace=llm-platform

# Registry credentials
kubectl create secret docker-registry registry-secret \
  --docker-server=your-registry.com \
  --docker-username=your-username \
  --docker-password=your-password \
  --namespace=llm-platform
```

## GPU Support

### Node Preparation

For GPU workloads, ensure your nodes have:

1. NVIDIA GPU drivers installed
2. NVIDIA Container Toolkit installed
3. Kubernetes GPU operator or device plugin

```bash
# Install NVIDIA GPU Operator
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm repo update

helm install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator-resources \
  --create-namespace
```

### GPU Node Labeling

Label your GPU nodes:

```bash
kubectl label nodes <gpu-node-name> accelerator=nvidia-tesla-v100
kubectl label nodes <gpu-node-name> gpu-memory=16GB
```

### GPU Workload Configuration

The FastAPI GPU deployment will automatically:
- Request GPU resources
- Apply node selectors for GPU nodes
- Set appropriate tolerations

## Storage Configuration

### Storage Classes

Create optimized storage classes:

```yaml
# fast-ssd-storage-class.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs  # Adjust for your cloud provider
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
allowVolumeExpansion: true
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: model-storage
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  iops: "16000"
  throughput: "1000"
allowVolumeExpansion: true
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
```

### Persistent Volume Claims

The platform creates several PVCs:
- `postgres-pvc`: Database storage (500Gi recommended)
- `redis-pvc`: Redis persistence (100Gi recommended) 
- `model-cache-pvc`: Model file storage (1Ti recommended)

## Networking

### Ingress Configuration

Example NGINX Ingress configuration:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: llm-platform-ingress
  namespace: llm-platform
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/rate-limit: "1000"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.your-domain.com
    - admin.your-domain.com
    secretName: llm-platform-tls
  rules:
  - host: api.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: llm-platform-fastapi
            port:
              number: 8001
  - host: admin.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: llm-platform-django
            port:
              number: 8000
```

### Network Policies

Secure your deployment with network policies:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: llm-platform-network-policy
  namespace: llm-platform
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: llm-platform
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
    - protocol: TCP
      port: 8001
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgresql
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
  - to: []  # Allow all outbound for model downloads
    ports:
    - protocol: TCP
      port: 443
    - protocol: TCP
      port: 80
```

## Monitoring and Observability

### Prometheus Configuration

The platform includes Prometheus monitoring:

```yaml
# prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: llm-platform-monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    scrape_configs:
      - job_name: 'llm-platform-django'
        static_configs:
          - targets: ['llm-platform-django:8000']
        metrics_path: '/metrics'
      
      - job_name: 'llm-platform-fastapi'
        static_configs:
          - targets: ['llm-platform-fastapi:8001']
        metrics_path: '/metrics'
      
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
        - role: pod
        relabel_configs:
        - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
          action: keep
          regex: true
```

### Grafana Dashboards

Pre-configured dashboards are available for:
- API performance metrics
- Model inference metrics
- Resource utilization
- Error rates and latency
- Cost optimization

## Security

### RBAC Configuration

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: llm-platform-serviceaccount
  namespace: llm-platform
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: llm-platform
  name: llm-platform-role
rules:
- apiGroups: [""]
  resources: ["pods", "services", "endpoints"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: llm-platform-rolebinding
  namespace: llm-platform
subjects:
- kind: ServiceAccount
  name: llm-platform-serviceaccount
  namespace: llm-platform
roleRef:
  kind: Role
  name: llm-platform-role
  apiGroup: rbac.authorization.k8s.io
```

### Pod Security

```yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: llm-platform-psp
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
```

## Deployment Steps

### 1. Prepare Environment

```bash
# Create namespace
kubectl create namespace llm-platform

# Apply secrets
kubectl apply -f secrets/

# Create storage classes
kubectl apply -f storage-classes.yaml
```

### 2. Deploy Dependencies

```bash
# Deploy PostgreSQL
helm install postgresql bitnami/postgresql \
  --namespace llm-platform \
  --values postgresql-values.yaml

# Deploy Redis
helm install redis bitnami/redis \
  --namespace llm-platform \
  --values redis-values.yaml
```

### 3. Deploy Application

```bash
# Deploy using Helm
helm install llm-platform ./helm-chart \
  --namespace llm-platform \
  --values values-production.yaml

# Or deploy manually
kubectl apply -f kubernetes/
```

### 4. Verify Deployment

```bash
# Check pod status
kubectl get pods -n llm-platform

# Check services
kubectl get services -n llm-platform

# Check ingress
kubectl get ingress -n llm-platform

# View logs
kubectl logs -f deployment/llm-platform-fastapi -n llm-platform
```

## Scaling

### Horizontal Pod Autoscaler

HPA is configured to scale based on:
- CPU utilization (70% for Django, 60% for FastAPI)
- Memory utilization (80% for Django, 70% for FastAPI)
- Custom metrics (requests per second)

### Vertical Pod Autoscaler

Install VPA for automatic resource optimization:

```bash
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler/
./hack/vpa-install.sh
```

### Cluster Autoscaler

Configure cluster autoscaler for automatic node scaling based on resource demands.

## Backup and Recovery

### Database Backup

```bash
# Create backup job
kubectl create job --from=cronjob/postgres-backup postgres-backup-manual -n llm-platform

# Restore from backup
kubectl apply -f restore-job.yaml
```

### Model Storage Backup

```bash
# Backup model cache
kubectl exec -n llm-platform deployment/llm-platform-fastapi -- \
  tar czf /backup/models-$(date +%Y%m%d).tar.gz -C /app/models .

# Copy backup to external storage
kubectl cp llm-platform/pod-name:/backup/models-$(date +%Y%m%d).tar.gz \
  ./models-backup.tar.gz
```

## Troubleshooting

### Common Issues

1. **Pods stuck in Pending state**
   ```bash
   kubectl describe pod <pod-name> -n llm-platform
   # Check for resource constraints or node selection issues
   ```

2. **ImagePullBackOff errors**
   ```bash
   # Check registry credentials
   kubectl get secret registry-secret -n llm-platform -o yaml
   ```

3. **PVC not binding**
   ```bash
   kubectl get pvc -n llm-platform
   kubectl describe pvc <pvc-name> -n llm-platform
   # Check storage class and node availability
   ```

4. **GPU pods not scheduling**
   ```bash
   kubectl get nodes -l accelerator=nvidia-tesla-v100
   kubectl describe node <gpu-node-name>
   ```

### Debugging Commands

```bash
# Get all resources
kubectl get all -n llm-platform

# Check events
kubectl get events -n llm-platform --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n llm-platform
kubectl top nodes

# Port forward for local debugging
kubectl port-forward svc/llm-platform-fastapi 8001:8001 -n llm-platform
```

## Maintenance

### Updates

```bash
# Update using Helm
helm upgrade llm-platform ./helm-chart \
  --namespace llm-platform \
  --values values-production.yaml

# Rollback if needed
helm rollback llm-platform 1 -n llm-platform
```

### Health Checks

```bash
# Run health check script
./scripts/health-check.sh production

# Check service endpoints
curl -f https://api.your-domain.com/health
curl -f https://admin.your-domain.com/health/
```

For more detailed information, see the [Operations Guide](../operations/monitoring.md) and [Troubleshooting Guide](../operations/troubleshooting.md).