"""
Alert Rules Management for LLM API Platform
Manages alert rules, thresholds, and notification channels for comprehensive monitoring.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import aiohttp
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertStatus(Enum):
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    SILENCED = "silenced"


@dataclass
class AlertRule:
    """Defines an alert rule with conditions and thresholds"""
    id: str
    name: str
    description: str
    severity: AlertSeverity
    metric_name: str
    condition: str  # e.g., ">", "<", "==", "!=", "contains"
    threshold: float
    duration: int  # seconds the condition must be true
    labels: Dict[str, str]
    annotations: Dict[str, str]
    enabled: bool = True


@dataclass
class Alert:
    """Represents an active or resolved alert"""
    id: str
    rule_id: str
    name: str
    severity: AlertSeverity
    status: AlertStatus
    started_at: datetime
    resolved_at: Optional[datetime] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    labels: Optional[Dict[str, str]] = None
    annotations: Optional[Dict[str, str]] = None
    notification_sent: bool = False


class AlertRuleEngine:
    """Core alert rule evaluation engine"""

    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.rule_states: Dict[str, Dict] = defaultdict(dict)
        self.notification_handlers = []
        self.running = False

    def add_rule(self, rule: AlertRule):
        """Add or update an alert rule"""
        self.rules[rule.id] = rule
        logger.info(f"Added alert rule: {rule.name} ({rule.id})")

    def remove_rule(self, rule_id: str):
        """Remove an alert rule"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            # Resolve any active alerts for this rule
            alerts_to_resolve = [
                alert_id for alert_id, alert in self.active_alerts.items()
                if alert.rule_id == rule_id
            ]
            for alert_id in alerts_to_resolve:
                self.resolve_alert(alert_id, "Rule removed")
            logger.info(f"Removed alert rule: {rule_id}")

    def add_notification_handler(self, handler: Callable):
        """Add a notification handler function"""
        self.notification_handlers.append(handler)

    async def evaluate_rules(self, metrics: Dict[str, float]):
        """Evaluate all active rules against current metrics"""
        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            await self._evaluate_rule(rule, metrics)

    async def _evaluate_rule(self, rule: AlertRule, metrics: Dict[str, float]):
        """Evaluate a single rule"""
        metric_value = metrics.get(rule.metric_name)

        if metric_value is None:
            return

        # Check condition
        condition_met = self._check_condition(metric_value, rule.condition, rule.threshold)

        rule_state = self.rule_states[rule.id]
        current_time = datetime.now()

        if condition_met:
            if 'condition_start' not in rule_state:
                rule_state['condition_start'] = current_time
                rule_state['condition_value'] = metric_value

            # Check if condition has been met for required duration
            condition_duration = (current_time - rule_state['condition_start']).total_seconds()

            if condition_duration >= rule.duration:
                # Fire alert if not already active
                alert_id = f"{rule.id}_{int(rule_state['condition_start'].timestamp())}"

                if alert_id not in self.active_alerts:
                    alert = Alert(
                        id=alert_id,
                        rule_id=rule.id,
                        name=rule.name,
                        severity=rule.severity,
                        status=AlertStatus.FIRING,
                        started_at=rule_state['condition_start'],
                        current_value=metric_value,
                        threshold=rule.threshold,
                        labels=rule.labels.copy(),
                        annotations=rule.annotations.copy()
                    )

                    self.active_alerts[alert_id] = alert
                    self.alert_history.append(alert)

                    logger.warning(f"ALERT FIRED: {rule.name} - {metric_value} {rule.condition} {rule.threshold}")

                    # Send notifications
                    await self._send_notifications(alert)

                else:
                    # Update existing alert with current value
                    self.active_alerts[alert_id].current_value = metric_value

        else:
            # Condition not met, clear rule state
            if 'condition_start' in rule_state:
                del rule_state['condition_start']
                del rule_state['condition_value']

            # Resolve any active alerts for this rule
            alerts_to_resolve = [
                alert_id for alert_id, alert in self.active_alerts.items()
                if alert.rule_id == rule.id and alert.status == AlertStatus.FIRING
            ]

            for alert_id in alerts_to_resolve:
                self.resolve_alert(alert_id, "Condition no longer met")

    def _check_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Check if condition is met"""
        if condition == ">":
            return value > threshold
        elif condition == ">=":
            return value >= threshold
        elif condition == "<":
            return value < threshold
        elif condition == "<=":
            return value <= threshold
        elif condition == "==":
            return value == threshold
        elif condition == "!=":
            return value != threshold
        else:
            logger.warning(f"Unknown condition: {condition}")
            return False

    def resolve_alert(self, alert_id: str, reason: str = ""):
        """Mark an alert as resolved"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()

            logger.info(f"ALERT RESOLVED: {alert.name} - {reason}")

            # Move to history and remove from active
            self.alert_history.append(alert)
            del self.active_alerts[alert_id]

    async def _send_notifications(self, alert: Alert):
        """Send notifications for an alert"""
        for handler in self.notification_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Notification handler failed: {e}")

        alert.notification_sent = True

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self.active_alerts.values())

    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            alert for alert in self.alert_history
            if alert.started_at >= cutoff_time
        ]

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics"""
        active_alerts = self.get_active_alerts()
        recent_history = self.get_alert_history(24)

        return {
            'active_alerts': {
                'total': len(active_alerts),
                'critical': len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]),
                'warning': len([a for a in active_alerts if a.severity == AlertSeverity.WARNING]),
                'info': len([a for a in active_alerts if a.severity == AlertSeverity.INFO]),
            },
            'recent_alerts': {
                'last_24h': len(recent_history),
                'resolved_24h': len([a for a in recent_history if a.status == AlertStatus.RESOLVED]),
            },
            'rules': {
                'total': len(self.rules),
                'enabled': len([r for r in self.rules.values() if r.enabled]),
                'disabled': len([r for r in self.rules.values() if not r.enabled]),
            }
        }


class NotificationChannels:
    """Manages different notification channels"""

    @staticmethod
    async def email_handler(alert: Alert, smtp_config: Dict[str, Any]):
        """Send email notification"""
        try:
            msg = MimeMultipart()
            msg['From'] = smtp_config['from_email']
            msg['To'] = smtp_config['to_email']
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.name}"

            body = f"""
