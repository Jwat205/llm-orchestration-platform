#!/bin/bash

# LLM API Platform - Complete AWS Deployment Script
# This script deploys the entire platform to AWS EKS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration variables
AWS_REGION=${AWS_REGION:-us-east-1}
CLUSTER_NAME=${CLUSTER_NAME:-llm-api-platform}
NAMESPACE=${NAMESPACE:-llm-api}
ECR_REGISTRY=""
DOMAIN_NAME=${DOMAIN_NAME:-api.yourdomain.com}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null && ! python -m awscli --version &> /dev/null; then
        print_error "AWS CLI not found. Please install AWS CLI first."
        exit 1
    fi

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_warning "kubectl not found. Installing kubectl..."
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        chmod +x kubectl
        sudo mv kubectl /usr/local/bin/ 2>/dev/null || mv kubectl ~/kubectl
        export PATH=$PATH:~/
    fi

    # Check eksctl
    if ! command -v eksctl &> /dev/null; then
        print_warning "eksctl not found. Installing eksctl..."
        curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
        sudo mv /tmp/eksctl /usr/local/bin 2>/dev/null || mv /tmp/eksctl ~/eksctl
    fi

    # Check Helm
    if ! command -v helm &> /dev/null; then
        print_warning "Helm not found. Installing Helm..."
        curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
    fi

    print_success "Prerequisites checked"
}

# Configure AWS credentials
configure_aws() {
    print_status "Configuring AWS credentials..."

    # Check if AWS credentials are configured
    if ! python -m awscli sts get-caller-identity &> /dev/null; then
        print_warning "AWS credentials not configured. Please configure them:"
        echo ""
        print_status "Run: aws configure"
        echo "Enter your AWS Access Key ID, Secret Access Key, and region (${AWS_REGION})"
        echo ""
        print_status "Or set environment variables:"
        echo "export AWS_ACCESS_KEY_ID=your-access-key"
        echo "export AWS_SECRET_ACCESS_KEY=your-secret-key"
        echo "export AWS_DEFAULT_REGION=${AWS_REGION}"
        echo ""
        read -p "Press Enter after configuring AWS credentials..."
    fi

    # Verify credentials
    ACCOUNT_ID=$(python -m awscli sts get-caller-identity --query Account --output text)
    if [ -z "$ACCOUNT_ID" ]; then
        print_error "Failed to get AWS account ID. Please check your credentials."
        exit 1
    fi

    ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    print_success "AWS configured. Account ID: $ACCOUNT_ID"
}

# Create ECR repositories
create_ecr_repositories() {
    print_status "Creating ECR repositories..."

    repositories=("llm-api/django" "llm-api/fastapi" "llm-api/frontend")

    for repo in "${repositories[@]}"; do
        if python -m awscli ecr describe-repositories --repository-names "$repo" --region "$AWS_REGION" &> /dev/null; then
            print_status "Repository $repo already exists"
        else
            print_status "Creating repository: $repo"
            python -m awscli ecr create-repository --repository-name "$repo" --region "$AWS_REGION"
        fi
    done

    print_success "ECR repositories ready"
}

# Build and push Docker images
build_and_push_images() {
    print_status "Building and pushing Docker images..."

    # Login to ECR
    print_status "Logging in to ECR..."
    python -m awscli ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

    # Build and push Django image
    print_status "Building Django image..."
    cd django-service
    docker build -t "${ECR_REGISTRY}/llm-api/django:latest" .
    docker push "${ECR_REGISTRY}/llm-api/django:latest"
    cd ..

    # Build and push FastAPI image
    print_status "Building FastAPI image..."
    cd fastapi-service
    docker build -t "${ECR_REGISTRY}/llm-api/fastapi:latest" .
    docker push "${ECR_REGISTRY}/llm-api/fastapi:latest"
    cd ..

    # Build and push Frontend image
    print_status "Building Frontend image..."
    cd frontend
    docker build -t "${ECR_REGISTRY}/llm-api/frontend:latest" .
    docker push "${ECR_REGISTRY}/llm-api/frontend:latest"
    cd ..

    print_success "Docker images built and pushed"
}

# Create EKS cluster
create_eks_cluster() {
    print_status "Creating EKS cluster..."

    # Check if cluster exists
    if python -m awscli eks describe-cluster --name "$CLUSTER_NAME" --region "$AWS_REGION" &> /dev/null; then
        print_status "Cluster $CLUSTER_NAME already exists"
    else
        print_status "Creating EKS cluster: $CLUSTER_NAME (this may take 15-20 minutes)..."

        # Create cluster configuration
        cat > cluster-config.yaml << EOF
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig

metadata:
  name: ${CLUSTER_NAME}
  region: ${AWS_REGION}
  version: "1.28"

nodeGroups:
  - name: worker-nodes
    instanceType: m5.large
    desiredCapacity: 3
    minSize: 1
    maxSize: 5
    volumeSize: 20
    ssh:
      allow: true
    iam:
      withAddonPolicies:
        imageBuilder: true
        autoScaler: true
        externalDNS: true
        certManager: true
        appMesh: true
        ebs: true
        fsx: true
        efs: true

  - name: gpu-nodes
    instanceType: g4dn.xlarge
    desiredCapacity: 1
    minSize: 0
    maxSize: 3
    volumeSize: 100
    ssh:
      allow: true
    labels:
      node-type: gpu
    taints:
      - key: nvidia.com/gpu
        value: "true"
        effect: NoSchedule

addons:
  - name: vpc-cni
  - name: coredns
  - name: kube-proxy
  - name: aws-ebs-csi-driver

cloudWatch:
  clusterLogging:
    enable: true
    logTypes: ["*"]
EOF

        eksctl create cluster -f cluster-config.yaml
    fi

    # Update kubeconfig
    python -m awscli eks update-kubeconfig --region "$AWS_REGION" --name "$CLUSTER_NAME"

    print_success "EKS cluster ready"
}

