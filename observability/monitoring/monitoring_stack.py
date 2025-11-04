"""
Comprehensive Monitoring Stack for LLM Platform
Orchestrates all monitoring components and provides unified interface
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import os
import subprocess
import threading
from contextlib import asynccontextmanager

# Import monitoring components
try:
    from .business_metrics import business_metrics, BusinessMetricsCollector
    from ..performance_optimization.profiling.fastapi_profiler import FastAPIProfiler
    from ..performance_optimization.optimization.memory_optimizer import memory_profiler, memory_optimizer
except ImportError:
    # Fallback imports for standalone usage
    business_metrics = None
    memory_profiler = None
    memory_optimizer = None

logger = logging.getLogger(__name__)

class MonitoringComponent(Enum):
    PROMETHEUS = "prometheus"
    GRAFANA = "grafana"
    ALERTMANAGER = "alertmanager"
    JAEGER = "jaeger"
    ELASTICSEARCH = "elasticsearch"
    LOGSTASH = "logstash"
    KIBANA = "kibana"

@dataclass
class ComponentHealth:
    """Health status of a monitoring component"""
    name: str
    status: str  # healthy, unhealthy, degraded, unknown
    uptime: float
    last_check: datetime
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

class MonitoringStack:
    """
    Unified monitoring stack management for LLM Platform
    """
    
    def __init__(self, config_dir: str = "./observability"):
        self.config_dir = config_dir
        self.components: Dict[str, ComponentHealth] = {}
        self.monitoring_active = False
        self.health_check_interval = 30  # seconds
        self.health_check_thread: Optional[threading.Thread] = None
        
        # Component configurations
        self.component_configs = {
            MonitoringComponent.PROMETHEUS: {
                'port': 9090,
                'config_file': 'infrastructure/observability/prometheus/prometheus.yml',
                'health_endpoint': '/api/v1/status/config'
            },
            MonitoringComponent.GRAFANA: {
                'port': 3000,
                'config_file': 'infrastructure/observability/grafana/grafana.ini',
                'health_endpoint': '/api/health'
            },
            MonitoringComponent.ALERTMANAGER: {
                'port': 9093,
                'config_file': 'observability/alerting/alertmanager.yml',
                'health_endpoint': '/-/healthy'
            },
            MonitoringComponent.JAEGER: {
                'port': 16686,
                'config_file': 'infrastructure/observability/jaeger/jaeger-deployment.yaml',
                'health_endpoint': '/'
            },
            MonitoringComponent.ELASTICSEARCH: {
                'port': 9200,
                'config_file': 'infrastructure/observability/elk-stack/elasticsearch.yml',
                'health_endpoint': '/_cluster/health'
            },
            MonitoringComponent.LOGSTASH: {
                'port': 9600,
                'config_file': 'infrastructure/observability/elk-stack/logstash.conf',
                'health_endpoint': '/'
            },
            MonitoringComponent.KIBANA: {
                'port': 5601,
                'config_file': 'infrastructure/observability/elk-stack/kibana.yml',
                'health_endpoint': '/api/status'
            }
        }
        
        # Initialize component health tracking
        for component in MonitoringComponent:
            self.components[component.value] = ComponentHealth(
                name=component.value,
                status="unknown",
                uptime=0,
                last_check=datetime.now()
            )
    
    async def start_monitoring(self):
        """Start the complete monitoring stack"""
        logger.info("Starting LLM Platform monitoring stack...")
        
        # Start health monitoring
        self.monitoring_active = True
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self.health_check_thread.start()
        
        # Initialize business metrics if available
        if business_metrics:
            logger.info("Initializing business metrics collection...")
            # Start any background collection tasks
        
        # Initialize memory monitoring if available
        if memory_profiler:
            memory_profiler.start_monitoring(interval=30.0)
            logger.info("Memory monitoring started")
        
        # Start component-specific monitoring
        await self._start_component_monitoring()
        
        logger.info("Monitoring stack startup complete")
    
    async def stop_monitoring(self):
        """Stop the monitoring stack"""
        logger.info("Stopping monitoring stack...")
        
        self.monitoring_active = False
        
        if self.health_check_thread:
            self.health_check_thread.join(timeout=10)
        
        if memory_profiler:
            memory_profiler.stop_monitoring()
        
        logger.info("Monitoring stack stopped")
    
    def _health_check_loop(self):
        """Background health checking loop"""
        while self.monitoring_active:
            try:
                for component_name in self.components:
                    self._check_component_health(component_name)
                
                # Log overall health summary
                healthy_count = sum(1 for c in self.components.values() 
                                  if c.status == "healthy")
                total_count = len(self.components)
                
                if healthy_count < total_count:
                    logger.warning(f"Monitoring health: {healthy_count}/{total_count} components healthy")
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            time.sleep(self.health_check_interval)
    
    def _check_component_health(self, component_name: str):
        """Check health of a specific component"""
        try:
            component = self.components[component_name]
            config = self.component_configs.get(MonitoringComponent(component_name))
            
            if not config:
                component.status = "unknown"
                return
            
            # Simple port check (in production, use proper health endpoints)
            port = config['port']
            
            # Use netstat or similar to check if port is listening
            result = subprocess.run(
                ['netstat', '-an'], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if f":{port}" in result.stdout:
                component.status = "healthy"
                component.uptime += self.health_check_interval
                component.error_message = None
            else:
                component.status = "unhealthy"
                component.error_message = f"Port {port} not accessible"
                component.uptime = 0
            
            component.last_check = datetime.now()
            
        except subprocess.TimeoutExpired:
            component.status = "degraded"
            component.error_message = "Health check timeout"
        except Exception as e:
            component.status = "unhealthy"
            component.error_message = str(e)
            component.uptime = 0
    
    async def _start_component_monitoring(self):
        """Start monitoring for each component"""
        for component, config in self.component_configs.items():
            try:
                await self._initialize_component_monitoring(component, config)
            except Exception as e:
                logger.error(f"Failed to initialize monitoring for {component.value}: {e}")
    
    async def _initialize_component_monitoring(self, component: MonitoringComponent, config: Dict):
        """Initialize monitoring for a specific component"""
        logger.info(f"Initializing monitoring for {component.value}")
        
        # Component-specific initialization logic would go here
        # For example, setting up custom metrics collectors, dashboards, etc.
        
        if component == MonitoringComponent.PROMETHEUS:
            await self._setup_prometheus_monitoring()
        elif component == MonitoringComponent.GRAFANA:
            await self._setup_grafana_monitoring()
        elif component == MonitoringComponent.ELASTICSEARCH:
            await self._setup_elasticsearch_monitoring()
    
    async def _setup_prometheus_monitoring(self):
        """Setup Prometheus-specific monitoring"""
        logger.info("Setting up Prometheus monitoring configuration")
        # Here you would configure custom Prometheus rules, targets, etc.
    
    async def _setup_grafana_monitoring(self):
        """Setup Grafana-specific monitoring"""
        logger.info("Setting up Grafana dashboards and alerts")
        # Here you would import dashboards, setup data sources, etc.
    
    async def _setup_elasticsearch_monitoring(self):
        """Setup Elasticsearch-specific monitoring"""
        logger.info("Setting up Elasticsearch index templates and monitoring")
        # Here you would setup index templates, monitoring indices, etc.
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary"""
        healthy_components = [c for c in self.components.values() if c.status == "healthy"]
        unhealthy_components = [c for c in self.components.values() if c.status == "unhealthy"]
        degraded_components = [c for c in self.components.values() if c.status == "degraded"]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_status': self._calculate_overall_status(),
            'component_count': len(self.components),
            'healthy_count': len(healthy_components),
            'unhealthy_count': len(unhealthy_components),
            'degraded_count': len(degraded_components),
            'components': {
                name: {
                    'status': comp.status,
                    'uptime_seconds': comp.uptime,
                    'last_check': comp.last_check.isoformat(),
                    'error_message': comp.error_message
                }
                for name, comp in self.components.items()
            }
        }
    
    def _calculate_overall_status(self) -> str:
        """Calculate overall monitoring stack status"""
        statuses = [c.status for c in self.components.values()]
        
        if all(s == "healthy" for s in statuses):
            return "healthy"
        elif any(s == "unhealthy" for s in statuses):
            return "unhealthy"
        elif any(s == "degraded" for s in statuses):
            return "degraded"
        else:
            return "unknown"
    
    def get_business_metrics_summary(self) -> Dict[str, Any]:
        """Get business metrics summary"""
        if business_metrics:
            return business_metrics.get_business_summary()
        return {'message': 'Business metrics not available'}
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance monitoring summary"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'memory_monitoring_active': False,
            'profiling_active': False
        }
        
        if memory_profiler:
            summary['memory_monitoring_active'] = memory_profiler.monitoring_active
            if memory_profiler.memory_history:
                latest = memory_profiler.memory_history[-1]
                summary['latest_memory_stats'] = {
                    'process_memory_mb': latest.process_memory_mb,
                    'system_memory_percent': latest.system_memory_percent,
                    'gpu_memory_mb': latest.gpu_memory_mb,
                    'python_objects': latest.python_objects
                }
        
        return summary
    
    def trigger_alert_test(self, alert_name: str, severity: str = "warning") -> Dict[str, Any]:
        """Trigger a test alert for validation"""
        test_alert = {
            'alert_name': alert_name,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'description': f"Test alert: {alert_name}",
            'source': 'monitoring_stack'
        }
        
        logger.warning(f"Test alert triggered: {test_alert}")
        
        # In production, this would send to Alertmanager
        return {
            'status': 'sent',
            'alert': test_alert
        }
    
    def get_monitoring_recommendations(self) -> List[Dict[str, Any]]:
        """Get monitoring optimization recommendations"""
        recommendations = []
        
        # Check component health
        unhealthy = [c for c in self.components.values() if c.status != "healthy"]
        if unhealthy:
            recommendations.append({
                'type': 'component_health',
                'priority': 'high',
                'issue': f"{len(unhealthy)} monitoring components unhealthy",
                'recommendation': 'Check and restart unhealthy monitoring components',
                'affected_components': [c.name for c in unhealthy]
            })
        
        # Check if business metrics are available
        if not business_metrics:
            recommendations.append({
                'type': 'business_metrics',
                'priority': 'medium',
                'issue': 'Business metrics not available',
                'recommendation': 'Install prometheus_client and initialize business metrics'
            })
        
        # Check memory monitoring
        if not memory_profiler or not memory_profiler.monitoring_active:
            recommendations.append({
                'type': 'memory_monitoring',
                'priority': 'medium',
                'issue': 'Memory monitoring not active',
                'recommendation': 'Enable memory monitoring for better performance tracking'
            })
        
        return recommendations
    
    @asynccontextmanager
    async def monitoring_context(self):
        """Context manager for monitoring lifecycle"""
        try:
            await self.start_monitoring()
            yield self
        finally:
            await self.stop_monitoring()

