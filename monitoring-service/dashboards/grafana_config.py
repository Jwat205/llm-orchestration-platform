

import json
import os
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class GrafanaConfig:
    """Grafana instance configuration"""
    url: str
    username: str
    password: str
    org_id: int = 1
    timeout: int = 30

@dataclass
class DataSourceConfig:
    """Data source configuration for Grafana"""
    name: str
    type: str
    url: str
    database: str = ""
    username: str = ""
    password: str = ""
    is_default: bool = False

class GrafanaManager:
    """Manages Grafana dashboards, data sources, and configuration"""
    
    def __init__(self, config: GrafanaConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.username, config.password)
        self.session.timeout = config.timeout
        
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make authenticated request to Grafana API"""
        url = f"{self.config.url}/api/{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, headers=headers)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Grafana API request failed: {e}")
            raise
    
    def setup_data_sources(self) -> bool:
        """Configure all required data sources"""
        data_sources = [
            DataSourceConfig(
                name="Prometheus",
                type="prometheus",
                url=os.getenv("PROMETHEUS_URL", "http://prometheus:9090"),
                is_default=True
            ),
            DataSourceConfig(
                name="PostgreSQL",
                type="postgres",
                url=os.getenv("POSTGRES_HOST", "postgres:5432"),
                database=os.getenv("POSTGRES_DB", "llm_platform"),
                username=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", "password")
            ),
            DataSourceConfig(
                name="InfluxDB",
                type="influxdb",
                url=os.getenv("INFLUXDB_URL", "http://influxdb:8086"),
                database=os.getenv("INFLUXDB_DB", "metrics")
            ),
            DataSourceConfig(
                name="Elasticsearch",
                type="elasticsearch",
                url=os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200"),
                database="[logs-*]YYYY.MM.DD"
            )
        ]
        
        success_count = 0
        for ds_config in data_sources:
            try:
                self.create_data_source(ds_config)
                success_count += 1
                logger.info(f"Data source '{ds_config.name}' configured successfully")
            except Exception as e:
                logger.error(f"Failed to configure data source '{ds_config.name}': {e}")
                
        return success_count == len(data_sources)
    
    def create_data_source(self, ds_config: DataSourceConfig) -> Dict:
        """Create or update a data source"""
        data_source = {
            "name": ds_config.name,
            "type": ds_config.type,
            "url": ds_config.url,
            "access": "proxy",
            "isDefault": ds_config.is_default,
            "jsonData": {},
            "secureJsonData": {}
        }
        
        # Type-specific configurations
        if ds_config.type == "postgres":
            data_source["database"] = ds_config.database
            data_source["user"] = ds_config.username
            data_source["secureJsonData"]["password"] = ds_config.password
            data_source["jsonData"]["sslmode"] = "disable"
            data_source["jsonData"]["maxOpenConns"] = 100
            data_source["jsonData"]["maxIdleConns"] = 100
            data_source["jsonData"]["connMaxLifetime"] = 14400
            
        elif ds_config.type == "influxdb":
            data_source["database"] = ds_config.database
            data_source["jsonData"]["httpMode"] = "GET"
            data_source["jsonData"]["keepCookies"] = []
            
        elif ds_config.type == "elasticsearch":
            data_source["database"] = ds_config.database
            data_source["jsonData"]["interval"] = "Daily"
            data_source["jsonData"]["timeField"] = "@timestamp"
            data_source["jsonData"]["esVersion"] = "7.10.0"
            data_source["jsonData"]["maxConcurrentShardRequests"] = 5
            
        elif ds_config.type == "prometheus":
            data_source["jsonData"]["httpMethod"] = "POST"
            data_source["jsonData"]["keepCookies"] = []
            
        return self._make_request("POST", "datasources", data_source)
    
    def provision_dashboards(self, dashboard_dir: str = "dashboards") -> bool:
        """Provision all dashboards from directory"""
        dashboard_path = Path(dashboard_dir)
        if not dashboard_path.exists():
            logger.error(f"Dashboard directory '{dashboard_dir}' not found")
            return False
            
        success_count = 0
        total_count = 0
        
        for dashboard_file in dashboard_path.glob("*.json"):
            total_count += 1
            try:
                with open(dashboard_file, 'r') as f:
                    dashboard_json = json.load(f)
                    
                self.import_dashboard(dashboard_json)
                success_count += 1
                logger.info(f"Dashboard '{dashboard_file.name}' imported successfully")
                
            except Exception as e:
                logger.error(f"Failed to import dashboard '{dashboard_file.name}': {e}")
                
        return success_count == total_count
    
    def import_dashboard(self, dashboard_json: Dict) -> Dict:
        """Import a single dashboard"""
        # Remove id and version to allow updates
        if 'id' in dashboard_json:
            del dashboard_json['id']
        if 'version' in dashboard_json:
            del dashboard_json['version']
            
        import_data = {
            "dashboard": dashboard_json,
            "overwrite": True,
            "inputs": []
        }
        
        return self._make_request("POST", "dashboards/db", import_data)
    
    def create_alert_rules(self) -> bool:
        """Create alerting rules for the platform"""
        alert_rules = [
            {
                "alert": {
                    "name": "High API Latency",
                    "message": "API response time is above threshold",
                    "frequency": "10s",
                    "conditions": [
                        {
                            "query": {
                                "queryType": "",
                                "refId": "A",
                                "datasourceUid": "prometheus",
                                "model": {
                                    "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5",
                                    "interval": "",
                                    "refId": "A"
                                }
                            },
                            "reducer": {
                                "type": "last",
                                "params": []
                            },
                            "evaluator": {
                                "params": [0.5],
                                "type": "gt"
                            }
                        }
                    ]
                }
            },
            {
                "alert": {
                    "name": "High Error Rate",
                    "message": "API error rate is above 5%",
                    "frequency": "30s",
                    "conditions": [
                        {
                            "query": {
                                "queryType": "",
                                "refId": "A",
                                "datasourceUid": "prometheus",
                                "model": {
                                    "expr": "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m]) > 0.05",
                                    "interval": "",
                                    "refId": "A"
                                }
                            },
                            "reducer": {
                                "type": "last",
                                "params": []
                            },
                            "evaluator": {
                                "params": [0.05],
                                "type": "gt"
                            }
                        }
                    ]
                }
            },
            {
                "alert": {
                    "name": "GPU Memory Usage High",
                    "message": "GPU memory usage is above 90%",
                    "frequency": "30s",
                    "conditions": [
                        {
                            "query": {
                                "queryType": "",
                                "refId": "A",
                                "datasourceUid": "prometheus",
                                "model": {
                                    "expr": "nvidia_ml_py_memory_used_bytes / nvidia_ml_py_memory_total_bytes > 0.9",
                                    "interval": "",
                                    "refId": "A"
                                }
                            },
                            "reducer": {
                                "type": "last",
                                "params": []
                            },
                            "evaluator": {
                                "params": [0.9],
                                "type": "gt"
                            }
                        }
                    ]
                }
            }
        ]
        
        success_count = 0
        for rule in alert_rules:
            try:
                self._make_request("POST", "alerts", rule)
                success_count += 1
                logger.info(f"Alert rule '{rule['alert']['name']}' created successfully")
            except Exception as e:
                logger.error(f"Failed to create alert rule '{rule['alert']['name']}': {e}")
                
        return success_count == len(alert_rules)
    
    def setup_notification_channels(self) -> bool:
        """Setup notification channels for alerts"""
        channels = [
            {
                "name": "slack-alerts",
                "type": "slack",
                "settings": {
                    "url": os.getenv("SLACK_WEBHOOK_URL", ""),
                    "channel": "#alerts",
                    "username": "Grafana",
                    "title": "LLM Platform Alert",
                    "text": "{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}"
                }
            },
            {
                "name": "email-alerts",
                "type": "email",
                "settings": {
                    "addresses": os.getenv("ALERT_EMAIL_ADDRESSES", "admin@company.com").split(","),
                    "subject": "LLM Platform Alert: {{ .GroupLabels.alertname }}",
                    "body": "{{ range .Alerts }}{{ .Annotations.description }}{{ end }}"
                }
            },
            {
                "name": "pagerduty-critical",
                "type": "pagerduty",
                "settings": {
                    "integrationKey": os.getenv("PAGERDUTY_INTEGRATION_KEY", ""),
                    "severity": "critical",
                    "class": "LLM Platform",
                    "component": "API"
                }
            }
        ]
        
        success_count = 0
        for channel in channels:
            try:
                # Skip if required settings are missing
                if channel["type"] == "slack" and not channel["settings"]["url"]:
                    continue
                if channel["type"] == "pagerduty" and not channel["settings"]["integrationKey"]:
                    continue
                    
                self._make_request("POST", "alert-notifications", channel)
                success_count += 1
                logger.info(f"Notification channel '{channel['name']}' created successfully")
            except Exception as e:
                logger.error(f"Failed to create notification channel '{channel['name']}': {e}")
                
        return success_count > 0
    
    def health_check(self) -> bool:
        """Check if Grafana is healthy and accessible"""
        try:
            response = self._make_request("GET", "health")
            return response.get("status") == "ok"
        except Exception as e:
            logger.error(f"Grafana health check failed: {e}")
            return False

def initialize_grafana():
    """Initialize Grafana with all configurations"""
    config = GrafanaConfig(
        url=os.getenv("GRAFANA_URL", "http://grafana:3000"),
        username=os.getenv("GRAFANA_USER", "admin"),
        password=os.getenv("GRAFANA_PASSWORD", "admin")
    )
    
    manager = GrafanaManager(config)
    
    # Wait for Grafana to be ready
    import time
    max_retries = 30
    for i in range(max_retries):
        if manager.health_check():
            logger.info("Grafana is ready")
            break
        time.sleep(2)
        logger.info(f"Waiting for Grafana... ({i+1}/{max_retries})")
    else:
        logger.error("Grafana failed to become ready")
        return False
    
    # Setup all components
    success = True
    success &= manager.setup_data_sources()
    success &= manager.provision_dashboards()
    success &= manager.create_alert_rules()
    success &= manager.setup_notification_channels()
    
    if success:
        logger.info("Grafana initialization completed successfully")
    else:
        logger.error("Grafana initialization completed with errors")
        
    return success

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    initialize_grafana()
