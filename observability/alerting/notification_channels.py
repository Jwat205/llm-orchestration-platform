"""
Notification Channels for LLM API Platform
Advanced notification management with multiple channels, routing, and rate limiting.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import aiohttp
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from jinja2 import Template
import hashlib

from .alert_rules import Alert, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    PAGERDUTY = "pagerduty"
    TEAMS = "teams"


@dataclass
class NotificationChannel:
    """Defines a notification channel configuration"""
    id: str
    name: str
    type: ChannelType
    config: Dict[str, Any]
    enabled: bool = True
    rate_limit: Optional[int] = None  # Max notifications per hour
    filters: Optional[Dict[str, Any]] = None  # Alert filters


@dataclass
class NotificationAttempt:
    """Records a notification attempt"""
    channel_id: str
    alert_id: str
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    response_time: Optional[float] = None


class NotificationManager:
    """Manages notification channels and delivery"""

    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {}
        self.attempt_history: deque = deque(maxlen=10000)
        self.rate_limits: Dict[str, deque] = defaultdict(lambda: deque())
        self.template_cache: Dict[str, Template] = {}

    def add_channel(self, channel: NotificationChannel):
        """Add or update a notification channel"""
        self.channels[channel.id] = channel
        logger.info(f"Added notification channel: {channel.name} ({channel.type.value})")

    def remove_channel(self, channel_id: str):
        """Remove a notification channel"""
        if channel_id in self.channels:
            del self.channels[channel_id]
            if channel_id in self.rate_limits:
                del self.rate_limits[channel_id]
            logger.info(f"Removed notification channel: {channel_id}")

    async def send_notification(self, alert: Alert, channel_id: Optional[str] = None):
        """Send notification to specified channel or all matching channels"""
        if channel_id:
            # Send to specific channel
            if channel_id in self.channels:
                await self._send_to_channel(alert, self.channels[channel_id])
        else:
            # Send to all matching channels
            matching_channels = self._find_matching_channels(alert)
            tasks = [self._send_to_channel(alert, channel) for channel in matching_channels]
            await asyncio.gather(*tasks, return_exceptions=True)

    def _find_matching_channels(self, alert: Alert) -> List[NotificationChannel]:
        """Find channels that match alert criteria"""
        matching = []

        for channel in self.channels.values():
            if not channel.enabled:
                continue

            # Check filters
            if channel.filters:
                if not self._alert_matches_filters(alert, channel.filters):
                    continue

            # Check rate limits
            if channel.rate_limit and self._is_rate_limited(channel.id, channel.rate_limit):
                logger.warning(f"Channel {channel.name} rate limited, skipping notification")
                continue

            matching.append(channel)

        return matching

    def _alert_matches_filters(self, alert: Alert, filters: Dict[str, Any]) -> bool:
        """Check if alert matches channel filters"""
        # Severity filter
        if 'severity' in filters:
            allowed_severities = filters['severity']
            if isinstance(allowed_severities, str):
                allowed_severities = [allowed_severities]
            if alert.severity.value not in allowed_severities:
                return False

        # Labels filter
        if 'labels' in filters and alert.labels:
            for key, value in filters['labels'].items():
                if key not in alert.labels or alert.labels[key] != value:
                    return False

        # Status filter
        if 'status' in filters:
            allowed_statuses = filters['status']
            if isinstance(allowed_statuses, str):
                allowed_statuses = [allowed_statuses]
            if alert.status.value not in allowed_statuses:
                return False

        return True

    def _is_rate_limited(self, channel_id: str, rate_limit: int) -> bool:
        """Check if channel is rate limited"""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)

        # Clean old entries
        channel_attempts = self.rate_limits[channel_id]
        while channel_attempts and channel_attempts[0] < hour_ago:
            channel_attempts.popleft()

        # Check rate limit
        return len(channel_attempts) >= rate_limit

    async def _send_to_channel(self, alert: Alert, channel: NotificationChannel):
        """Send notification to a specific channel"""
        start_time = time.time()
        success = False
        error_message = None

        try:
            if channel.type == ChannelType.EMAIL:
                await self._send_email(alert, channel)
            elif channel.type == ChannelType.SLACK:
                await self._send_slack(alert, channel)
            elif channel.type == ChannelType.WEBHOOK:
                await self._send_webhook(alert, channel)
            elif channel.type == ChannelType.SMS:
                await self._send_sms(alert, channel)
            elif channel.type == ChannelType.PAGERDUTY:
                await self._send_pagerduty(alert, channel)
            elif channel.type == ChannelType.TEAMS:
                await self._send_teams(alert, channel)
            else:
                raise ValueError(f"Unsupported channel type: {channel.type}")

            success = True
            logger.info(f"Notification sent successfully: {channel.name} -> {alert.name}")

        except Exception as e:
            error_message = str(e)
            logger.error(f"Notification failed: {channel.name} -> {alert.name}: {error_message}")

        # Record attempt
        attempt = NotificationAttempt(
            channel_id=channel.id,
            alert_id=alert.id,
            timestamp=datetime.now(),
            success=success,
            error_message=error_message,
            response_time=time.time() - start_time
        )
        self.attempt_history.append(attempt)

        # Update rate limiting
        if channel.rate_limit:
            self.rate_limits[channel.id].append(datetime.now())

    async def _send_email(self, alert: Alert, channel: NotificationChannel):
        """Send email notification"""
        config = channel.config
        template_name = config.get('template', 'default_email')

        # Render template
        subject, body = self._render_email_template(alert, template_name, config)

        # Create message
        msg = MimeMultipart()
        msg['From'] = config['from_email']
        msg['To'] = config['to_email']
        msg['Subject'] = subject
        msg.attach(MimeText(body, 'html' if config.get('html', False) else 'plain'))

        # Send email
        server = smtplib.SMTP(config['smtp_server'], config.get('smtp_port', 587))

        if config.get('use_tls', True):
            server.starttls()

        if config.get('username'):
            server.login(config['username'], config['password'])

        server.send_message(msg)
        server.quit()

    async def _send_slack(self, alert: Alert, channel: NotificationChannel):
        """Send Slack notification"""
        config = channel.config
        webhook_url = config['webhook_url']

        # Build Slack message
        color = self._get_slack_color(alert.severity)

        payload = {
            "text": f"Alert: {alert.name}",
            "username": config.get('username', 'LLM API Monitor'),
            "icon_emoji": config.get('icon', ':warning:'),
            "channel": config.get('channel'),
            "attachments": [{
                "color": color,
                "title": alert.name,
                "title_link": config.get('dashboard_url'),
                "fields": [
                    {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                    {"title": "Status", "value": alert.status.value, "short": True},
                    {"title": "Started", "value": alert.started_at.strftime("%Y-%m-%d %H:%M:%S UTC"), "short": True},
                ]
            }]
        }

        # Add current value if available
        if alert.current_value is not None:
            payload["attachments"][0]["fields"].extend([
                {"title": "Current Value", "value": str(alert.current_value), "short": True},
                {"title": "Threshold", "value": str(alert.threshold), "short": True},
            ])

        # Add description
        if alert.annotations and 'description' in alert.annotations:
            payload["attachments"][0]["text"] = alert.annotations['description']

        # Add action buttons
        if config.get('add_actions', True):
            payload["attachments"][0]["actions"] = [
                {
                    "type": "button",
                    "text": "View Dashboard",
                    "url": config.get('dashboard_url', '#')
                },
                {
                    "type": "button",
                    "text": "Runbook",
                    "url": alert.annotations.get('runbook_url', '#')
                }
            ]

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload, timeout=30) as response:
                if response.status != 200:
                    raise Exception(f"Slack API returned {response.status}: {await response.text()}")

    async def _send_webhook(self, alert: Alert, channel: NotificationChannel):
        """Send webhook notification"""
        config = channel.config
        url = config['url']

        # Prepare payload
        payload = {
            "alert": {
                "id": alert.id,
                "name": alert.name,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "started_at": alert.started_at.isoformat(),
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "current_value": alert.current_value,
                "threshold": alert.threshold,
                "labels": alert.labels,
                "annotations": alert.annotations,
            },
            "channel": channel.name,
            "timestamp": datetime.now().isoformat()
        }

        # Add custom fields
        if 'custom_fields' in config:
            payload.update(config['custom_fields'])

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'LLM-API-Monitor/1.0'
        }

        # Add custom headers
        if 'headers' in config:
            headers.update(config['headers'])

        # Add authentication
        if 'auth_token' in config:
            headers['Authorization'] = f"Bearer {config['auth_token']}"
        elif 'api_key' in config:
            headers['X-API-Key'] = config['api_key']

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=config.get('timeout', 30)
            ) as response:
                if response.status not in [200, 201, 202]:
                    raise Exception(f"Webhook returned {response.status}: {await response.text()}")

    async def _send_sms(self, alert: Alert, channel: NotificationChannel):
        """Send SMS notification"""
        config = channel.config

        # This is a placeholder - implement with your SMS provider
        # Examples: Twilio, AWS SNS, etc.
        message = f"ALERT: {alert.name} - {alert.severity.value.upper()}"

        if config.get('provider') == 'twilio':
            # Twilio implementation
            pass
        elif config.get('provider') == 'aws_sns':
            # AWS SNS implementation
            pass
        else:
            raise NotImplementedError("SMS provider not implemented")

    async def _send_pagerduty(self, alert: Alert, channel: NotificationChannel):
        """Send PagerDuty notification"""
        config = channel.config

        # PagerDuty Events API v2
        url = "https://events.pagerduty.com/v2/enqueue"

        event_action = "trigger" if alert.status == AlertStatus.FIRING else "resolve"

        payload = {
            "routing_key": config['integration_key'],
            "event_action": event_action,
            "dedup_key": f"llm-api-{alert.rule_id}",
            "payload": {
                "summary": alert.name,
                "severity": self._get_pagerduty_severity(alert.severity),
                "source": "LLM API Monitor",
                "timestamp": alert.started_at.isoformat(),
                "custom_details": {
                    "current_value": alert.current_value,
                    "threshold": alert.threshold,
                    "labels": alert.labels,
                    "runbook_url": alert.annotations.get('runbook_url'),
                }
            }
        }

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'LLM-API-Monitor/1.0'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                if response.status not in [200, 202]:
                    raise Exception(f"PagerDuty returned {response.status}: {await response.text()}")

    async def _send_teams(self, alert: Alert, channel: NotificationChannel):
        """Send Microsoft Teams notification"""
        config = channel.config
        webhook_url = config['webhook_url']

        # Teams adaptive card
        color = self._get_teams_color(alert.severity)

        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"Alert: {alert.name}",
            "sections": [{
                "activityTitle": alert.name,
                "activitySubtitle": f"Severity: {alert.severity.value.upper()}",
                "activityImage": config.get('icon_url'),
                "facts": [
                    {"name": "Status", "value": alert.status.value},
                    {"name": "Started", "value": alert.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")},
                ]
            }]
        }

        # Add current value if available
        if alert.current_value is not None:
            payload["sections"][0]["facts"].extend([
                {"name": "Current Value", "value": str(alert.current_value)},
                {"name": "Threshold", "value": str(alert.threshold)},
            ])

        # Add description
        if alert.annotations and 'description' in alert.annotations:
            payload["sections"][0]["text"] = alert.annotations['description']

        # Add action buttons
        if config.get('add_actions', True):
            payload["potentialAction"] = [
                {
                    "@type": "OpenUri",
                    "name": "View Dashboard",
                    "targets": [{"os": "default", "uri": config.get('dashboard_url', '#')}]
                },
                {
                    "@type": "OpenUri",
                    "name": "Runbook",
                    "targets": [{"os": "default", "uri": alert.annotations.get('runbook_url', '#')}]
                }
            ]

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload, timeout=30) as response:
                if response.status != 200:
                    raise Exception(f"Teams API returned {response.status}: {await response.text()}")

    def _render_email_template(self, alert: Alert, template_name: str, config: Dict[str, Any]) -> tuple:
        """Render email template"""
        # Load template if not cached
        if template_name not in self.template_cache:
            template_content = self._get_email_template(template_name)
            self.template_cache[template_name] = Template(template_content)

        template = self.template_cache[template_name]

        # Prepare template context
        context = {
            'alert': alert,
            'severity_color': self._get_severity_color(alert.severity),
            'dashboard_url': config.get('dashboard_url'),
        }

        rendered = template.render(**context)

        # Split subject and body (assuming first line is subject)
        lines = rendered.split('\n', 1)
        subject = lines[0].strip()
        body = lines[1] if len(lines) > 1 else ""

        return subject, body

    def _get_email_template(self, template_name: str) -> str:
        """Get email template content"""
        # Default template
        if template_name == 'default_email':
            return """[{{ alert.severity.value.upper() }}] {{ alert.name }}
