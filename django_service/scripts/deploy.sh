#!/bin/bash

# Django EKS Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION="us-west-2"
CLUSTER_NAME="django-eks-cluster"
ECR_REPOSITORY="django-service"
IMAGE_TAG="${1:-latest}"
NAMESPACE="django-app"

echo -e "${GREEN}Starting Django EKS deployment...${NC}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check required tools
echo -e "${YELLOW}Checking required tools...${NC}"
required_tools=("aws" "kubectl" "docker" "terraform")
for tool in "${required_tools[@]}"; do
    if ! command_exists "$tool"; then
        echo -e "${RED}Error: $tool is not installed${NC}"
        exit 1
    fi
done
echo -e "${GREEN}All required tools are installed${NC}"

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo -e "${YELLOW}Building and pushing Docker image...${NC}"

# Build Docker image
docker build -t ${ECR_REPOSITORY}:${IMAGE_TAG} .

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URI}

# Tag and push image
docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}
docker push ${ECR_URI}:${IMAGE_TAG}

echo -e "${GREEN}Image pushed successfully: ${ECR_URI}:${IMAGE_TAG}${NC}"

# Update kubeconfig
echo -e "${YELLOW}Updating kubeconfig...${NC}"
aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER_NAME}

# Apply Kubernetes manifests
echo -e "${YELLOW}Applying Kubernetes manifests...${NC}"

# Create namespace
kubectl apply -f k8s/namespace.yaml

# Apply configuration
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# Apply storage
kubectl apply -f k8s/pvc.yaml

# Update deployment with new image
sed "s|your-account\.dkr\.ecr\.us-west-2\.amazonaws\.com/django-service:latest|${ECR_URI}:${IMAGE_TAG}|g" k8s/django-deployment.yaml | kubectl apply -f -

# Apply service and networking
kubectl apply -f k8s/django-service.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml

# Wait for deployment
echo -e "${YELLOW}Waiting for deployment to be ready...${NC}"
kubectl rollout status deployment/django-deployment -n ${NAMESPACE} --timeout=300s

# Get service status
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${YELLOW}Service status:${NC}"
kubectl get pods -n ${NAMESPACE}
kubectl get services -n ${NAMESPACE}
kubectl get ingress -n ${NAMESPACE}

# Get load balancer URL
LOAD_BALANCER=$(kubectl get ingress django-ingress -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
if [ ! -z "$LOAD_BALANCER" ]; then
    echo -e "${GREEN}Load Balancer URL: http://${LOAD_BALANCER}${NC}"
else
    echo -e "${YELLOW}Load Balancer URL not yet available. Check again in a few minutes.${NC}"
fi

echo -e "${GREEN}Deployment script completed!${NC}"