Alert: {alert.name}
Severity: {alert.severity.value.upper()}
Status: {alert.status.value}
Started: {alert.started_at}
Current Value: {alert.current_value}
Threshold: {alert.threshold}

Description: {alert.annotations.get('description', 'No description')}
Runbook: {alert.annotations.get('runbook_url', 'No runbook available')}

Labels: {alert.labels}
            """

            msg.attach(MimeText(body, 'plain'))

            # Send email
            server = smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port'])
            if smtp_config.get('use_tls'):
                server.starttls()
            if smtp_config.get('username'):
                server.login(smtp_config['username'], smtp_config['password'])

            server.send_message(msg)
            server.quit()

            logger.info(f"Email notification sent for alert: {alert.name}")

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

    @staticmethod
    async def slack_handler(alert: Alert, webhook_url: str):
        """Send Slack notification"""
        try:
            color = {
                AlertSeverity.CRITICAL: "danger",
                AlertSeverity.WARNING: "warning",
                AlertSeverity.INFO: "good"
            }.get(alert.severity, "warning")

            payload = {
                "text": f"Alert: {alert.name}",
                "attachments": [{
                    "color": color,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Status", "value": alert.status.value, "short": True},
                        {"title": "Current Value", "value": str(alert.current_value), "short": True},
                        {"title": "Threshold", "value": str(alert.threshold), "short": True},
                        {"title": "Started", "value": alert.started_at.strftime("%Y-%m-%d %H:%M:%S"), "short": False},
                    ]
                }]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent for alert: {alert.name}")
                    else:
                        logger.error(f"Slack notification failed with status {response.status}")

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    @staticmethod
    async def webhook_handler(alert: Alert, webhook_url: str, headers: Dict[str, str] = None):
        """Send generic webhook notification"""
        try:
            payload = {
                "alert": asdict(alert),
                "timestamp": datetime.now().isoformat()
            }

            # Convert datetime objects to strings for JSON serialization
            if alert.started_at:
                payload["alert"]["started_at"] = alert.started_at.isoformat()
            if alert.resolved_at:
                payload["alert"]["resolved_at"] = alert.resolved_at.isoformat()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers=headers or {'Content-Type': 'application/json'}
                ) as response:
                    if response.status in [200, 201, 202]:
                        logger.info(f"Webhook notification sent for alert: {alert.name}")
                    else:
                        logger.error(f"Webhook notification failed with status {response.status}")

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")


# Pre-defined alert rules for LLM API Platform
def get_default_alert_rules() -> List[AlertRule]:
    """Get default alert rules for the platform"""
    return [
        # Performance alerts
        AlertRule(
            id="high_response_time",
            name="High API Response Time",
            description="API response time is above acceptable threshold",
            severity=AlertSeverity.WARNING,
            metric_name="api_response_time_p95",
            condition=">",
            threshold=2000.0,  # 2 seconds
            duration=300,  # 5 minutes
            labels={"service": "api", "type": "performance"},
            annotations={
                "description": "API P95 response time is above 2 seconds",
                "runbook_url": "https://docs.company.com/runbooks/high-response-time"
            }
        ),

        AlertRule(
            id="very_high_response_time",
            name="Very High API Response Time",
            description="API response time is critically high",
            severity=AlertSeverity.CRITICAL,
            metric_name="api_response_time_p95",
            condition=">",
            threshold=5000.0,  # 5 seconds
            duration=60,  # 1 minute
            labels={"service": "api", "type": "performance"},
            annotations={
                "description": "API P95 response time is above 5 seconds - immediate attention required",
                "runbook_url": "https://docs.company.com/runbooks/critical-response-time"
            }
        ),

        # Error rate alerts
        AlertRule(
            id="high_error_rate",
            name="High Error Rate",
            description="API error rate is above acceptable threshold",
            severity=AlertSeverity.WARNING,
            metric_name="api_error_rate",
            condition=">",
            threshold=5.0,  # 5%
            duration=300,  # 5 minutes
            labels={"service": "api", "type": "reliability"},
            annotations={
                "description": "API error rate is above 5%",
                "runbook_url": "https://docs.company.com/runbooks/high-error-rate"
            }
        ),

        AlertRule(
            id="critical_error_rate",
            name="Critical Error Rate",
            description="API error rate is critically high",
            severity=AlertSeverity.CRITICAL,
            metric_name="api_error_rate",
            condition=">",
            threshold=15.0,  # 15%
            duration=60,  # 1 minute
            labels={"service": "api", "type": "reliability"},
            annotations={
                "description": "API error rate is above 15% - service degradation likely",
                "runbook_url": "https://docs.company.com/runbooks/critical-error-rate"
            }
        ),

        # Resource alerts
        AlertRule(
            id="high_cpu_usage",
            name="High CPU Usage",
            description="CPU usage is above threshold",
            severity=AlertSeverity.WARNING,
            metric_name="cpu_usage_percent",
            condition=">",
            threshold=80.0,
            duration=600,  # 10 minutes
            labels={"type": "resource"},
            annotations={
                "description": "CPU usage is above 80% for extended period",
                "runbook_url": "https://docs.company.com/runbooks/high-cpu"
            }
        ),

        AlertRule(
            id="high_memory_usage",
            name="High Memory Usage",
            description="Memory usage is above threshold",
            severity=AlertSeverity.WARNING,
            metric_name="memory_usage_percent",
            condition=">",
            threshold=85.0,
            duration=300,  # 5 minutes
            labels={"type": "resource"},
            annotations={
                "description": "Memory usage is above 85%",
                "runbook_url": "https://docs.company.com/runbooks/high-memory"
            }
        ),

        # Model-specific alerts
        AlertRule(
            id="slow_model_inference",
            name="Slow Model Inference",
            description="Model inference time is slower than expected",
            severity=AlertSeverity.WARNING,
            metric_name="model_inference_time_p95",
            condition=">",
            threshold=30000.0,  # 30 seconds
            duration=300,  # 5 minutes
            labels={"service": "llm", "type": "performance"},
            annotations={
                "description": "Model inference P95 time is above 30 seconds",
                "runbook_url": "https://docs.company.com/runbooks/slow-inference"
            }
        ),

        # Database alerts
        AlertRule(
            id="slow_database_queries",
            name="Slow Database Queries",
            description="Database query performance is degraded",
            severity=AlertSeverity.WARNING,
            metric_name="db_query_time_p95",
            condition=">",
            threshold=1000.0,  # 1 second
            duration=600,  # 10 minutes
            labels={"service": "database", "type": "performance"},
            annotations={
                "description": "Database P95 query time is above 1 second",
                "runbook_url": "https://docs.company.com/runbooks/slow-queries"
            }
        ),

        # Service availability
        AlertRule(
            id="service_down",
            name="Service Down",
            description="Service is not responding to health checks",
            severity=AlertSeverity.CRITICAL,
            metric_name="service_up",
            condition="==",
            threshold=0.0,
            duration=60,  # 1 minute
            labels={"type": "availability"},
            annotations={
                "description": "Service is not responding to health checks",
                "runbook_url": "https://docs.company.com/runbooks/service-down"
            }
        ),
    ]


# Global alert engine instance
alert_engine = AlertRuleEngine()

# Initialize with default rules
for rule in get_default_alert_rules():
    alert_engine.add_rule(rule)


# Export key components
__all__ = [
    'AlertRule',
    'Alert',
    'AlertRuleEngine',
    'NotificationChannels',
    'AlertSeverity',
    'AlertStatus',
    'alert_engine',
    'get_default_alert_rules'
]