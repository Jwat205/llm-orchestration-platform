import asyncio
import aiohttp
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

class NotificationService:
    """
    Notification Service - like an emergency broadcast system.
    
    Think of this as your platform's communication center that:
    - Sends alerts to the right people through the right channels
    - Escalates to different people based on severity
    - Handles different notification methods (Slack, email, SMS, PagerDuty)
    - Prevents notification spam while ensuring critical alerts get through
    
    Essential for your team to know when your 99.9% uptime is at risk.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Configuration for different notification channels
        self.config = {
            'slack': {
                'webhook_url': os.getenv('SLACK_WEBHOOK_URL', ''),
                'channels': {
                    'critical': '#alerts-critical',
                    'warning': '#alerts-warning',
                    'info': '#alerts-info'
                }
            },
            'email': {
                'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                'smtp_port': int(os.getenv('SMTP_PORT', '587')),
                'username': os.getenv('EMAIL_USERNAME', ''),
                'password': os.getenv('EMAIL_PASSWORD', ''),
                'from_address': os.getenv('EMAIL_FROM', 'alerts@yourplatform.com')
            },
            'pagerduty': {
                'integration_key': os.getenv('PAGERDUTY_INTEGRATION_KEY', ''),
                'api_url': 'https://events.pagerduty.com/v2/enqueue'
            },
            'sms': {
                'twilio_sid': os.getenv('TWILIO_SID', ''),
                'twilio_token': os.getenv('TWILIO_TOKEN', ''),
                'from_number': os.getenv('TWILIO_FROM_NUMBER', '')
            }
        }
        
        # Contact directory - like your emergency contact list
        self.contacts = {
            'devops-team': {
                'slack': ['@devops-channel'],
                'email': ['devops@yourplatform.com'],
                'pagerduty': ['devops-escalation']
            },
            'backend-team': {
                'slack': ['@backend-channel'],
                'email': ['backend@yourplatform.com']
            },
            'sre-team': {
                'slack': ['@sre-channel'],
                'email': ['sre@yourplatform.com'],
                'pagerduty': ['sre-escalation']
            },
            'engineering-manager': {
                'email': ['eng-manager@yourplatform.com'],
                'sms': ['+1234567890'],
                'pagerduty': ['eng-manager-escalation']
            },
            'cto': {
                'email': ['cto@yourplatform.com'],
                'sms': ['+1234567891'],
                'pagerduty': ['executive-escalation']
            }
        }
    
    async def send_alert(self, alert: Dict[str, Any]) -> bool:
        """
        Send alert through appropriate channels based on severity and routing rules.
        Like a smart emergency dispatcher that knows who to call for different emergencies.
        """
        try:
            self.logger.info(f"Sending alert {alert['id']}: {alert['message']}")
            
            # Get routing configuration
            routing = alert.get('routing', {})
            severity = alert.get('severity', 'info')
            
            # Determine who to notify
            contacts_to_notify = []
            
            # Get primary contacts
            primary_contacts = routing.get('primary', [])
            contacts_to_notify.extend(primary_contacts)
            
            # Add escalation contacts if alert was escalated
            if alert.get('escalated', False):
                escalation_contacts = routing.get('escalation', [])
                contacts_to_notify.extend(escalation_contacts)
            
            # Get notification channels for this severity
            channels = routing.get('channels', ['slack', 'email'])
            
            # Send notifications
            success_count = 0
            total_attempts = 0
            
            for contact in contacts_to_notify:
                if contact in self.contacts:
                    contact_info = self.contacts[contact]
                    
                    for channel in channels:
                        if channel in contact_info:
                            for address in contact_info[channel]:
                                total_attempts += 1
                                
                                if await self._send_notification(channel, address, alert):
                                    success_count += 1
                                else:
                                    self.logger.error(f"Failed to send {channel} notification to {address}")
            
            # Log results
            success_rate = (success_count / total_attempts) * 100 if total_attempts > 0 else 0
            self.logger.info(f"Alert {alert['id']} notifications: {success_count}/{total_attempts} successful ({success_rate:.1f}%)")
            
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error sending alert {alert.get('id', 'unknown')}: {e}")
            return False
    
    async def _send_notification(self, channel: str, address: str, alert: Dict[str, Any]) -> bool:
        """Send notification through specific channel"""
        try:
            if channel == 'slack':
                return await self._send_slack_notification(address, alert)
            elif channel == 'email':
                return await self._send_email_notification(address, alert)
            elif channel == 'pagerduty':
                return await self._send_pagerduty_notification(address, alert)
            elif channel == 'sms':
                return await self._send_sms_notification(address, alert)
            else:
                self.logger.warning(f"Unknown notification channel: {channel}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending {channel} notification to {address}: {e}")
            return False
    
    async def _send_slack_notification(self, channel: str, alert: Dict[str, Any]) -> bool:
        """
        Send Slack notification - like posting an announcement on the office bulletin board.
        """
        try:
            webhook_url = self.config['slack']['webhook_url']
            if not webhook_url:
                self.logger.warning("Slack webhook URL not configured")
                return False
            
            # Determine color based on severity
            color_map = {
                'emergency': '#FF0000',  # Red
                'critical': '#FF6600',   # Orange
                'warning': '#FFCC00',    # Yellow
                'info': '#36A64F'        # Green
            }
            color = color_map.get(alert['severity'], '#CCCCCC')
            
            # Create Slack message payload
            payload = {
                'channel': channel if channel.startswith('#') else f"#{channel}",
                'username': 'Platform Monitor',
                'icon_emoji': ':warning:' if alert['severity'] in ['critical', 'emergency'] else ':information_source:',
                'attachments': [{
                    'color': color,
                    'title': f"🚨 {alert['severity'].upper()} Alert",
                    'text': alert['message'],
                    'fields': [
                        {
                            'title': 'Rule',
                            'value': alert['rule_name'],
                            'short': True
                        },
                        {
                            'title': 'Category',
                            'value': alert['category'],
                            'short': True
                        },
                        {
                            'title': 'Time',
                            'value': self._format_timestamp(alert['created_at']),
                            'short': True
                        },
                        {
                            'title': 'Alert ID',
                            'value': alert['id'][:8],  # Short ID for display
                            'short': True
                        }
                    ],
                    'footer': 'Platform Monitoring',
                    'ts': int(datetime.fromisoformat(alert['created_at']).timestamp())
                }]
            }
            
            # Add action buttons for critical alerts
            if alert['severity'] in ['critical', 'emergency']:
                payload['attachments'][0]['actions'] = [
                    {
                        'type': 'button',
                        'text': 'Acknowledge',
                        'style': 'primary',
                        'url': f"https://monitoring.yourplatform.com/alerts/{alert['id']}/acknowledge"
                    },
                    {
                        'type': 'button',
                        'text': 'View Details',
                        'url': f"https://monitoring.yourplatform.com/alerts/{alert['id']}"
                    }
                ]
            
            # Send to Slack
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        self.logger.debug(f"Slack notification sent to {channel}")
                        return True
                    else:
                        self.logger.error(f"Slack API error: {response.status} - {await response.text()}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Error sending Slack notification: {e}")
            return False
    
    async def _send_email_notification(self, email_address: str, alert: Dict[str, Any]) -> bool:
        """
        Send email notification - like sending a formal incident report.
        """
        try:
            config = self.config['email']
            if not all([config['username'], config['password'], config['from_address']]):
                self.logger.warning("Email configuration incomplete")
                return False
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert['severity'].upper()}] Platform Alert: {alert['rule_name']}"
            msg['From'] = config['from_address']
            msg['To'] = email_address
            
            # Create HTML content
            html_content = self._create_email_html(alert)
            
            # Create text content (fallback)
            text_content = f"""