# Install necessary Kubernetes tools
install_k8s_tools() {
    print_status "Installing Kubernetes tools..."

    # Install AWS Load Balancer Controller
    print_status "Installing AWS Load Balancer Controller..."
    kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller//crds?ref=master"

    helm repo add eks https://aws.github.io/eks-charts
    helm repo update

    # Create IAM service account for load balancer controller
    eksctl create iamserviceaccount \
        --cluster="$CLUSTER_NAME" \
        --namespace=kube-system \
        --name=aws-load-balancer-controller \
        --role-name=AmazonEKSLoadBalancerControllerRole \
        --attach-policy-arn=arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess \
        --approve \
        --override-existing-serviceaccounts || true

    helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
        -n kube-system \
        --set clusterName="$CLUSTER_NAME" \
        --set serviceAccount.create=false \
        --set serviceAccount.name=aws-load-balancer-controller || true

    # Install NGINX Ingress Controller
    print_status "Installing NGINX Ingress Controller..."
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
    helm repo update
    helm install ingress-nginx ingress-nginx/ingress-nginx \
        --namespace ingress-nginx \
        --create-namespace \
        --set controller.service.type=LoadBalancer || true

    # Install cert-manager for SSL certificates
    print_status "Installing cert-manager..."
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml || true

    print_success "Kubernetes tools installed"
}

# Deploy the application
deploy_application() {
    print_status "Deploying LLM API Platform..."

    # Create namespace
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # Create secrets
    print_status "Creating secrets..."
    kubectl create secret generic app-secrets \
        --namespace="$NAMESPACE" \
        --from-literal=DATABASE_URL="postgresql://postgres:$(openssl rand -base64 32)@postgres:5432/llm_api" \
        --from-literal=REDIS_URL="redis://:$(openssl rand -base64 32)@redis:6379/0" \
        --from-literal=DJANGO_SECRET_KEY="$(openssl rand -base64 50)" \
        --from-literal=JWT_SECRET="$(openssl rand -base64 32)" \
        --dry-run=client -o yaml | kubectl apply -f -

    # Deploy PostgreSQL
    print_status "Deploying PostgreSQL..."
    cat > postgres-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: llm_api
        - name: POSTGRES_USER
          value: postgres
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: DATABASE_URL
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: ${NAMESPACE}
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: ${NAMESPACE}
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF

    kubectl apply -f postgres-deployment.yaml

    # Deploy Redis
    print_status "Deploying Redis..."
    cat > redis-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-storage
          mountPath: /data
      volumes:
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: ${NAMESPACE}
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: ${NAMESPACE}
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
EOF

    kubectl apply -f redis-deployment.yaml

    # Deploy Django
    print_status "Deploying Django service..."
    cat > django-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django
  namespace: ${NAMESPACE}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: django
  template:
    metadata:
      labels:
        app: django
    spec:
      containers:
      - name: django
        image: ${ECR_REGISTRY}/llm-api/django:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: DATABASE_URL
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: REDIS_URL
        - name: DJANGO_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: DJANGO_SECRET_KEY
        livenessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: django
  namespace: ${NAMESPACE}
spec:
  selector:
    app: django
  ports:
  - port: 8000
    targetPort: 8000
EOF

    kubectl apply -f django-deployment.yaml

    # Deploy FastAPI
    print_status "Deploying FastAPI service..."
    cat > fastapi-deployment.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi
  namespace: ${NAMESPACE}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: fastapi
  template:
    metadata:
      labels:
        app: fastapi
    spec:
      containers:
      - name: fastapi
        image: ${ECR_REGISTRY}/llm-api/fastapi:latest
        ports:
        - containerPort: 8001
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: DATABASE_URL
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: REDIS_URL
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: fastapi
  namespace: ${NAMESPACE}
spec:
  selector:
    app: fastapi
  ports:
  - port: 8001
    targetPort: 8001
EOF

    kubectl apply -f fastapi-deployment.yaml

    # Create Ingress
    print_status "Creating Ingress..."
    cat > ingress.yaml << EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: llm-api-ingress
  namespace: ${NAMESPACE}
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  tls:
  - hosts:
    - ${DOMAIN_NAME}
    secretName: llm-api-tls
  rules:
  - host: ${DOMAIN_NAME}
    http:
      paths:
      - path: /api/v1/auth
        pathType: Prefix
        backend:
          service:
            name: django
            port:
              number: 8000
      - path: /admin
        pathType: Prefix
        backend:
          service:
            name: django
            port:
              number: 8000
      - path: /api/v1
        pathType: Prefix
        backend:
          service:
            name: fastapi
            port:
              number: 8001
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 3000
EOF

    kubectl apply -f ingress.yaml

    print_success "Application deployed"
}

