
"""
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class PanelType(Enum):
    """Supported panel types"""
    GRAPH = "graph"
    STAT = "stat"
    TABLE = "table"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    BAR_GAUGE = "bargauge"
    PIE_CHART = "piechart"
    TEXT = "text"
    LOGS = "logs"
    NODE_GRAPH = "nodeGraph"

class TimeRange(Enum):
    """Common time ranges"""
    LAST_5M = "5m"
    LAST_15M = "15m"
    LAST_1H = "1h"
    LAST_6H = "6h"
    LAST_24H = "24h"
    LAST_7D = "7d"
    LAST_30D = "30d"

@dataclass
class Target:
    """Prometheus query target"""
    expr: str
    refId: str = "A"
    interval: str = ""
    legendFormat: str = ""
    instant: bool = False
    exemplar: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "expr": self.expr,
            "refId": self.refId,
            "interval": self.interval,
            "legendFormat": self.legendFormat,
            "instant": self.instant,
            "exemplar": self.exemplar,
            "datasource": {"type": "prometheus", "uid": "prometheus"}
        }

@dataclass
class GridPos:
    """Panel grid position"""
    h: int
    w: int
    x: int
    y: int

class CustomWidgets:
    """Factory for creating custom dashboard widgets"""
    
    @staticmethod
    def create_api_latency_panel(grid_pos: GridPos) -> Dict:
        """API latency percentiles panel"""
        return {
            "id": 1,
            "title": "API Response Time Percentiles",
            "type": PanelType.GRAPH.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{job="fastapi-service"}[5m]))',
                    legendFormat="50th percentile",
                    refId="A"
                ).to_dict(),
                Target(
                    expr='histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="fastapi-service"}[5m]))',
                    legendFormat="95th percentile",
                    refId="B"
                ).to_dict(),
                Target(
                    expr='histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{job="fastapi-service"}[5m]))',
                    legendFormat="99th percentile",
                    refId="C"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                        "lineInterpolation": "linear",
                        "lineWidth": 2,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "red", "value": 0.5}
                        ]
                    },
                    "unit": "s"
                }
            },
            "options": {
                "legend": {"displayMode": "table", "placement": "bottom"},
                "tooltip": {"mode": "multi", "sort": "none"}
            }
        }
    
    @staticmethod
    def create_request_rate_panel(grid_pos: GridPos) -> Dict:
        """Requests per second panel"""
        return {
            "id": 2,
            "title": "Request Rate (req/sec)",
            "type": PanelType.STAT.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='sum(rate(http_requests_total{job="fastapi-service"}[5m]))',
                    legendFormat="Requests/sec",
                    refId="A"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 100},
                            {"color": "red", "value": 1000}
                        ]
                    },
                    "unit": "reqps"
                }
            },
            "options": {
                "colorMode": "background",
                "graphMode": "area",
                "justifyMode": "center",
                "orientation": "horizontal",
                "reduceOptions": {
                    "values": False,
                    "calcs": ["lastNotNull"],
                    "fields": ""
                },
                "textMode": "auto"
            }
        }
    
    @staticmethod
    def create_error_rate_panel(grid_pos: GridPos) -> Dict:
        """Error rate percentage panel"""
        return {
            "id": 3,
            "title": "Error Rate",
            "type": PanelType.GAUGE.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='sum(rate(http_requests_total{job="fastapi-service",status=~"5.."}[5m])) / sum(rate(http_requests_total{job="fastapi-service"}[5m])) * 100',
                    legendFormat="Error Rate %",
                    refId="A"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "max": 10,
                    "min": 0,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 1},
                            {"color": "red", "value": 5}
                        ]
                    },
                    "unit": "percent"
                }
            },
            "options": {
                "orientation": "auto",
                "reduceOptions": {
                    "values": False,
                    "calcs": ["lastNotNull"],
                    "fields": ""
                },
                "showThresholdLabels": False,
                "showThresholdMarkers": True
            }
        }
    
    @staticmethod
    def create_model_usage_panel(grid_pos: GridPos) -> Dict:
        """Model usage distribution panel"""
        return {
            "id": 4,
            "title": "Model Usage Distribution",
            "type": PanelType.PIE_CHART.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='sum by (model) (increase(llm_requests_total[1h]))',
                    legendFormat="{{model}}",
                    refId="A"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False}
                    },
                    "mappings": []
                }
            },
            "options": {
                "reduceOptions": {
                    "values": False,
                    "calcs": ["lastNotNull"],
                    "fields": ""
                },
                "pieType": "pie",
                "tooltip": {"mode": "single", "sort": "none"},
                "legend": {"displayMode": "table", "placement": "right"},
                "displayLabels": ["name", "percent"]
            }
        }
    
    @staticmethod
    def create_gpu_metrics_panel(grid_pos: GridPos) -> Dict:
        """GPU utilization and memory panel"""
        return {
            "id": 5,
            "title": "GPU Metrics",
            "type": PanelType.GRAPH.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='nvidia_ml_py_utilization_gpu',
                    legendFormat="GPU {{instance}} Utilization %",
                    refId="A"
                ).to_dict(),
                Target(
                    expr='nvidia_ml_py_memory_used_bytes / nvidia_ml_py_memory_total_bytes * 100',
                    legendFormat="GPU {{instance}} Memory %",
                    refId="B"
                ).to_dict(),
                Target(
                    expr='nvidia_ml_py_temperature_gpu',
                    legendFormat="GPU {{instance}} Temperature °C",
                    refId="C"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                        "lineInterpolation": "linear",
                        "lineWidth": 2,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 80},
                            {"color": "red", "value": 90}
                        ]
                    },
                    "unit": "percent"
                }
            },
            "options": {
                "legend": {"displayMode": "table", "placement": "bottom"},
                "tooltip": {"mode": "multi", "sort": "none"}
            },
            "yAxes": [
                {
                    "label": "Percentage",
                    "max": 100,
                    "min": 0,
                    "show": True
                }
            ]
        }
    
    @staticmethod
    def create_token_metrics_panel(grid_pos: GridPos) -> Dict:
        """Token generation metrics panel"""
        return {
            "id": 6,
            "title": "Token Generation Metrics",
            "type": PanelType.GRAPH.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='rate(llm_tokens_generated_total[5m])',
                    legendFormat="Tokens/sec - {{model}}",
                    refId="A"
                ).to_dict(),
                Target(
                    expr='histogram_quantile(0.95, rate(llm_tokens_per_second_bucket[5m]))',
                    legendFormat="95th percentile tokens/sec",
                    refId="B"
                ).to_dict(),
                Target(
                    expr='avg(llm_context_length)',
                    legendFormat="Average context length",
                    refId="C"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                        "lineInterpolation": "linear",
                        "lineWidth": 2,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None}
                        ]
                    },
                    "unit": "short"
                }
            },
            "options": {
                "legend": {"displayMode": "table", "placement": "bottom"},
                "tooltip": {"mode": "multi", "sort": "none"}
            }
        }
    
    @staticmethod
    def create_cost_analysis_panel(grid_pos: GridPos) -> Dict:
        """Cost analysis panel"""
        return {
            "id": 7,
            "title": "Cost Analysis (Last 24h)",
            "type": PanelType.TABLE.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='sum by (user_id, model) (increase(llm_cost_dollars[24h]))',
                    legendFormat="Cost by User/Model",
                    refId="A",
                    instant=True
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "custom": {
                        "align": "auto",
                        "displayMode": "auto",
                        "inspect": False
                    },
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 10},
                            {"color": "red", "value": 100}
                        ]
                    },
                    "unit": "currencyUSD"
                }
            },
            "options": {
                "showHeader": True,
                "sortBy": [{"desc": True, "displayName": "Value"}]
            },
            "transformations": [
                {
                    "id": "organize",
                    "options": {
                        "excludeByName": {},
                        "indexByName": {},
                        "renameByName": {
                            "user_id": "User ID",
                            "model": "Model",
                            "Value": "Cost ($)"
                        }
                    }
                }
            ]
        }
    
    @staticmethod
    def create_database_performance_panel(grid_pos: GridPos) -> Dict:
        """Database performance metrics panel"""
        return {
            "id": 8,
            "title": "Database Performance",
            "type": PanelType.GRAPH.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='rate(postgresql_queries_total[5m])',
                    legendFormat="Queries/sec",
                    refId="A"
                ).to_dict(),
                Target(
                    expr='avg(postgresql_query_duration_seconds)',
                    legendFormat="Avg Query Duration",
                    refId="B"
                ).to_dict(),
                Target(
                    expr='postgresql_connections_active',
                    legendFormat="Active Connections",
                    refId="C"
                ).to_dict(),
                Target(
                    expr='rate(postgresql_deadlocks_total[5m])',
                    legendFormat="Deadlocks/sec",
                    refId="D"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                        "lineInterpolation": "linear",
                        "lineWidth": 2,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None}
                        ]
                    },
                    "unit": "short"
                }
            },
            "options": {
                "legend": {"displayMode": "table", "placement": "bottom"},
                "tooltip": {"mode": "multi", "sort": "none"}
            }
        }
    
    @staticmethod
    def create_cache_performance_panel(grid_pos: GridPos) -> Dict:
        """Redis cache performance panel"""
        return {
            "id": 9,
            "title": "Cache Performance",
            "type": PanelType.GRAPH.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='redis_cache_hit_rate * 100',
                    legendFormat="Cache Hit Rate %",
                    refId="A"
                ).to_dict(),
                Target(
                    expr='rate(redis_commands_total[5m])',
                    legendFormat="Commands/sec",
                    refId="B"
                ).to_dict(),
                Target(
                    expr='redis_memory_used_bytes / redis_memory_max_bytes * 100',
                    legendFormat="Memory Usage %",
                    refId="C"
                ).to_dict(),
                Target(
                    expr='redis_connected_clients',
                    legendFormat="Connected Clients",
                    refId="D"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                        "lineInterpolation": "linear",
                        "lineWidth": 2,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None}
                        ]
                    },
                    "unit": "short"
                }
            },
            "options": {
                "legend": {"displayMode": "table", "placement": "bottom"},
                "tooltip": {"mode": "multi", "sort": "none"}
            }
        }
    
    @staticmethod
    def create_system_resources_panel(grid_pos: GridPos) -> Dict:
        """System resource utilization panel"""
        return {
            "id": 10,
            "title": "System Resources",
            "type": PanelType.GRAPH.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
                    legendFormat="CPU Usage %",
                    refId="A"
                ).to_dict(),
                Target(
                    expr='(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
                    legendFormat="Memory Usage %",
                    refId="B"
                ).to_dict(),
                Target(
                    expr='100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)',
                    legendFormat="Disk Usage %",
                    refId="C"
                ).to_dict(),
                Target(
                    expr='rate(node_network_receive_bytes_total[5m]) * 8',
                    legendFormat="Network In (bps)",
                    refId="D"
                ).to_dict(),
                Target(
                    expr='rate(node_network_transmit_bytes_total[5m]) * 8',
                    legendFormat="Network Out (bps)",
                    refId="E"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                        "lineInterpolation": "linear",
                        "lineWidth": 2,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 70},
                            {"color": "red", "value": 90}
                        ]
                    },
                    "unit": "percent"
                }
            },
            "options": {
                "legend": {"displayMode": "table", "placement": "bottom"},
                "tooltip": {"mode": "multi", "sort": "none"}
            }
        }
    
    @staticmethod
    def create_user_activity_heatmap(grid_pos: GridPos) -> Dict:
        """User activity heatmap panel"""
        return {
            "id": 11,
            "title": "User Activity Heatmap (Requests per Hour)",
            "type": PanelType.HEATMAP.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='sum by (hour) (increase(http_requests_total{job="fastapi-service"}[1h]))',
                    legendFormat="Requests",
                    refId="A"
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {
                        "mode": "spectrum",
                        "scheme": "Spectral",
                        "steps": 128
                    },
                    "custom": {
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False}
                    },
                    "mappings": []
                }
            },
            "options": {
                "calculate": False,
                "calculation": {},
                "cellGap": 2,
                "cellValues": {},
                "color": {
                    "exponent": 0.5,
                    "fill": "dark-orange",
                    "mode": "spectrum",
                    "reverse": False,
                    "scale": "exponential",
                    "scheme": "Oranges",
                    "steps": 64
                },
                "exemplars": {"color": "rgba(255,0,255,0.7)"},
                "filterValues": {"le": 1e-9},
                "legend": {"show": False},
                "rowsFrame": {"layout": "auto"},
                "tooltip": {"show": True, "yHistogram": False},
                "yAxis": {"axisPlacement": "left", "reverse": False}
            }
        }
    
    @staticmethod
    def create_alert_summary_panel(grid_pos: GridPos) -> Dict:
        """Active alerts summary panel"""
        return {
            "id": 12,
            "title": "Active Alerts",
            "type": PanelType.TABLE.value,
            "gridPos": asdict(grid_pos),
            "targets": [
                Target(
                    expr='ALERTS{alertstate="firing"}',
                    legendFormat="Active Alerts",
                    refId="A",
                    instant=True
                ).to_dict()
            ],
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "custom": {
                        "align": "auto",
                        "displayMode": "color-background",
                        "inspect": False
                    },
                    "mappings": [
                        {
                            "options": {
                                "critical": {"color": "red", "index": 0},
                                "warning": {"color": "yellow", "index": 1},
                                "info": {"color": "blue", "index": 2}
                            },
                            "type": "value"
                        }
                    ],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 1},
                            {"color": "red", "value": 5}
                        ]
                    }
                }
            },
            "options": {
                "showHeader": True,
                "sortBy": [{"desc": True, "displayName": "Severity"}]
            },
            "transformations": [
                {
                    "id": "organize",
                    "options": {
                        "excludeByName": {"Time": True, "__name__": True},
                        "indexByName": {},
                        "renameByName": {
                            "alertname": "Alert",
                            "severity": "Severity",
                            "summary": "Summary",
                            "instance": "Instance"
                        }
                    }
                }
            ]
        }

class DashboardBuilder:
    """Builder class for creating complete dashboards"""
    
    def __init__(self, title: str, uid: str):
        self.dashboard = {
            "id": None,
            "uid": uid,
            "title": title,
            "tags": ["llm-platform", "monitoring"],
            "timezone": "browser",
            "panels": [],
            "time": {
                "from": "now-1h",
                "to": "now"
            },
            "timepicker": {},
            "refresh": "30s",
            "version": 1,
            "editable": True,
            "gnetId": None,
            "graphTooltip": 0,
            "links": [],
            "templating": {"list": []},
            "annotations": {"list": []},
            "schemaVersion": 27
        }
        self.panel_id_counter = 1
    
    def add_panel(self, panel: Dict) -> 'DashboardBuilder':
        """Add a panel to the dashboard"""
        panel["id"] = self.panel_id_counter
        self.panel_id_counter += 1
        self.dashboard["panels"].append(panel)
        return self
    
    def add_template_variable(self, name: str, query: str, label: str = None) -> 'DashboardBuilder':
        """Add a template variable"""
        variable = {
            "name": name,
            "type": "query",
            "label": label or name.title(),
            "query": query,
            "refresh": 1,
            "includeAll": True,
            "allValue": ".*",
            "multi": True,
            "datasource": {"type": "prometheus", "uid": "prometheus"}
        }
        self.dashboard["templating"]["list"].append(variable)
        return self
    
    def set_time_range(self, from_time: str, to_time: str = "now") -> 'DashboardBuilder':
        """Set dashboard time range"""
        self.dashboard["time"]["from"] = from_time
        self.dashboard["time"]["to"] = to_time
        return self
    
    def set_refresh_interval(self, interval: str) -> 'DashboardBuilder':
        """Set auto-refresh interval"""
        self.dashboard["refresh"] = interval
        return self
    
    def build(self) -> Dict:
        """Build and return the dashboard"""
        return self.dashboard

def create_llm_performance_dashboard() -> Dict:
    """Create the main LLM performance dashboard"""
    builder = DashboardBuilder("LLM Platform Performance", "llm-performance")
    
    # Add template variables
    builder.add_template_variable("model", 'label_values(llm_requests_total, model)', "Model")
    builder.add_template_variable("instance", 'label_values(up, instance)', "Instance")
    
    # Row 1: Key metrics
    builder.add_panel(CustomWidgets.create_request_rate_panel(GridPos(4, 6, 0, 0)))
    builder.add_panel(CustomWidgets.create_error_rate_panel(GridPos(4, 6, 6, 0)))
    builder.add_panel(CustomWidgets.create_api_latency_panel(GridPos(4, 12, 12, 0)))
    
    # Row 2: Model and GPU metrics
    builder.add_panel(CustomWidgets.create_model_usage_panel(GridPos(8, 6, 0, 4)))
    builder.add_panel(CustomWidgets.create_gpu_metrics_panel(GridPos(8, 18, 6, 4)))
    
    # Row 3: Token metrics and system resources
    builder.add_panel(CustomWidgets.create_token_metrics_panel(GridPos(8, 12, 0, 12)))
    builder.add_panel(CustomWidgets.create_system_resources_panel(GridPos(8, 12, 12, 12)))
    
    # Row 4: Database and cache performance
    builder.add_panel(CustomWidgets.create_database_performance_panel(GridPos(8, 12, 0, 20)))
    builder.add_panel(CustomWidgets.create_cache_performance_panel(GridPos(8, 12, 12, 20)))
    
    return builder.build()

def create_business_dashboard() -> Dict:
    """Create business metrics dashboard"""
    builder = DashboardBuilder("LLM Platform Business Metrics", "llm-business")
    
    # Add template variables
    builder.add_template_variable("user_tier", 'label_values(llm_requests_total, user_tier)', "User Tier")
    
    # Row 1: Cost and usage
    builder.add_panel(CustomWidgets.create_cost_analysis_panel(GridPos(8, 12, 0, 0)))
    builder.add_panel(CustomWidgets.create_user_activity_heatmap(GridPos(8, 12, 12, 0)))
    
    # Row 2: Alerts and monitoring
    builder.add_panel(CustomWidgets.create_alert_summary_panel(GridPos(8, 24, 0, 8)))
    
    return builder.build()

def export_dashboard_json(dashboard: Dict, filename: str) -> None:
    """Export dashboard to JSON file"""
    with open(filename, 'w') as f:
        json.dump(dashboard, f, indent=2)

if __name__ == "__main__":
    # Create and export dashboards
    performance_dashboard = create_llm_performance_dashboard()
    business_dashboard = create_business_dashboard()
    
    export_dashboard_json(performance_dashboard, "llm-performance.json")
    export_dashboard_json(business_dashboard, "llm-business.json")
    
    print("Dashboard JSON files created successfully!")
    print("- llm-performance.json: Main performance monitoring dashboard")
    print("- llm-business.json: Business metrics and cost analysis dashboard")