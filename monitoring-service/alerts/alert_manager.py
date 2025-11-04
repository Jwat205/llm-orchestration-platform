import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import redis
import uuid
from enum import Enum

class AlertSeverity(Enum):
    """Alert severity levels - like fire alarm vs smoke detector"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"  # Wake up the CEO level

class AlertStatus(Enum):
    """Alert lifecycle states"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

class AlertManager:
    """
    Alert Manager - like a smart security system for your platform.
    
    Think of this as your platform's nervous system that:
    - Detects problems before they affect users
    - Routes alerts to the right people
    - Prevents alert fatigue with smart filtering
    - Escalates critical issues automatically
    
    Essential for maintaining your 99.9% uptime target.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Alert rules configuration
        self.alert_rules = self._initialize_alert_rules()
        
        # Alert routing configuration
        self.routing_rules = self._initialize_routing_rules()
        
        # Suppression rules to prevent alert storms
        self.suppression_rules = self._initialize_suppression_rules()
    
    def _initialize_alert_rules(self) -> Dict[str, Dict]:
        """
        Initialize alert rules - like setting up your smoke detectors.
        These rules define when to trigger alerts based on metrics.
        """
        return {
            # Performance alerts - critical for your <100ms SLA
            'high_response_time': {
                'condition': lambda metrics: metrics.get('avg_response_time_ms', 0) > 500,
                'severity': AlertSeverity.CRITICAL,
                'message_template': 'High response time detected: {avg_response_time_ms:.1f}ms (threshold: 500ms)',
                'cooldown_minutes': 5,
                'escalation_minutes': 15,
                'category': 'performance'
            },
            'sla_violation': {
                'condition': lambda metrics: metrics.get('avg_response_time_ms', 0) > 100,
                'severity': AlertSeverity.WARNING,
                'message_template': 'SLA violation: {avg_response_time_ms:.1f}ms (target: <100ms)',
                'cooldown_minutes': 2,
                'escalation_minutes': 10,
                'category': 'performance'
            },
            'high_error_rate': {
                'condition': lambda metrics: metrics.get('error_rate_percent', 0) > 5,
                'severity': AlertSeverity.CRITICAL,
                'message_template': 'High error rate: {error_rate_percent:.1f}% (threshold: 5%)',
                'cooldown_minutes': 3,
                'escalation_minutes': 10,
                'category': 'reliability'
            },
            
            # System resource alerts
            'high_cpu_usage': {
                'condition': lambda metrics: metrics.get('cpu_percent', 0) > 90,
                'severity': AlertSeverity.CRITICAL,
                'message_template': 'Critical CPU usage: {cpu_percent:.1f}% (threshold: 90%)',
                'cooldown_minutes': 5,
                'escalation_minutes': 20,
                'category': 'resources'
            },
            'high_memory_usage': {
                'condition': lambda metrics: metrics.get('memory_percent', 0) > 95,
                'severity': AlertSeverity.CRITICAL,
                'message_template': 'Critical memory usage: {memory_percent:.1f}% (threshold: 95%)',
                'cooldown_minutes': 5,
                'escalation_minutes': 15,
                'category': 'resources'
            },
            'disk_space_critical': {
                'condition': lambda metrics: metrics.get('disk_percent', 0) > 95,
                'severity': AlertSeverity.CRITICAL,
                'message_template': 'Critical disk usage: {disk_percent:.1f}% (threshold: 95%)',
                'cooldown_minutes': 10,
                'escalation_minutes': 30,
                'category': 'resources'
            },
            
            # Service health alerts
            'service_unavailable': {
                'condition': lambda metrics: metrics.get('service_availability_percent', 100) < 100,
                'severity': AlertSeverity.CRITICAL,
                'message_template': 'Service unavailable: {service_availability_percent:.1f}% healthy',
                'cooldown_minutes': 1,
                'escalation_minutes': 5,
                'category': 'availability'
            },
            'cache_performance_degraded': {
                'condition': lambda metrics: metrics.get('cache_hit_rate_percent', 100) < 70,
                'severity': AlertSeverity.WARNING,
                'message_template': 'Poor cache performance: {cache_hit_rate_percent:.1f}% hit rate (target: >70%)',
                'cooldown_minutes': 10,
                'escalation_minutes': 30,
                'category': 'performance'
            },
            
            # Business metrics alerts
            'request_volume_spike': {
                'condition': lambda metrics: metrics.get('requests_per_second', 0) > 2000,  # 2x your normal 1000 RPS
                'severity': AlertSeverity.WARNING,
                'message_template': 'Request volume spike: {requests_per_second} RPS (normal: ~1000 RPS)',
                'cooldown_minutes': 5,
                'escalation_minutes': 20,
                'category': 'capacity'
            },
            'request_volume_drop': {
                'condition': lambda metrics: metrics.get('requests_per_second', 1000) < 100,  # Significant drop
                'severity': AlertSeverity.WARNING,
                'message_template': 'Request volume drop: {requests_per_second} RPS (expected: ~1000 RPS)',
                'cooldown_minutes': 5,
                'escalation_minutes': 15,
                'category': 'business'
            }
        }
    
    def _initialize_routing_rules(self) -> Dict[str, Dict]:
        """
        Initialize alert routing - like an emergency contact list.
        Determines who gets notified for different types of alerts.
        """
        return {
            'performance': {
                'primary': ['devops-team', 'backend-team'],
                'escalation': ['engineering-manager', 'cto'],
                'channels': ['slack', 'email', 'pagerduty']
            },
            'reliability': {
                'primary': ['sre-team', 'devops-team'],
                'escalation': ['engineering-manager', 'vp-engineering'],
                'channels': ['slack', 'email', 'pagerduty']
            },
            'resources': {
                'primary': ['devops-team', 'infrastructure-team'],
                'escalation': ['infrastructure-manager'],
                'channels': ['slack', 'email']
            },
            'availability': {
                'primary': ['sre-team', 'devops-team', 'backend-team'],
                'escalation': ['engineering-manager', 'cto'],
                'channels': ['slack', 'email', 'pagerduty', 'sms']
            },
            'capacity': {
                'primary': ['devops-team', 'product-team'],
                'escalation': ['engineering-manager'],
                'channels': ['slack', 'email']
            },
            'business': {
                'primary': ['product-team', 'business-ops'],
                'escalation': ['product-manager', 'coo'],
                'channels': ['slack', 'email']
            }
        }
    
    def _initialize_suppression_rules(self) -> Dict[str, Dict]:
        """
        Initialize suppression rules - like smart spam filters for alerts.
        Prevents alert storms that could overwhelm your team.
        """
        return {
            'similar_alerts': {
                'window_minutes': 10,
                'max_count': 3,
                'grouping_fields': ['rule_name', 'severity', 'category']
            },
            'maintenance_window': {
                'suppress_categories': ['resources', 'performance'],
                'max_duration_hours': 4
            },
            'known_issues': {
                'auto_suppress_duration_minutes': 60,
                'require_manual_resolution': True
            }
        }
    
    async def check_alert_conditions(self) -> List[Dict[str, Any]]:
        """
        Check all alert conditions against current metrics.
        Like a security guard doing rounds to check everything is okay.
        """
        triggered_alerts = []
        
        try:
            # Get current metrics from collector
            current_metrics = await self._get_current_metrics()
            
            if not current_metrics:
                self.logger.warning("No current metrics available for alert checking")
                return triggered_alerts
            
            # Check each alert rule
            for rule_name, rule_config in self.alert_rules.items():
                try:
                    # Evaluate rule condition
                    condition_met = rule_config['condition'](current_metrics)
                    
                    if condition_met:
                        # Check if this alert should be suppressed
                        if await self._should_suppress_alert(rule_name, rule_config, current_metrics):
                            self.logger.debug(f"Alert {rule_name} suppressed")
                            continue
                        
                        # Check cooldown period
                        if await self._is_in_cooldown(rule_name):
                            self.logger.debug(f"Alert {rule_name} in cooldown period")
                            continue
                        
                        # Create alert
                        alert = await self._create_alert(rule_name, rule_config, current_metrics)
                        triggered_alerts.append(alert)
                        
                        # Store alert
                        await self._store_alert(alert)
                        
                        # Set cooldown
                        await self._set_cooldown(rule_name, rule_config['cooldown_minutes'])
                        
                        self.logger.info(f"Alert triggered: {rule_name} - {alert['message']}")
                
                except Exception as e:
                    self.logger.error(f"Error checking alert rule {rule_name}: {e}")
            
            return triggered_alerts
            
        except Exception as e:
            self.logger.error(f"Error checking alert conditions: {e}")
            return []

    async def _get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current system metrics from Redis.
        Like checking all your dashboard gauges at once.
        """
        try:
            metrics = {}
            
            # Get latest performance metrics
            today = datetime.utcnow().strftime('%Y%m%d')
            perf_key = f"performance:current:{today}"
            perf_data = self.redis_client.get(perf_key)
            
            if perf_data:
                try:
                    perf_info = json.loads(perf_data)
                    metrics.update(perf_info)
                except json.JSONDecodeError:
                    pass
            
            # Get system health metrics
            health_key = "health:current"
            health_data = self.redis_client.get(health_key)
            
            if health_data:
                try:
                    health_info = json.loads(health_data)
                    metrics.update(health_info)
                except json.JSONDecodeError:
                    pass
            
            # Get resource usage
            resource_key = "resource:current"
            resource_data = self.redis_client.get(resource_key)
            
            if resource_data:
                try:
                    resource_info = json.loads(resource_data)
                    metrics.update(resource_info)
                except json.JSONDecodeError:
                    pass
            
            # Add simulated metrics if no real data
            if not metrics:
                metrics = await self._simulate_current_metrics()
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error getting current metrics: {e}")
            return {}

    async def _simulate_current_metrics(self) -> Dict[str, Any]:
        """Simulate realistic current metrics for testing"""
        import random
        
        return {
            'avg_response_time_ms': random.uniform(50, 200),
            'error_rate_percent': random.uniform(0.1, 8.0),
            'cpu_percent': random.uniform(20, 95),
            'memory_percent': random.uniform(30, 98),
            'disk_percent': random.uniform(40, 85),
            'requests_per_second': random.randint(800, 1200),
            'service_availability_percent': random.uniform(98.5, 100),
            'cache_hit_rate_percent': random.uniform(65, 95)
        }

    async def _should_suppress_alert(self, rule_name: str, rule_config: Dict, metrics: Dict) -> bool:
        """Check if alert should be suppressed based on suppression rules"""
        try:
            # Check similar alerts in suppression window
            suppression_config = self.suppression_rules['similar_alerts']
            window_minutes = suppression_config['window_minutes']
            max_count = suppression_config['max_count']
            
            # Get recent alerts
            recent_alerts_key = f"alerts:recent:{rule_name}"
            recent_count = self.redis_client.zcount(
                recent_alerts_key,
                int(time.time()) - (window_minutes * 60),
                int(time.time())
            )
            
            return recent_count >= max_count
            
        except Exception as e:
            self.logger.error(f"Error checking suppression: {e}")
            return False

    async def _is_in_cooldown(self, rule_name: str) -> bool:
        """Check if rule is in cooldown period"""
        try:
            cooldown_key = f"cooldown:{rule_name}"
            remaining = self.redis_client.ttl(cooldown_key)
            return remaining > 0
            
        except Exception as e:
            self.logger.error(f"Error checking cooldown: {e}")
            return False

    async def _create_alert(self, rule_name: str, rule_config: Dict, metrics: Dict) -> Dict[str, Any]:
        """Create a new alert based on rule and metrics"""
        try:
            alert_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            alert = {
                'id': alert_id,
                'rule_name': rule_name,
                'severity': rule_config['severity'].value,
                'category': rule_config['category'],
                'message': rule_config['message_template'].format(**metrics),
                'timestamp': timestamp,
                'status': AlertStatus.ACTIVE.value,
                'metrics': metrics,
                'tags': [rule_config['category'], rule_config['severity'].value],
                'acknowledged': False,
                'resolved': False,
                'escalation_level': 0
            }
            
            return alert
            
        except Exception as e:
            self.logger.error(f"Error creating alert: {e}")
            return {}

    async def _store_alert(self, alert: Dict[str, Any]):
        """Store alert in Redis for persistence and routing"""
        try:
            # Store alert details
            alert_key = f"alert:{alert['id']}"
            self.redis_client.setex(alert_key, 86400, json.dumps(alert))  # 24h TTL
            
            # Add to active alerts set
            active_key = "alerts:active"
            self.redis_client.sadd(active_key, alert['id'])
            
            # Add to category index
            category_key = f"alerts:category:{alert['category']}"
            self.redis_client.sadd(category_key, alert['id'])
            
            # Add to severity index
            severity_key = f"alerts:severity:{alert['severity']}"
            self.redis_client.sadd(severity_key, alert['id'])
            
            # Add to recent alerts for suppression
            recent_key = f"alerts:recent:{alert['rule_name']}"
            self.redis_client.zadd(recent_key, {alert['id']: int(time.time())})
            self.redis_client.expire(recent_key, 3600)  # 1h TTL
            
            # Route alert to appropriate teams
            await self._route_alert(alert)
            
        except Exception as e:
            self.logger.error(f"Error storing alert: {e}")

    async def _route_alert(self, alert: Dict[str, Any]):
        """Route alert to appropriate teams and channels"""
        try:
            category = alert['category']
            
            if category not in self.routing_rules:
                self.logger.warning(f"No routing rules for category: {category}")
                return
            
            routing_config = self.routing_rules[category]
            
            # Store alert for each team
            for team in routing_config['primary']:
                team_key = f"alerts:team:{team}"
                self.redis_client.sadd(team_key, alert['id'])
            
            # Store for escalation
            escalation_key = f"alerts:escalation:{category}"
            escalation_data = {
                'alert_id': alert['id'],
                'escalation_time': int(time.time()) + (self.alert_rules.get(alert['rule_name'], {}).get('escalation_minutes', 15) * 60),
                'level': 1
            }
            self.redis_client.zadd(escalation_key, {json.dumps(escalation_data): escalation_data['escalation_time']})
            
        except Exception as e:
            self.logger.error(f"Error routing alert: {e}")

    async def _set_cooldown(self, rule_name: str, cooldown_minutes: int):
        """Set cooldown period for alert rule"""
        try:
            cooldown_key = f"cooldown:{rule_name}"
            self.redis_client.setex(cooldown_key, cooldown_minutes * 60, "1")
        except Exception as e:
            self.logger.error(f"Error setting cooldown: {e}")

    async def acknowledge_alert(self, alert_id: str, user: str, notes: str = "") -> bool:
        """
        Acknowledge an alert - like signing off on a work order.
        Returns True if successful, False if alert not found.
        """
        try:
            alert_key = f"alert:{alert_id}"
            alert_data = self.redis_client.get(alert_key)
            
            if not alert_data:
                return False
            
            alert = json.loads(alert_data)
            alert['status'] = AlertStatus.ACKNOWLEDGED.value
            alert['acknowledged_by'] = user
            alert['acknowledged_at'] = datetime.utcnow().isoformat()
            alert['acknowledgment_notes'] = notes
            
            self.redis_client.setex(alert_key, 86400, json.dumps(alert))
            
            # Remove from active alerts
            self.redis_client.srem("alerts:active", alert_id)
            
            self.logger.info(f"Alert {alert_id} acknowledged by {user}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error acknowledging alert {alert_id}: {e}")
            return False

    async def resolve_alert(self, alert_id: str, user: str, resolution: str = "") -> bool:
        """
        Resolve an alert - like closing a support ticket.
        Returns True if successful, False if alert not found.
        """
        try:
            alert_key = f"alert:{alert_id}"
            alert_data = self.redis_client.get(alert_key)
            
            if not alert_data:
                return False
            
            alert = json.loads(alert_data)
            alert['status'] = AlertStatus.RESOLVED.value
            alert['resolved_by'] = user
            alert['resolved_at'] = datetime.utcnow().isoformat()
            alert['resolution'] = resolution
            
            self.redis_client.setex(alert_key, 86400, json.dumps(alert))
            
            # Remove from all active indices
            self.redis_client.srem("alerts:active", alert_id)
            self.redis_client.srem(f"alerts:category:{alert['category']}", alert_id)
            self.redis_client.srem(f"alerts:severity:{alert['severity']}", alert_id)
            
            # Remove from team queues
            for team, routing_config in self.routing_rules.items():
                if team in routing_config.get('primary', []) or team in routing_config.get('escalation', []):
                    self.redis_client.srem(f"alerts:team:{team}", alert_id)
            
            self.logger.info(f"Alert {alert_id} resolved by {user}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resolving alert {alert_id}: {e}")
            return False

    async def get_active_alerts(self, category: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all active alerts, optionally filtered by category or severity.
        Like checking your security system's active alarms.
        """
        try:
            alert_ids = set()
            
            if category:
                category_key = f"alerts:category:{category}"
                alert_ids.update(self.redis_client.smembers(category_key))
            elif severity:
                severity_key = f"alerts:severity:{severity}"
                alert_ids.update(self.redis_client.smembers(severity_key))
            else:
                alert_ids.update(self.redis_client.smembers("alerts:active"))
            
            alerts = []
            for alert_id in alert_ids:
                alert_key = f"alert:{alert_id}"
                alert_data = self.redis_client.get(alert_key)
                
                if alert_data:
                    try:
                        alert = json.loads(alert_data)
                        if alert['status'] == AlertStatus.ACTIVE.value:
                            alerts.append(alert)
                    except json.JSONDecodeError:
                        continue
            
            # Sort by severity and timestamp
            severity_order = {
                AlertSeverity.EMERGENCY.value: 0,
                AlertSeverity.CRITICAL.value: 1,
                AlertSeverity.WARNING.value: 2,
                AlertSeverity.INFO.value: 3
            }
            
            alerts.sort(key=lambda x: (severity_order.get(x['severity'], 4), x['timestamp']))
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting active alerts: {e}")
            return []

    async def run_escalation_check(self):
        """
        Check for alerts that need escalation - like an automated escalation manager.
        Should be called periodically (e.g., every minute).
        """
        try:
            current_time = int(time.time())
            
            for category, routing_config in self.routing_rules.items():
                escalation_key = f"alerts:escalation:{category}"
                
                # Get alerts ready for escalation
                escalatable = self.redis_client.zrangebyscore(
                    escalation_key, 
                    0, 
                    current_time
                )
                
                for escalation_str in escalatable:
                    try:
                        escalation_data = json.loads(escalation_str)
                        alert_id = escalation_data['alert_id']
                        
                        # Get alert details
                        alert_key = f"alert:{alert_id}"
                        alert_data = self.redis_client.get(alert_key)
                        
                        if alert_data:
                            alert = json.loads(alert_data)
                            
                            if alert['status'] == AlertStatus.ACTIVE.value:
                                # Escalate to next level
                                await self._escalate_alert(alert, escalation_data['level'], routing_config)
                                
                                # Update escalation level and reschedule
                                escalation_data['level'] += 1
                                escalation_data['escalation_time'] = current_time + (15 * 60)  # 15 min escalation
                                
                                # Remove old escalation and add new one
                                self.redis_client.zrem(escalation_key, escalation_str)
                                self.redis_client.zadd(escalation_key, {json.dumps(escalation_data): escalation_data['escalation_time']})
                                
                    except Exception as e:
                        self.logger.error(f"Error in escalation for {category}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error running escalation check: {e}")

    async def _escalate_alert(self, alert: Dict[str, Any], level: int, routing_config: Dict):
        """Escalate alert to next level team"""
        try:
            escalation_teams = routing_config.get('escalation', [])
            
            if level <= len(escalation_teams):
                team = escalation_teams[level - 1]
                
                # Add to escalation team's queue
                team_key = f"alerts:team:{team}"
                self.redis_client.sadd(team_key, alert['id'])
                
                # Log escalation
                self.logger.warning(f"Alert {alert['id']} escalated to {team} (level {level})")
                
                # Could send escalation notifications here
                await self._send_escalation_notification(alert, team, level)
                
        except Exception as e:
            self.logger.error(f"Error escalating alert: {e}")

    async def _send_escalation_notification(self, alert: Dict[str, Any], team: str, level: int):
        """Send escalation notification (placeholder for actual implementation)"""
        self.logger.info(f"ESCALATION: Alert {alert['id']} escalated to {team} team (level {level})")