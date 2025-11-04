#!/bin/bash

# AWS Infrastructure Setup Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION="us-west-2"
CLUSTER_NAME="django-eks-cluster"
TERRAFORM_DIR="aws/terraform"

echo -e "${GREEN}Setting up AWS infrastructure for Django EKS deployment...${NC}"

# Check if Terraform is installed
if ! command -v terraform >/dev/null 2>&1; then
    echo -e "${RED}Error: Terraform is not installed${NC}"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo -e "${RED}Error: AWS CLI is not configured${NC}"
    exit 1
fi

# Navigate to Terraform directory
cd ${TERRAFORM_DIR}

echo -e "${YELLOW}Initializing Terraform...${NC}"
terraform init

echo -e "${YELLOW}Planning Terraform deployment...${NC}"
terraform plan -var="aws_region=${AWS_REGION}" -var="cluster_name=${CLUSTER_NAME}"

# Ask for confirmation
read -p "Do you want to proceed with the infrastructure deployment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

echo -e "${YELLOW}Applying Terraform configuration...${NC}"
terraform apply -var="aws_region=${AWS_REGION}" -var="cluster_name=${CLUSTER_NAME}" -auto-approve

# Get outputs
echo -e "${GREEN}Infrastructure deployed successfully!${NC}"
echo -e "${YELLOW}Getting infrastructure details...${NC}"

CLUSTER_ENDPOINT=$(terraform output -raw cluster_endpoint)
ECR_REPOSITORY_URL=$(terraform output -raw ecr_repository_url)
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
REDIS_ENDPOINT=$(terraform output -raw redis_endpoint)

echo -e "${GREEN}Infrastructure Details:${NC}"
echo "EKS Cluster Endpoint: ${CLUSTER_ENDPOINT}"
echo "ECR Repository URL: ${ECR_REPOSITORY_URL}"
echo "RDS Endpoint: ${RDS_ENDPOINT}"
echo "Redis Endpoint: ${REDIS_ENDPOINT}"

# Update kubeconfig
echo -e "${YELLOW}Updating kubeconfig...${NC}"
aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER_NAME}

# Install AWS Load Balancer Controller
echo -e "${YELLOW}Installing AWS Load Balancer Controller...${NC}"

# Create IAM OIDC provider
eksctl utils associate-iam-oidc-provider --region=${AWS_REGION} --cluster=${CLUSTER_NAME} --approve

# Download IAM policy
curl -o iam_policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.5.4/docs/install/iam_policy.json

# Create IAM policy
aws iam create-policy \
    --policy-name AWSLoadBalancerControllerIAMPolicy \
    --policy-document file://iam_policy.json \
    --region ${AWS_REGION} || true

# Create IAM role and service account
eksctl create iamserviceaccount \
  --cluster=${CLUSTER_NAME} \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --role-name AmazonEKSLoadBalancerControllerRole \
  --attach-policy-arn=arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/AWSLoadBalancerControllerIAMPolicy \
  --approve \
  --region=${AWS_REGION} || true

# Install AWS Load Balancer Controller using Helm
helm repo add eks https://aws.github.io/eks-charts || true
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=${CLUSTER_NAME} \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region=${AWS_REGION} \
  --set vpcId=$(terraform output -raw vpc_id) || true

# Install Nginx Ingress Controller
echo -e "${YELLOW}Installing Nginx Ingress Controller...${NC}"
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx || true
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"="nlb" || true

# Install cert-manager for SSL certificates
echo -e "${YELLOW}Installing cert-manager...${NC}"
helm repo add jetstack https://charts.jetstack.io || true
helm repo update

helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true || true

# Wait for cert-manager to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=300s

# Create ClusterIssuer for Let's Encrypt
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com  # Change this to your email
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

echo -e "${GREEN}Infrastructure setup completed successfully!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Update the domain in k8s/ingress.yaml"
echo "2. Update the email in the ClusterIssuer"
echo "3. Update the secrets in k8s/secrets.yaml with base64 encoded values"
echo "4. Run the deployment script: ./scripts/deploy.sh"

cd - >/dev/null