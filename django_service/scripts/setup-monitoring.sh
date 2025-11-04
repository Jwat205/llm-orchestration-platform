#!/bin/bash

# Monitoring Setup Script for Django EKS
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up monitoring for Django EKS deployment...${NC}"

# Check if helm is installed
if ! command -v helm >/dev/null 2>&1; then
    echo -e "${RED}Error: Helm is not installed${NC}"
    exit 1
fi

# Create monitoring namespace
echo -e "${YELLOW}Creating monitoring namespace...${NC}"
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

# Add Helm repositories
echo -e "${YELLOW}Adding Helm repositories...${NC}"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add fluent https://fluent.github.io/helm-charts
helm repo update

# Install Prometheus
echo -e "${YELLOW}Installing Prometheus...${NC}"
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName=gp2 \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi \
  --set alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.storageClassName=gp2 \
  --set alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.resources.requests.storage=10Gi \
  --set grafana.persistence.enabled=true \
  --set grafana.persistence.storageClassName=gp2 \
  --set grafana.persistence.size=10Gi \
  --set grafana.adminPassword=admin123 \
  --wait

# Create ServiceMonitor for Django app
echo -e "${YELLOW}Creating ServiceMonitor for Django application...${NC}"
cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: django-service-monitor
  namespace: monitoring
  labels:
    app: django
spec:
  selector:
    matchLabels:
      app: django
  namespaceSelector:
    matchNames:
    - django-app
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
EOF

# Install Fluentd for log collection
echo -e "${YELLOW}Installing Fluentd...${NC}"
helm upgrade --install fluentd fluent/fluentd \
  --namespace kube-system \
  --set rbac.create=true \
  --set serviceAccount.create=true \
  --set image.repository=fluent/fluentd-kubernetes-daemonset \
  --set image.tag=v1.16-debian-elasticsearch7-1 \
  --set env[0].name=FLUENT_ELASTICSEARCH_HOST \
  --set env[0].value=elasticsearch-logging.kube-system.svc.cluster.local \
  --set env[1].name=FLUENT_ELASTICSEARCH_PORT \
  --set env[1].value="9200" \
  --set env[2].name=AWS_REGION \
  --set env[2].value=us-west-2 \
  --wait

# Apply custom Fluentd configuration
kubectl apply -f monitoring/fluentd-config.yaml

# Install Elasticsearch (optional - for centralized logging)
echo -e "${YELLOW}Do you want to install Elasticsearch for centralized logging? (y/N)${NC}"
read -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Installing Elasticsearch...${NC}"
    helm repo add elastic https://helm.elastic.co
    helm repo update
    
    helm upgrade --install elasticsearch elastic/elasticsearch \
      --namespace kube-system \
      --set replicas=3 \
      --set minimumMasterNodes=2 \
      --set resources.requests.cpu=500m \
      --set resources.requests.memory=2Gi \
      --set resources.limits.cpu=1000m \
      --set resources.limits.memory=2Gi \
      --set volumeClaimTemplate.resources.requests.storage=30Gi \
      --set volumeClaimTemplate.storageClassName=gp2 \
      --wait
    
    # Install Kibana
    echo -e "${YELLOW}Installing Kibana...${NC}"
    helm upgrade --install kibana elastic/kibana \
      --namespace kube-system \
      --set service.type=LoadBalancer \
      --wait
fi

# Create Grafana dashboard
echo -e "${YELLOW}Importing Grafana dashboard...${NC}"
kubectl create configmap django-dashboard \
  --from-file=monitoring/grafana-dashboard.json \
  --namespace=monitoring \
  --dry-run=client -o yaml | kubectl apply -f -

# Get service URLs
echo -e "${GREEN}Monitoring setup completed!${NC}"
echo
echo -e "${YELLOW}Access URLs:${NC}"

# Prometheus
PROMETHEUS_LB=$(kubectl get svc prometheus-kube-prometheus-prometheus -n monitoring -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
if [ ! -z "$PROMETHEUS_LB" ]; then
    echo "Prometheus: http://$PROMETHEUS_LB:9090"
else
    echo "Prometheus: kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n monitoring"
fi

# Grafana
GRAFANA_LB=$(kubectl get svc prometheus-grafana -n monitoring -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
if [ ! -z "$GRAFANA_LB" ]; then
    echo "Grafana: http://$GRAFANA_LB (admin/admin123)"
else
    echo "Grafana: kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring (admin/admin123)"
fi

# AlertManager
ALERTMANAGER_LB=$(kubectl get svc prometheus-kube-prometheus-alertmanager -n monitoring -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
if [ ! -z "$ALERTMANAGER_LB" ]; then
    echo "AlertManager: http://$ALERTMANAGER_LB:9093"
else
    echo "AlertManager: kubectl port-forward svc/prometheus-kube-prometheus-alertmanager 9093:9093 -n monitoring"
fi

# Kibana (if installed)
KIBANA_LB=$(kubectl get svc kibana-kibana -n kube-system -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
if [ ! -z "$KIBANA_LB" ]; then
    echo "Kibana: http://$KIBANA_LB:5601"
fi

echo
echo -e "${GREEN}Monitoring stack is ready!${NC}"
echo -e "${YELLOW}Note: It may take a few minutes for all services to be fully available.${NC}"