<html>
<body style="font-family: Arial, sans-serif;">
    <div style="border-left: 4px solid {{ severity_color }}; padding-left: 20px;">
        <h2 style="color: {{ severity_color }};">{{ alert.name }}</h2>

        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Severity:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{{ alert.severity.value.upper() }}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{{ alert.status.value }}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Started:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{{ alert.started_at.strftime('%Y-%m-%d %H:%M:%S UTC') }}</td>
            </tr>
            {% if alert.current_value %}
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Current Value:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{{ alert.current_value }}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Threshold:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{{ alert.threshold }}</td>
            </tr>
            {% endif %}
        </table>

        {% if alert.annotations and alert.annotations.description %}
        <div style="margin-top: 20px;">
            <h3>Description:</h3>
            <p>{{ alert.annotations.description }}</p>
        </div>
        {% endif %}

        {% if dashboard_url %}
        <div style="margin-top: 20px;">
            <a href="{{ dashboard_url }}" style="background-color: #007cba; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">View Dashboard</a>
        </div>
        {% endif %}
    </div>
</body>
</html>"""

        # Add more templates as needed
        return "Subject: Alert\nNo template found"

    def _get_slack_color(self, severity: AlertSeverity) -> str:
        """Get Slack color for severity"""
        return {
            AlertSeverity.CRITICAL: "danger",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.INFO: "good"
        }.get(severity, "warning")

    def _get_teams_color(self, severity: AlertSeverity) -> str:
        """Get Teams color for severity"""
        return {
            AlertSeverity.CRITICAL: "FF0000",
            AlertSeverity.WARNING: "FFA500",
            AlertSeverity.INFO: "00FF00"
        }.get(severity, "FFA500")

    def _get_severity_color(self, severity: AlertSeverity) -> str:
        """Get color for severity"""
        return {
            AlertSeverity.CRITICAL: "#FF0000",
            AlertSeverity.WARNING: "#FFA500",
            AlertSeverity.INFO: "#00AA00"
        }.get(severity, "#FFA500")

    def _get_pagerduty_severity(self, severity: AlertSeverity) -> str:
        """Get PagerDuty severity mapping"""
        return {
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.INFO: "info"
        }.get(severity, "warning")

    def get_channel_stats(self) -> Dict[str, Any]:
        """Get notification channel statistics"""
        recent_attempts = [
            a for a in self.attempt_history
            if a.timestamp > datetime.now() - timedelta(hours=24)
        ]

        stats = {
            'channels': {
                'total': len(self.channels),
                'enabled': len([c for c in self.channels.values() if c.enabled]),
                'by_type': defaultdict(int)
            },
            'recent_attempts': {
                'total': len(recent_attempts),
                'successful': len([a for a in recent_attempts if a.success]),
                'failed': len([a for a in recent_attempts if not a.success]),
                'by_channel': defaultdict(int)
            }
        }

        # Count by type
        for channel in self.channels.values():
            stats['channels']['by_type'][channel.type.value] += 1

        # Count by channel
        for attempt in recent_attempts:
            stats['recent_attempts']['by_channel'][attempt.channel_id] += 1

        return stats


# Global notification manager
notification_manager = NotificationManager()

# Export key components
__all__ = [
    'NotificationChannel',
    'NotificationManager',
    'ChannelType',
    'NotificationAttempt',
    'notification_manager'
]