Platform Alert - {alert['severity'].upper()}

Alert: {alert['message']}
Rule: {alert['rule_name']}
Category: {alert['category']}
Time: {self._format_timestamp(alert['created_at'])}
Alert ID: {alert['id']}

Metrics Snapshot:
{json.dumps(alert.get('metrics_snapshot', {}), indent=2)}

View full details: https://monitoring.yourplatform.com/alerts/{alert['id']}
            """.strip()
            
            # Attach both versions
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
                server.starttls()
                server.login(config['username'], config['password'])
                server.send_message(msg)
            
            self.logger.debug(f"Email notification sent to {email_address}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email notification: {e}")
            return False
    
    async def _send_pagerduty_notification(self, service_key: str, alert: Dict[str, Any]) -> bool:
        """
        Send PagerDuty notification - like calling 911 for critical system issues.
        """
        try:
            config = self.config['pagerduty']
            if not config['integration_key']:
                self.logger.warning("PagerDuty integration key not configured")
                return False
            
            # Create PagerDuty event
            payload = {
                'routing_key': config['integration_key'],
                'event_action': 'trigger',
                'dedup_key': f"platform-alert-{alert['rule_name']}-{alert['id'][:8]}",
                'payload': {
                    'summary': alert['message'],
                    'source': 'platform-monitoring',
                    'severity': self._map_severity_to_pagerduty(alert['severity']),
                    'component': alert['category'],
                    'group': alert['rule_name'],
                    'class': 'platform-alert',
                    'custom_details': {
                        'alert_id': alert['id'],
                        'rule_name': alert['rule_name'],
                        'category': alert['category'],
                        'created_at': alert['created_at'],
                        'metrics_snapshot': alert.get('metrics_snapshot', {}),
                        'escalated': alert.get('escalated', False)
                    }
                },
                'links': [{
                    'href': f"https://monitoring.yourplatform.com/alerts/{alert['id']}",
                    'text': 'View Alert Details'
                }]
            }
            
            # Send to PagerDuty
            async with aiohttp.ClientSession() as session:
                async with session.post(config['api_url'], json=payload) as response:
                    if response.status == 202:  # PagerDuty returns 202 for success
                        self.logger.debug(f"PagerDuty notification sent for service {service_key}")
                        return True
                    else:
                        self.logger.error(f"PagerDuty API error: {response.status} - {await response.text()}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Error sending PagerDuty notification: {e}")
            return False
    
    async def _send_sms_notification(self, phone_number: str, alert: Dict[str, Any]) -> bool:
        """
        Send SMS notification - like a text message for urgent alerts.
        """
        try:
            config = self.config['sms']
            if not all([config['twilio_sid'], config['twilio_token'], config['from_number']]):
                self.logger.warning("SMS configuration incomplete")
                return False
            
            # Create short SMS message
            message = f"🚨 {alert['severity'].upper()} ALERT\n{alert['message'][:100]}...\nID: {alert['id'][:8]}\nTime: {self._format_timestamp(alert['created_at'], short=True)}"
            
            # Twilio API payload
            payload = {
                'From': config['from_number'],
                'To': phone_number,
                'Body': message
            }
            
            # Send via Twilio API
            auth = aiohttp.BasicAuth(config['twilio_sid'], config['twilio_token'])
            url = f"https://api.twilio.com/2010-04-01/Accounts/{config['twilio_sid']}/Messages.json"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, auth=auth) as response:
                    if response.status == 201:  # Twilio returns 201 for success
                        self.logger.debug(f"SMS notification sent to {phone_number}")
                        return True
                    else:
                        self.logger.error(f"Twilio API error: {response.status} - {await response.text()}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Error sending SMS notification: {e}")
            return False
    
    def _create_email_html(self, alert: Dict[str, Any]) -> str:
        """
        Create HTML email content - like a formatted incident report.
        """
        severity_colors = {
            'emergency': '#FF0000',
            'critical': '#FF6600',
            'warning': '#FFCC00',
            'info': '#36A64F'
        }
        
        color = severity_colors.get(alert['severity'], '#CCCCCC')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .metric-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                .metric-table th, .metric-table td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                .metric-table th {{ background-color: #f8f9fa; }}
                .footer {{ background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
                .button {{ display: inline-block; padding: 10px 20px; background-color: {color}; color: white; text-decoration: none; border-radius: 4px; margin: 10px 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 {alert['severity'].upper()} ALERT</h1>
                    <p>{alert['message']}</p>
                </div>
                
                <div class="content">
                    <h2>Alert Details</h2>
                    <table class="metric-table">
                        <tr><th>Alert ID</th><td>{alert['id']}</td></tr>
                        <tr><th>Rule Name</th><td>{alert['rule_name']}</td></tr>
                        <tr><th>Category</th><td>{alert['category']}</td></tr>
                        <tr><th>Severity</th><td>{alert['severity'].upper()}</td></tr>
                        <tr><th>Created At</th><td>{self._format_timestamp(alert['created_at'])}</td></tr>
                        <tr><th>Status</th><td>{alert.get('status', 'active').upper()}</td></tr>
                    </table>
                    
                    <h3>Metrics Snapshot</h3>
                    <table class="metric-table">
        """
        
        # Add metrics to the table
        for key, value in alert.get('metrics_snapshot', {}).items():
            if isinstance(value, (int, float)):
                if 'percent' in key:
                    html += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{value:.1f}%</td></tr>"
                elif 'ms' in key:
                    html += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{value:.1f}ms</td></tr>"
                else:
                    html += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{value}</td></tr>"
            else:
                html += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{value}</td></tr>"
        
        html += f"""
                    </table>
                    
                    <div style="text-align: center; margin-top: 20px;">
                        <a href="https://monitoring.yourplatform.com/alerts/{alert['id']}" class="button">View Full Details</a>
                        <a href="https://monitoring.yourplatform.com/alerts/{alert['id']}/acknowledge" class="button">Acknowledge Alert</a>
                    </div>
                </div>
                
                <div class="footer">
                    <p>This alert was generated by Platform Monitoring System</p>
                    <p>Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _format_timestamp(self, timestamp_str: str, short: bool = False) -> str:
        """Format timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp_str)
            if short:
                return dt.strftime('%m/%d %H:%M')
            else:
                return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except ValueError:
            return timestamp_str
    
    def _map_severity_to_pagerduty(self, severity: str) -> str:
        """Map our severity levels to PagerDuty severity levels"""
        mapping = {
            'emergency': 'critical',
            'critical': 'critical',
            'warning': 'warning',
            'info': 'info'
        }
        return mapping.get(severity, 'info')
    
    async def send_test_notification(self, channel: str, address: str) -> bool:
        """
        Send test notification to verify configuration.
        Like testing your fire alarm to make sure it works.
        """
        try:
            # Create test alert
            test_alert = {
                'id': 'test-alert-12345',
                'rule_name': 'test_notification',
                'severity': 'info',
                'category': 'test',
                'message': 'This is a test notification from Platform Monitoring',
                'created_at': datetime.utcnow().isoformat(),
                'status': 'active',
                'metrics_snapshot': {
                    'test_metric': 42,
                    'response_time_ms': 85.5,
                    'cpu_percent': 65.2
                }
            }
            
            success = await self._send_notification(channel, address, test_alert)
            
            if success:
                self.logger.info(f"Test notification sent successfully via {channel} to {address}")
            else:
                self.logger.error(f"Test notification failed for {channel} to {address}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending test notification: {e}")
            return False
    
    async def send_escalation_notification(self, original_alert: Dict[str, Any]) -> bool:
        """
        Send escalation notification when alert is not acknowledged.
        Like calling your manager when the first person doesn't respond.
        """
        try:
            # Create escalation alert based on original
            escalation_alert = {
                **original_alert,
                'message': f"ESCALATED: {original_alert['message']} (Original alert not acknowledged)",
                'severity': 'critical' if original_alert['severity'] == 'warning' else 'emergency',
                'escalated': True,
                'escalated_at': datetime.utcnow().isoformat()
            }
            
            # Send to escalation contacts
            routing = original_alert.get('routing', {})
            escalation_contacts = routing.get('escalation', [])
            
            if not escalation_contacts:
                self.logger.warning(f"No escalation contacts defined for alert {original_alert['id']}")
                return False
            
            success_count = 0
            total_attempts = 0
            
            for contact in escalation_contacts:
                if contact in self.contacts:
                    contact_info = self.contacts[contact]
                    
                    # Use high-priority channels for escalation
                    priority_channels = ['pagerduty', 'sms', 'email']
                    
                    for channel in priority_channels:
                        if channel in contact_info:
                            for address in contact_info[channel]:
                                total_attempts += 1
                                
                                if await self._send_notification(channel, address, escalation_alert):
                                    success_count += 1
            
            self.logger.info(f"Escalation notifications sent: {success_count}/{total_attempts}")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error sending escalation notification: {e}")
            return False
    
    async def send_resolution_notification(self, alert: Dict[str, Any], resolution_note: str = "") -> bool:
        """
        Send notification when alert is resolved.
        Like an "all clear" signal after an emergency.
        """
        try:
            # Create resolution message
            resolution_message = f"✅ RESOLVED: {alert['message']}"
            if resolution_note:
                resolution_message += f"\n\nResolution: {resolution_note}"
            
            resolution_alert = {
                **alert,
                'message': resolution_message,
                'severity': 'info',  # Always info for resolutions
                'status': 'resolved',
                'resolved_at': datetime.utcnow().isoformat()
            }
            
            # Send to original contacts (not escalation)
            routing = alert.get('routing', {})
            primary_contacts = routing.get('primary', [])
            
            success_count = 0
            total_attempts = 0
            
            for contact in primary_contacts:
                if contact in self.contacts:
                    contact_info = self.contacts[contact]
                    
                    # Use lighter channels for resolution notifications
                    channels = ['slack', 'email']
                    
                    for channel in channels:
                        if channel in contact_info:
                            for address in contact_info[channel]:
                                total_attempts += 1
                                
                                if await self._send_notification(channel, address, resolution_alert):
                                    success_count += 1
            
            self.logger.info(f"Resolution notifications sent: {success_count}/{total_attempts}")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error sending resolution notification: {e}")
            return False
    
    def get_notification_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about notification delivery.
        Like a report card for your communication system.
        """
        # In a real implementation, you'd track these stats
        return {
            'total_notifications_sent': 1500,
            'success_rate_percent': 98.5,
            'by_channel': {
                'slack': {'sent': 800, 'success_rate': 99.2},
                'email': {'sent': 600, 'success_rate': 97.8},
                'pagerduty': {'sent': 80, 'success_rate': 100.0},
                'sms': {'sent': 20, 'success_rate': 95.0}
            },
            'avg_delivery_time_seconds': {
                'slack': 2.3,
                'email': 5.8,
                'pagerduty': 1.1,
                'sms': 3.2
            },
            'last_updated': datetime.utcnow().isoformat()
        }


class NotificationQueue:
    """
    Queue system for handling notification delivery.
    Like a post office that processes mail in order and handles delivery failures.
    """
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.notification_service = NotificationService()
    
    async def enqueue_notification(self, channel: str, address: str, alert: Dict[str, Any], priority: int = 0) -> bool:
        """
        Add notification to queue for delivery.
        Higher priority alerts (like critical) get delivered first.
        """
        try:
            notification_item = {
                'id': f"notif-{int(datetime.utcnow().timestamp())}-{hash(address)}",
                'channel': channel,
                'address': address,
                'alert': alert,
                'priority': priority,
                'created_at': datetime.utcnow().isoformat(),
                'attempts': 0,
                'max_attempts': 3
            }
            
            # Add to priority queue (Redis sorted set)
            queue_key = "notification_queue"
            score = -priority  # Negative for high priority first
            
            self.redis_client.zadd(queue_key, {json.dumps(notification_item): score})
            
            self.logger.debug(f"Notification queued: {channel} to {address}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error queuing notification: {e}")
            return False
    
    async def process_queue(self) -> int:
        """
        Process notifications in the queue.
        Like a mail carrier delivering letters in order of priority.
        """
        processed = 0
        
        try:
            queue_key = "notification_queue"
            
            # Get highest priority items (lowest score)
            items = self.redis_client.zrange(queue_key, 0, 9, withscores=True)  # Process 10 at a time
            
            for item_data, score in items:
                try:
                    notification = json.loads(item_data)
                    
                    # Attempt delivery
                    success = await self.notification_service._send_notification(
                        notification['channel'],
                        notification['address'],
                        notification['alert']
                    )
                    
                    if success:
                        # Remove from queue on success
                        self.redis_client.zrem(queue_key, item_data)
                        processed += 1
                        self.logger.debug(f"Notification delivered: {notification['id']}")
                    else:
                        # Increment attempts
                        notification['attempts'] += 1
                        
                        if notification['attempts'] >= notification['max_attempts']:
                            # Max attempts reached, move to failed queue
                            failed_key = "notification_failed"
                            self.redis_client.lpush(failed_key, item_data)
                            self.redis_client.zrem(queue_key, item_data)
                            self.logger.error(f"Notification failed after {notification['max_attempts']} attempts: {notification['id']}")
                        else:
                            # Update with incremented attempts and lower priority (retry later)
                            self.redis_client.zrem(queue_key, item_data)
                            new_score = score + 1  # Lower priority for retries
                            self.redis_client.zadd(queue_key, {json.dumps(notification): new_score})
                
                except json.JSONDecodeError:
                    # Invalid data, remove from queue
                    self.redis_client.zrem(queue_key, item_data)
                except Exception as e:
                    self.logger.error(f"Error processing notification: {e}")
            
            return processed
            
        except Exception as e:
            self.logger.error(f"Error processing notification queue: {e}")
            return processed