# Global monitoring stack instance
monitoring_stack = MonitoringStack()

# Convenience functions
async def start_monitoring():
    """Start the global monitoring stack"""
    await monitoring_stack.start_monitoring()

async def stop_monitoring():
    """Stop the global monitoring stack"""
    await monitoring_stack.stop_monitoring()

def get_monitoring_health():
    """Get monitoring stack health"""
    return monitoring_stack.get_health_summary()

def get_business_summary():
    """Get business metrics summary"""
    return monitoring_stack.get_business_metrics_summary()

def get_performance_summary():
    """Get performance monitoring summary"""
    return monitoring_stack.get_performance_summary()

# Example usage and testing
async def main():
    """Example usage of the monitoring stack"""
    async with monitoring_stack.monitoring_context():
        print("Monitoring stack started")
        
        # Wait for a few health checks
        await asyncio.sleep(65)
        
        # Get health summary
        health = monitoring_stack.get_health_summary()
        print(f"Health Summary: {json.dumps(health, indent=2)}")
        
        # Get recommendations
        recommendations = monitoring_stack.get_monitoring_recommendations()
        print(f"Recommendations: {json.dumps(recommendations, indent=2)}")
        
        # Test alert
        alert_result = monitoring_stack.trigger_alert_test("TestAlert", "warning")
        print(f"Test Alert: {json.dumps(alert_result, indent=2)}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())