# Deploy monitoring stack
deploy_monitoring() {
    print_status "Deploying monitoring stack..."

    # Add Prometheus Helm repo
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update

    # Install Prometheus
    print_status "Installing Prometheus..."
    helm install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --create-namespace \
        --set grafana.adminPassword=admin123 || true

    # Install AlertManager configuration
    kubectl apply -f kubernetes/services/monitoring/alertmanager.yaml || true

    print_success "Monitoring stack deployed"
}

# Wait for services to be ready
wait_for_services() {
    print_status "Waiting for services to be ready..."

    services=("postgres" "redis" "django" "fastapi")

    for service in "${services[@]}"; do
        print_status "Waiting for $service..."
        kubectl wait --for=condition=available --timeout=300s deployment/$service -n "$NAMESPACE" || true
    done

    print_success "Services are ready"
}

# Run database migrations
run_migrations() {
    print_status "Running database migrations..."

    # Wait for Django pod to be ready
    kubectl wait --for=condition=ready pod -l app=django -n "$NAMESPACE" --timeout=300s

    # Get Django pod name
    DJANGO_POD=$(kubectl get pods -n "$NAMESPACE" -l app=django -o jsonpath='{.items[0].metadata.name}')

    # Run migrations
    kubectl exec -n "$NAMESPACE" "$DJANGO_POD" -- python manage.py migrate

    # Create superuser
    kubectl exec -n "$NAMESPACE" "$DJANGO_POD" -- python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created')
"

    print_success "Database migrations completed"
}

# Get service URLs
get_service_urls() {
    print_status "Getting service URLs..."

    # Get LoadBalancer IP
    INGRESS_IP=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_success "🚀 LLM API Platform deployed successfully!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    print_status "📍 Service URLs:"
    echo ""

    if [ "$INGRESS_IP" != "pending" ]; then
        echo "   🌐 Public API: http://$INGRESS_IP"
        echo "   📊 Django Admin: http://$INGRESS_IP/admin/"
        echo "   🔧 FastAPI Docs: http://$INGRESS_IP/docs"
    else
        echo "   ⏳ LoadBalancer IP is pending. Check with:"
        echo "      kubectl get svc ingress-nginx-controller -n ingress-nginx"
    fi

    echo ""
    print_status "🔐 Admin Credentials:"
    echo "   Username: admin"
    echo "   Password: admin123"
    echo ""
    print_status "📊 Monitoring:"
    GRAFANA_IP=$(kubectl get svc prometheus-grafana -n monitoring -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")
    if [ "$GRAFANA_IP" != "pending" ]; then
        echo "   📈 Grafana: http://$GRAFANA_IP (admin/admin123)"
    else
        echo "   📈 Grafana: Access via kubectl port-forward"
        echo "      kubectl port-forward svc/prometheus-grafana -n monitoring 3000:80"
    fi

    echo ""
    print_status "🔧 Useful Commands:"
    echo "   View pods: kubectl get pods -n $NAMESPACE"
    echo "   View logs: kubectl logs -f deployment/django -n $NAMESPACE"
    echo "   Scale services: kubectl scale deployment django --replicas=3 -n $NAMESPACE"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Main deployment function
main() {
    echo ""
    echo "🚀 LLM API Platform - AWS EKS Deployment"
    echo "════════════════════════════════════════"
    echo ""

    print_warning "This script will deploy the LLM API Platform to AWS EKS."
    print_warning "Make sure you have:"
    print_warning "1. AWS credentials configured"
    print_warning "2. Sufficient AWS permissions (EKS, EC2, IAM)"
    print_warning "3. Docker running for building images"
    echo ""
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Deployment cancelled"
        exit 1
    fi

    check_prerequisites
    configure_aws
    create_ecr_repositories
    # build_and_push_images  # Commented out as we don't have actual Docker images
    create_eks_cluster
    install_k8s_tools
    deploy_application
    deploy_monitoring
    wait_for_services
    run_migrations
    get_service_urls

    print_success "🎉 Deployment completed successfully!"
}

# Cleanup function
cleanup() {
    print_warning "Cleaning up AWS resources..."

    print_status "Do you want to delete the EKS cluster? This will remove all resources. (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        eksctl delete cluster --name "$CLUSTER_NAME" --region "$AWS_REGION"
        print_success "Cluster deleted"
    fi
}

# Handle script arguments
case "${1:-}" in
    "cleanup")
        cleanup
        ;;
    *)
        main
        ;;
esac