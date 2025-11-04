import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
import redis
from enum import Enum

from .notification_service import NotificationService

class EscalationLevel(Enum):
    """Escalation levels - like emergency response severity levels"""
    LEVEL_1 = "level_1"  # Team leads, on-call engineers
    LEVEL_2 = "level_2"  # Managers, senior engineers  
    LEVEL_3 = "level_3"  # Directors, executives
    LEVEL_4 = "level_4"  # C-level, emergency response

class EscalationHandler:
    """
    Escalation Handler - like a smart emergency response coordinator.
    
    This manages alert escalations to ensure critical issues get the right attention:
    - Automatic escalation when alerts aren't acknowledged
    - Smart routing based on severity and business impact
    - Executive notifications for critical system failures
    - Follow-up and resolution tracking
    
    Think of this as your platform's emergency management system that ensures
    critical issues affecting your 99.9% uptime target get resolved quickly.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.notification_service = NotificationService()
        
        # Escalation matrix - defines who gets notified at each level
        self.escalation_matrix = self._initialize_escalation_matrix()
        
        # Escalation timing rules
        self.escalation_timings = {
            'critical': {
                'level_1': 5,   # 5 minutes to Level 1
                'level_2': 15,  # 15 minutes to Level 2
                'level_3': 30,  # 30 minutes to Level 3
                'level_4': 60   # 1 hour to executives
            },
            'warning': {
                'level_1': 15,  # 15 minutes to Level 1
                'level_2': 60,  # 1 hour to Level 2
                'level_3': 240, # 4 hours to Level 3
                'level_4': None # No executive escalation for warnings
            },
            'emergency': {
                'level_1': 1,   # Immediate Level 1
                'level_2': 5,   # 5 minutes to Level 2
                'level_3': 10,  # 10 minutes to Level 3
                'level_4': 20   # 20 minutes to executives
            }
        }
        
        # Business impact categorization
        self.business_impact_rules = self._initialize_business_impact_rules()
        
        # Escalation suppression rules (prevent over-escalation)
        self.suppression_rules = {
            'similar_alerts_window_minutes': 30,
            'max_escalations_per_hour': 5,
            'executive_notification_cooldown_minutes': 120  # Don't spam executives
        }
    
    def _initialize_escalation_matrix(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Initialize escalation matrix - like an emergency contact tree.
        Defines who gets contacted at each escalation level for different categories.
        """
        return {
            'performance': {  # Your <100ms SLA violations
                'level_1': ['sre-team', 'backend-team', 'on-call-engineer'],
                'level_2': ['engineering-manager', 'sre-manager'],
                'level_3': ['vp-engineering', 'cto'],
                'level_4': ['ceo', 'cto', 'head-of-operations']
            },
            'availability': {  # System downtime affecting 99.9% uptime
                'level_1': ['sre-team', 'devops-team', 'on-call-engineer'],
                'level_2': ['engineering-manager', 'infrastructure-manager'],
                'level_3': ['vp-engineering', 'cto'],
                'level_4': ['ceo', 'cto', 'head-of-operations', 'head-of-customer-success']
            },
            'security': {  # Security incidents
                'level_1': ['security-team', 'sre-team'],
                'level_2': ['security-manager', 'engineering-manager'],
                'level_3': ['ciso', 'cto'],
                'level_4': ['ceo', 'ciso', 'legal-team']
            },
            'business': {  # Revenue/customer impact
                'level_1': ['product-team', 'customer-success'],
                'level_2': ['product-manager', 'head-of-customer-success'],
                'level_3': ['vp-product', 'coo'],
                'level_4': ['ceo', 'coo', 'head-of-sales']
            },
            'infrastructure': {  # Infrastructure failures
                'level_1': ['devops-team', 'infrastructure-team'],
                'level_2': ['infrastructure-manager', 'devops-manager'],
                'level_3': ['vp-engineering', 'cto'],
                'level_4': ['cto', 'head-of-operations']
            },
            'capacity': {  # Scaling issues affecting 1,000+ RPS capability
                'level_1': ['sre-team', 'infrastructure-team'],
                'level_2': ['sre-manager', 'infrastructure-manager'],
                'level_3': ['vp-engineering', 'cto'],
                'level_4': ['cto', 'head-of-operations']
            }
        }
    
    def _initialize_business_impact_rules(self) -> Dict[str, Dict[str, Any]]:
        """
        Initialize business impact assessment rules.
        Like a triage system that determines how urgent each issue is.
        """
        return {
            'revenue_impact': {
                'high': {
                    'conditions': ['billing_system_down', 'payment_processing_failed', 'subscription_issues'],
                    'escalation_multiplier': 1.5,  # Escalate 50% faster
                    'force_executive_notification': True
                },
                'medium': {
                    'conditions': ['api_rate_limiting', 'performance_degradation'],
                    'escalation_multiplier': 1.2,
                    'force_executive_notification': False
                }
            },
            'customer_impact': {
                'widespread': {  # >50% of users affected
                    'conditions': ['service_unavailable', 'major_outage'],
                    'escalation_multiplier': 2.0,  # Double escalation speed
                    'force_executive_notification': True,
                    'require_status_page_update': True
                },
                'significant': {  # 10-50% of users affected
                    'conditions': ['partial_outage', 'api_errors'],
                    'escalation_multiplier': 1.3,
                    'force_executive_notification': False
                }
            },
            'sla_impact': {
                'sla_breach': {  # Your 99.9% uptime or <100ms targets
                    'conditions': ['uptime_below_sla', 'response_time_above_sla'],
                    'escalation_multiplier': 1.4,
                    'force_executive_notification': True,
                    'require_incident_report': True
                }
            }
        }
    
    async def process_alert_for_escalation(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an alert to determine if escalation is needed.
        Like a triage nurse assessing if a patient needs immediate attention.
        """
        try:
            alert_id = alert.get('id')
            severity = alert.get('severity', 'info')
            category = alert.get('category', 'general')
            created_at = datetime.fromisoformat(alert.get('created_at'))
            
            # Check if alert should be escalated
            escalation_needed = await self._should_escalate_alert(alert)
            
            if not escalation_needed:
                return {'escalation_needed': False, 'reason': 'No escalation criteria met'}
            
            # Determine escalation level
            escalation_level = await self._determine_escalation_level(alert)
            
            # Check for suppression rules
            if await self._is_escalation_suppressed(alert, escalation_level):
                return {
                    'escalation_needed': False, 
                    'reason': 'Escalation suppressed due to recent similar escalations'
                }
            
            # Create escalation record
            escalation = await self._create_escalation_record(alert, escalation_level)
            
            # Execute escalation
            escalation_result = await self._execute_escalation(escalation)
            
            # Schedule follow-up if needed
            await self._schedule_escalation_followup(escalation)
            
            return {
                'escalation_needed': True,
                'escalation_id': escalation['id'],
                'level': escalation_level.value,
                'notifications_sent': escalation_result.get('notifications_sent', 0),
                'next_escalation_at': escalation.get('next_escalation_at')
            }
            
        except Exception as e:
            self.logger.error(f"Error processing alert for escalation: {e}")
            return {'escalation_needed': False, 'error': str(e)}
    
    async def _should_escalate_alert(self, alert: Dict[str, Any]) -> bool:
        """
        Determine if an alert should be escalated.
        Like deciding if a situation requires calling for backup.
        """
        try:
            alert_id = alert.get('id')
            severity = alert.get('severity', 'info')
            created_at = datetime.fromisoformat(alert.get('created_at'))
            
            # Check if alert has been acknowledged
            is_acknowledged = await self._is_alert_acknowledged(alert_id)
            if is_acknowledged:
                return False
            
            # Check escalation timing
            escalation_times = self.escalation_timings.get(severity, {})
            if not escalation_times:
                return False
            
            # Calculate time since alert creation
            time_since_creation = (datetime.utcnow() - created_at).total_seconds() / 60
            
            # Check if any escalation level timing is met
            for level, minutes in escalation_times.items():
                if minutes and time_since_creation >= minutes:
                    # Check if this level has already been escalated
                    if not await self._has_level_been_escalated(alert_id, level):
                        return True
            
            # Check for business impact that requires immediate escalation
            business_impact = await self._assess_business_impact(alert)
            if business_impact.get('force_immediate_escalation', False):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error determining if alert should escalate: {e}")
            return False
    
    async def _determine_escalation_level(self, alert: Dict[str, Any]) -> EscalationLevel:
        """
        Determine the appropriate escalation level.
        Like determining how many fire trucks to send to an emergency.
        """
        try:
            alert_id = alert.get('id')
            severity = alert.get('severity', 'info')
            created_at = datetime.fromisoformat(alert.get('created_at'))
            
            # Calculate time since creation
            time_since_creation = (datetime.utcnow() - created_at).total_seconds() / 60
            
            # Get escalation timings for this severity
            escalation_times = self.escalation_timings.get(severity, {})
            
            # Determine highest level that should be escalated based on time
            target_level = EscalationLevel.LEVEL_1  # Default
            
            for level_name, minutes in escalation_times.items():
                if minutes and time_since_creation >= minutes:
                    # Check if this level hasn't been escalated yet
                    if not await self._has_level_been_escalated(alert_id, level_name):
                        if level_name == 'level_1':
                            target_level = EscalationLevel.LEVEL_1
                        elif level_name == 'level_2':
                            target_level = EscalationLevel.LEVEL_2
                        elif level_name == 'level_3':
                            target_level = EscalationLevel.LEVEL_3
                        elif level_name == 'level_4':
                            target_level = EscalationLevel.LEVEL_4
            
            # Check for business impact adjustments
            business_impact = await self._assess_business_impact(alert)
            if business_impact.get('force_executive_notification', False):
                target_level = max(target_level, EscalationLevel.LEVEL_3)
            
            return target_level
            
        except Exception as e:
            self.logger.error(f"Error determining escalation level: {e}")
            return EscalationLevel.LEVEL_1
    
    async def _assess_business_impact(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess the business impact of an alert.
        Like evaluating how much a problem will cost the company.
        """
        try:
            alert_message = alert.get('message', '').lower()
            category = alert.get('category', 'general')
            severity = alert.get('severity', 'info')
            
            impact_assessment = {
                'revenue_impact': 'low',
                'customer_impact': 'minimal',
                'sla_impact': False,
                'force_immediate_escalation': False,
                'force_executive_notification': False,
                'require_status_page_update': False,
                'require_incident_report': False,
                'escalation_multiplier': 1.0
            }
            
            # Assess revenue impact
            revenue_keywords = ['billing', 'payment', 'subscription', 'checkout', 'purchase']
            if any(keyword in alert_message for keyword in revenue_keywords):
                impact_assessment['revenue_impact'] = 'high'
                impact_assessment['force_executive_notification'] = True
                impact_assessment['escalation_multiplier'] = 1.5
            
            # Assess customer impact based on availability and performance
            if category == 'availability':
                if 'service_unavailable' in alert_message or 'major_outage' in alert_message:
                    impact_assessment['customer_impact'] = 'widespread'
                    impact_assessment['force_executive_notification'] = True
                    impact_assessment['require_status_page_update'] = True
                    impact_assessment['escalation_multiplier'] = 2.0
                elif 'partial_outage' in alert_message:
                    impact_assessment['customer_impact'] = 'significant'
                    impact_assessment['escalation_multiplier'] = 1.3
            
            # Assess SLA impact (your 99.9% uptime and <100ms targets)
            sla_keywords = ['sla_violation', 'uptime_below', 'response_time_above']
            if any(keyword in alert_message for keyword in sla_keywords):
                impact_assessment['sla_impact'] = True
                impact_assessment['force_executive_notification'] = True
                impact_assessment['require_incident_report'] = True
                impact_assessment['escalation_multiplier'] = 1.4
            
            # High-volume platform specific impacts (your 100M+ requests)
            capacity_keywords = ['capacity', 'overload', 'rate_limit', 'scaling']
            if any(keyword in alert_message for keyword in capacity_keywords):
                impact_assessment['escalation_multiplier'] = 1.3
                if severity in ['critical', 'emergency']:
                    impact_assessment['force_executive_notification'] = True
            
            # Security incidents always have high business impact
            if category == 'security':
                impact_assessment['force_executive_notification'] = True
                impact_assessment['require_incident_report'] = True
                impact_assessment['escalation_multiplier'] = 1.5
            
            return impact_assessment
            
        except Exception as e:
            self.logger.error(f"Error assessing business impact: {e}")
            return {'escalation_multiplier': 1.0}
    
    async def _is_escalation_suppressed(self, alert: Dict[str, Any], level: EscalationLevel) -> bool:
        """
        Check if escalation should be suppressed to prevent alert fatigue.
        Like not calling 911 multiple times for the same emergency.
        """
        try:
            alert_id = alert.get('id')
            category = alert.get('category', 'general')
            
            # Check for recent similar escalations
            recent_escalations = await self._get_recent_escalations(
                category, 
                self.suppression_rules['similar_alerts_window_minutes']
            )
            
            # Count escalations in the last hour
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_count = len([
                esc for esc in recent_escalations 
                if datetime.fromisoformat(esc['created_at']) > hour_ago
            ])
            
            if recent_count >= self.suppression_rules['max_escalations_per_hour']:
                self.logger.warning(f"Suppressing escalation for {alert_id}: too many recent escalations")
                return True
            
            # Check executive notification cooldown
            if level in [EscalationLevel.LEVEL_3, EscalationLevel.LEVEL_4]:
                last_executive_notification = await self._get_last_executive_notification_time()
                if last_executive_notification:
                    cooldown_minutes = self.suppression_rules['executive_notification_cooldown_minutes']
                    time_since_last = (datetime.utcnow() - last_executive_notification).total_seconds() / 60
                    
                    if time_since_last < cooldown_minutes:
                        self.logger.info(f"Suppressing executive escalation: in cooldown period")
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking escalation suppression: {e}")
            return False
    
    async def _create_escalation_record(self, alert: Dict[str, Any], level: EscalationLevel) -> Dict[str, Any]:
        """
        Create a record of the escalation.
        Like filling out an incident report form.
        """
        try:
            escalation_id = f"esc-{alert.get('id')}-{level.value}-{int(datetime.utcnow().timestamp())}"
            
            escalation = {
                'id': escalation_id,
                'alert_id': alert.get('id'),
                'alert_category': alert.get('category', 'general'),
                'alert_severity': alert.get('severity', 'info'),
                'escalation_level': level.value,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'pending',
                'business_impact': await self._assess_business_impact(alert),
                'target_contacts': self._get_escalation_contacts(alert.get('category', 'general'), level),
                'notifications_sent': [],
                'acknowledged_by': None,
                'acknowledged_at': None,
                'resolved_at': None,
                'next_escalation_at': self._calculate_next_escalation_time(alert, level),
                'metadata': {
                    'original_alert': alert,
                    'escalation_reason': f"Alert not acknowledged within required timeframe for {level.value}",
                    'business_justification': self._generate_business_justification(alert, level)
                }
            }
            
            # Store escalation record
            escalation_key = f"escalations:active:{escalation_id}"
            self.redis_client.setex(escalation_key, 86400, json.dumps(escalation))  # 24 hours
            
            # Add to escalation tracking
            await self._track_escalation(escalation)
            
            return escalation
            
        except Exception as e:
            self.logger.error(f"Error creating escalation record: {e}")
            return {}
    
    def _get_escalation_contacts(self, category: str, level: EscalationLevel) -> List[str]:
        """Get the list of contacts for escalation level and category"""
        escalation_matrix = self.escalation_matrix.get(category, {})
        return escalation_matrix.get(level.value, [])
    
    def _calculate_next_escalation_time(self, alert: Dict[str, Any], current_level: EscalationLevel) -> Optional[str]:
        """Calculate when the next escalation should occur"""
        try:
            severity = alert.get('severity', 'info')
            escalation_times = self.escalation_timings.get(severity, {})
            
            # Determine next level
            level_order = [EscalationLevel.LEVEL_1, EscalationLevel.LEVEL_2, EscalationLevel.LEVEL_3, EscalationLevel.LEVEL_4]
            current_index = level_order.index(current_level)
            
            if current_index + 1 < len(level_order):
                next_level = level_order[current_index + 1]
                next_level_minutes = escalation_times.get(next_level.value.replace('level_', 'level_'))
                
                if next_level_minutes:
                    alert_created = datetime.fromisoformat(alert.get('created_at'))
                    next_escalation_time = alert_created + timedelta(minutes=next_level_minutes)
                    return next_escalation_time.isoformat()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error calculating next escalation time: {e}")
            return None
    
    def _generate_business_justification(self, alert: Dict[str, Any], level: EscalationLevel) -> str:
        """Generate business justification for the escalation"""
        severity = alert.get('severity', 'info')
        category = alert.get('category', 'general')
        
        justifications = {
            EscalationLevel.LEVEL_1: f"Initial response team notification for {severity} {category} alert",
            EscalationLevel.LEVEL_2: f"Management notification required - {severity} alert unresolved",
            EscalationLevel.LEVEL_3: f"Senior leadership notification - critical business impact from {category} issue",
            EscalationLevel.LEVEL_4: f"Executive notification - potential significant impact to business operations and customer experience"
        }
        
        base_justification = justifications.get(level, "Escalation required")
        
        # Add specific business context
        if category == 'availability':
            base_justification += " (may impact 99.9% uptime SLA)"
        elif category == 'performance':
            base_justification += " (may impact <100ms response time SLA)"
        elif category == 'capacity':
            base_justification += " (may impact 1,000+ RPS capability)"
        
        return base_justification
    
    async def _execute_escalation(self, escalation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the escalation by sending notifications.
        Like actually making the emergency phone calls.
        """
        try:
            escalation_id = escalation['id']
            level = escalation['escalation_level']
            target_contacts = escalation['target_contacts']
            alert = escalation['metadata']['original_alert']
            
            # Create escalation alert message
            escalation_alert = self._create_escalation_alert(escalation, alert)
            
            # Send notifications to all target contacts
            notifications_sent = 0
            failed_notifications = []
            
            for contact in target_contacts:
                try:
                    success = await self.notification_service.send_alert({
                        **escalation_alert,
                        'escalation_level': level,
                        'escalation_id': escalation_id,
                        'routing': {'primary': [contact]}
                    })
                    
                    if success:
                        notifications_sent += 1
                        escalation['notifications_sent'].append({
                            'contact': contact,
                            'sent_at': datetime.utcnow().isoformat(),
                            'success': True
                        })
                    else:
                        failed_notifications.append(contact)
                        
                except Exception as e:
                    self.logger.error(f"Failed to send escalation notification to {contact}: {e}")
                    failed_notifications.append(contact)
            
            # Update escalation record
            escalation['status'] = 'sent' if notifications_sent > 0 else 'failed'
            escalation['updated_at'] = datetime.utcnow().isoformat()
            
            # Store updated escalation
            escalation_key = f"escalations:active:{escalation_id}"
            self.redis_client.setex(escalation_key, 86400, json.dumps(escalation))
            
            # Log escalation
            self.logger.info(
                f"Escalation {escalation_id} executed: {notifications_sent} notifications sent, "
                f"{len(failed_notifications)} failed"
            )
            
            return {
                'escalation_id': escalation_id,
                'notifications_sent': notifications_sent,
                'failed_notifications': failed_notifications,
                'status': escalation['status']
            }
            
        except Exception as e:
            self.logger.error(f"Error executing escalation: {e}")
            return {'notifications_sent': 0, 'error': str(e)}
    
    def _create_escalation_alert(self, escalation: Dict[str, Any], original_alert: Dict[str, Any]) -> Dict[str, Any]:
        """Create an enhanced alert for escalation notifications"""
        level = escalation['escalation_level']
        business_impact = escalation.get('business_impact', {})
        
        # Create escalated alert with additional context
        escalation_alert = {
            **original_alert,
            'escalated': True,
            'escalation_level': level,
            'escalation_id': escalation['id'],
            'message': f"🚨 ESCALATED {level.upper()}: {original_alert['message']}",
            'severity': 'critical' if level in ['level_3', 'level_4'] else original_alert.get('severity', 'warning'),
            'escalation_context': {
                'time_since_creation': self._calculate_time_since_creation(original_alert),
                'business_impact': business_impact,
                'escalation_reason': escalation['metadata']['escalation_reason'],
                'business_justification': escalation['metadata']['business_justification']
            }
        }
        
        return escalation_alert
    
    def _calculate_time_since_creation(self, alert: Dict[str, Any]) -> str:
        """Calculate human-readable time since alert creation"""
        try:
            created_at = datetime.fromisoformat(alert['created_at'])
            time_diff = datetime.utcnow() - created_at
            
            minutes = int(time_diff.total_seconds() / 60)
            if minutes < 60:
                return f"{minutes} minutes"
            else:
                hours = minutes // 60
                remaining_minutes = minutes % 60
                return f"{hours}h {remaining_minutes}m"
                
        except Exception as e:
            return "unknown duration"
    
    async def _schedule_escalation_followup(self, escalation: Dict[str, Any]):
        """Schedule follow-up escalation if needed"""
        try:
            next_escalation_at = escalation.get('next_escalation_at')
            
            if next_escalation_at:
                followup_key = f"escalations:followup:{escalation['id']}"
                followup_data = {
                    'escalation_id': escalation['id'],
                    'alert_id': escalation['alert_id'],
                    'scheduled_for': next_escalation_at,
                    'status': 'scheduled'
                }
                
                # Calculate TTL until next escalation
                next_time = datetime.fromisoformat(next_escalation_at)
                ttl_seconds = int((next_time - datetime.utcnow()).total_seconds()) + 300  # 5 min buffer
                
                if ttl_seconds > 0:
                    self.redis_client.setex(followup_key, ttl_seconds, json.dumps(followup_data))
                    
                    self.logger.info(
                        f"Scheduled follow-up escalation for {escalation['id']} at {next_escalation_at}"
                    )
                
        except Exception as e:
            self.logger.error(f"Error scheduling escalation follow-up: {e}")
    
    async def acknowledge_escalation(self, escalation_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge an escalation - like confirming you've received the emergency call.
        """
        try:
            escalation_key = f"escalations:active:{escalation_id}"
            escalation_data = self.redis_client.get(escalation_key)
            
            if not escalation_data:
                self.logger.warning(f"Escalation {escalation_id} not found")
                return False
            
            escalation = json.loads(escalation_data)
            
            # Update escalation record
            escalation['status'] = 'acknowledged'
            escalation['acknowledged_by'] = acknowledged_by
            escalation['acknowledged_at'] = datetime.utcnow().isoformat()
            escalation['updated_at'] = datetime.utcnow().isoformat()
            
            # Store updated escalation
            self.redis_client.setex(escalation_key, 86400, json.dumps(escalation))
            
            # Cancel follow-up escalations
            await self._cancel_followup_escalations(escalation_id)
            
            # Send acknowledgment notification
            await self._send_acknowledgment_notification(escalation, acknowledged_by)
            
            self.logger.info(f"Escalation {escalation_id} acknowledged by {acknowledged_by}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error acknowledging escalation {escalation_id}: {e}")
            return False
    
    async def _cancel_followup_escalations(self, escalation_id: str):
        """Cancel scheduled follow-up escalations"""
        try:
            followup_key = f"escalations:followup:{escalation_id}"
            followup_data = self.redis_client.get(followup_key)
            
            if followup_data:
                followup = json.loads(followup_data)
                followup['status'] = 'cancelled'
                followup['cancelled_at'] = datetime.utcnow().isoformat()
                
                # Update with short TTL to clean up
                self.redis_client.setex(followup_key, 300, json.dumps(followup))
                
                self.logger.info(f"Cancelled follow-up escalation for {escalation_id}")
                
        except Exception as e:
            self.logger.error(f"Error cancelling follow-up escalations: {e}")
    
    async def _send_acknowledgment_notification(self, escalation: Dict[str, Any], acknowledged_by: str):
        """Send notification that escalation was acknowledged"""
        try:
            # Create acknowledgment alert
            acknowledgment_alert = {
                'id': f"ack-{escalation['id']}",
                'type': 'escalation_acknowledgment',
                'severity': 'info',
                'category': escalation['alert_category'],
                'message': f"✅ Escalation {escalation['escalation_level'].upper()} acknowledged by {acknowledged_by}",
                'details': {
                    'escalation_id': escalation['id'],
                    'alert_id': escalation['alert_id'],
                    'acknowledged_by': acknowledged_by,
                    'acknowledged_at': escalation['acknowledged_at'],
                    'original_message': escalation['metadata']['original_alert']['message']
                },
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Send to original escalation contacts for awareness
            target_contacts = escalation['target_contacts']
            
            for contact in target_contacts:
                try:
                    await self.notification_service.send_alert({
                        **acknowledgment_alert,
                        'routing': {'primary': [contact]}
                    })
                except Exception as e:
                    self.logger.error(f"Failed to send acknowledgment notification to {contact}: {e}")
            
            self.logger.info(f"Sent acknowledgment notifications for escalation {escalation['id']}")
            
        except Exception as e:
            self.logger.error(f"Error sending acknowledgment notification: {e}")
    
    async def resolve_escalation(self, escalation_id: str, resolved_by: str, resolution_notes: str = "") -> bool:
        """
        Mark an escalation as resolved.
        Like closing an emergency incident report.
        """
        try:
            escalation_key = f"escalations:active:{escalation_id}"
            escalation_data = self.redis_client.get(escalation_key)
            
            if not escalation_data:
                self.logger.warning(f"Escalation {escalation_id} not found")
                return False
            
            escalation = json.loads(escalation_data)
            
            # Update escalation record
            escalation['status'] = 'resolved'
            escalation['resolved_by'] = resolved_by
            escalation['resolved_at'] = datetime.utcnow().isoformat()
            escalation['resolution_notes'] = resolution_notes
            escalation['updated_at'] = datetime.utcnow().isoformat()
            
            # Move to resolved escalations with longer TTL for reporting
            resolved_key = f"escalations:resolved:{escalation_id}"
            self.redis_client.setex(resolved_key, 604800, json.dumps(escalation))  # 7 days
            
            # Remove from active escalations
            self.redis_client.delete(escalation_key)
            
            # Cancel any pending follow-ups
            await self._cancel_followup_escalations(escalation_id)
            
            # Send resolution notification
            await self._send_resolution_notification(escalation, resolved_by, resolution_notes)
            
            self.logger.info(f"Escalation {escalation_id} resolved by {resolved_by}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resolving escalation {escalation_id}: {e}")
            return False
    
    async def _send_resolution_notification(self, escalation: Dict[str, Any], resolved_by: str, resolution_notes: str):
        """Send notification that escalation was resolved"""
        try:
            # Create resolution alert
            resolution_alert = {
                'id': f"res-{escalation['id']}",
                'type': 'escalation_resolution',
                'severity': 'info',
                'category': escalation['alert_category'],
                'message': f"✅ Escalation {escalation['escalation_level'].upper()} RESOLVED by {resolved_by}",
                'details': {
                    'escalation_id': escalation['id'],
                    'alert_id': escalation['alert_id'],
                    'resolved_by': resolved_by,
                    'resolved_at': escalation['resolved_at'],
                    'resolution_notes': resolution_notes,
                    'duration': self._calculate_escalation_duration(escalation),
                    'original_message': escalation['metadata']['original_alert']['message']
                },
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Send to stakeholders for closure awareness
            target_contacts = escalation['target_contacts']
            
            for contact in target_contacts:
                try:
                    await self.notification_service.send_alert({
                        **resolution_alert,
                        'routing': {'primary': [contact]}
                    })
                except Exception as e:
                    self.logger.error(f"Failed to send resolution notification to {contact}: {e}")
            
            self.logger.info(f"Sent resolution notifications for escalation {escalation['id']}")
            
        except Exception as e:
            self.logger.error(f"Error sending resolution notification: {e}")
    
    def _calculate_escalation_duration(self, escalation: Dict[str, Any]) -> str:
        """Calculate duration of escalation"""
        try:
            created_at = datetime.fromisoformat(escalation['created_at'])
            resolved_at = datetime.fromisoformat(escalation['resolved_at'])
            duration = resolved_at - created_at
            
            minutes = int(duration.total_seconds() / 60)
            if minutes < 60:
                return f"{minutes} minutes"
            else:
                hours = minutes // 60
                remaining_minutes = minutes % 60
                return f"{hours}h {remaining_minutes}m"
                
        except Exception as e:
            return "unknown duration"
    
    async def get_active_escalations(self) -> List[Dict[str, Any]]:
        """Get all currently active escalations"""
        try:
            pattern = "escalations:active:*"
            keys = self.redis_client.keys(pattern)
            
            escalations = []
            for key in keys:
                escalation_data = self.redis_client.get(key)
                if escalation_data:
                    escalation = json.loads(escalation_data)
                    escalations.append(escalation)
            
            # Sort by creation time (most recent first)
            escalations.sort(key=lambda x: x['created_at'], reverse=True)
            return escalations
            
        except Exception as e:
            self.logger.error(f"Error getting active escalations: {e}")
            return []
    
    async def get_escalation_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get escalation metrics for the specified time period"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Get active and resolved escalations
            active_escalations = await self.get_active_escalations()
            resolved_escalations = await self._get_resolved_escalations(hours)
            
            all_escalations = active_escalations + resolved_escalations
            
            # Filter by time period
            recent_escalations = [
                esc for esc in all_escalations
                if datetime.fromisoformat(esc['created_at']) > cutoff_time
            ]
            
            # Calculate metrics
            metrics = {
                'total_escalations': len(recent_escalations),
                'active_escalations': len(active_escalations),
                'resolved_escalations': len(resolved_escalations),
                'escalations_by_level': self._group_by_level(recent_escalations),
                'escalations_by_category': self._group_by_category(recent_escalations),
                'average_resolution_time': self._calculate_average_resolution_time(resolved_escalations),
                'executive_notifications': len([
                    esc for esc in recent_escalations 
                    if esc['escalation_level'] in ['level_3', 'level_4']
                ]),
                'suppressed_escalations': await self._get_suppressed_escalations_count(hours)
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating escalation metrics: {e}")
            return {}
    
    # Helper methods for missing functionality
    
    async def _is_alert_acknowledged(self, alert_id: str) -> bool:
        """Check if an alert has been acknowledged"""
        try:
            ack_key = f"alerts:acknowledged:{alert_id}"
            return self.redis_client.exists(ack_key)
        except Exception as e:
            self.logger.error(f"Error checking alert acknowledgment: {e}")
            return False
    
    async def _has_level_been_escalated(self, alert_id: str, level: str) -> bool:
        """Check if a specific escalation level has already been triggered for this alert"""
        try:
            escalation_pattern = f"escalations:*:esc-{alert_id}-{level}-*"
            keys = self.redis_client.keys(escalation_pattern)
            return len(keys) > 0
        except Exception as e:
            self.logger.error(f"Error checking escalation level: {e}")
            return False
    
    async def _get_recent_escalations(self, category: str, window_minutes: int) -> List[Dict[str, Any]]:
        """Get recent escalations for a category within the time window"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
            
            # Get all active escalations
            active_escalations = await self.get_active_escalations()
            
            # Filter by category and time
            recent = [
                esc for esc in active_escalations
                if (esc['alert_category'] == category and 
                    datetime.fromisoformat(esc['created_at']) > cutoff_time)
            ]
            
            return recent
            
        except Exception as e:
            self.logger.error(f"Error getting recent escalations: {e}")
            return []
    
    async def _get_last_executive_notification_time(self) -> Optional[datetime]:
        """Get the timestamp of the last executive notification"""
        try:
            key = "escalations:last_executive_notification"
            timestamp_str = self.redis_client.get(key)
            
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str.decode())
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting last executive notification time: {e}")
            return None
    
    async def _track_escalation(self, escalation: Dict[str, Any]):
        """Track escalation for metrics and suppression"""
        try:
            # Track by category
            category_key = f"escalations:tracking:{escalation['alert_category']}"
            tracking_data = {
                'escalation_id': escalation['id'],
                'level': escalation['escalation_level'],
                'created_at': escalation['created_at']
            }
            
            # Add to sorted set with timestamp score for time-based queries
            timestamp = datetime.fromisoformat(escalation['created_at']).timestamp()
            self.redis_client.zadd(category_key, {escalation['id']: timestamp})
            self.redis_client.expire(category_key, 86400)  # 24 hours
            
            # Track executive notifications
            if escalation['escalation_level'] in ['level_3', 'level_4']:
                exec_key = "escalations:last_executive_notification"
                self.redis_client.setex(exec_key, 7200, escalation['created_at'])  # 2 hours
            
        except Exception as e:
            self.logger.error(f"Error tracking escalation: {e}")
    
    async def _get_resolved_escalations(self, hours: int) -> List[Dict[str, Any]]:
        """Get resolved escalations within the specified hours"""
        try:
            pattern = "escalations:resolved:*"
            keys = self.redis_client.keys(pattern)
            
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            escalations = []
            
            for key in keys:
                escalation_data = self.redis_client.get(key)
                if escalation_data:
                    escalation = json.loads(escalation_data)
                    if datetime.fromisoformat(escalation['resolved_at']) > cutoff_time:
                        escalations.append(escalation)
            
            return escalations
            
        except Exception as e:
            self.logger.error(f"Error getting resolved escalations: {e}")
            return []
    
    def _group_by_level(self, escalations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group escalations by level"""
        level_counts = {'level_1': 0, 'level_2': 0, 'level_3': 0, 'level_4': 0}
        for esc in escalations:
            level = esc.get('escalation_level', 'level_1')
            level_counts[level] = level_counts.get(level, 0) + 1
        return level_counts
    
    def _group_by_category(self, escalations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group escalations by category"""
        category_counts = {}
        for esc in escalations:
            category = esc.get('alert_category', 'general')
            category_counts[category] = category_counts.get(category, 0) + 1
        return category_counts
    
    def _calculate_average_resolution_time(self, resolved_escalations: List[Dict[str, Any]]) -> str:
        """Calculate average resolution time"""
        if not resolved_escalations:
            return "N/A"
        
        try:
            total_minutes = 0
            count = 0
            
            for esc in resolved_escalations:
                if 'resolved_at' in esc and 'created_at' in esc:
                    created = datetime.fromisoformat(esc['created_at'])
                    resolved = datetime.fromisoformat(esc['resolved_at'])
                    duration_minutes = (resolved - created).total_seconds() / 60
                    total_minutes += duration_minutes
                    count += 1
            
            if count > 0:
                avg_minutes = int(total_minutes / count)
                if avg_minutes < 60:
                    return f"{avg_minutes} minutes"
                else:
                    hours = avg_minutes // 60
                    minutes = avg_minutes % 60
                    return f"{hours}h {minutes}m"
            
            return "N/A"
            
        except Exception as e:
            self.logger.error(f"Error calculating average resolution time: {e}")
            return "N/A"
    
    async def _get_suppressed_escalations_count(self, hours: int) -> int:
        """Get count of suppressed escalations"""
        try:
            # This would track suppressed escalations if we stored them
            # For now, return 0 as we don't persist suppression events
            return 0
        except Exception as e:
            self.logger.error(f"Error getting suppressed escalations count: {e}")
            return 0
    
    async def process_scheduled_escalations(self):
        """
        Process scheduled follow-up escalations.
        This should be called periodically by a background worker.
        """
        try:
            pattern = "escalations:followup:*"
            keys = self.redis_client.keys(pattern)
            
            current_time = datetime.utcnow()
            processed = 0
            
            for key in keys:
                followup_data = self.redis_client.get(key)
                if followup_data:
                    followup = json.loads(followup_data)
                    
                    if followup['status'] == 'scheduled':
                        scheduled_time = datetime.fromisoformat(followup['scheduled_for'])
                        
                        if current_time >= scheduled_time:
                            # Get the original alert and process escalation
                            alert_id = followup['alert_id']
                            alert_key = f"alerts:active:{alert_id}"
                            alert_data = self.redis_client.get(alert_key)
                            
                            if alert_data:
                                alert = json.loads(alert_data)
                                result = await self.process_alert_for_escalation(alert)
                                
                                if result.get('escalation_needed'):
                                    processed += 1
                                    
                                    # Mark followup as processed
                                    followup['status'] = 'processed'
                                    followup['processed_at'] = current_time.isoformat()
                                    self.redis_client.setex(key, 300, json.dumps(followup))
                            else:
                                # Alert no longer exists, cancel followup
                                followup['status'] = 'cancelled'
                                followup['cancelled_at'] = current_time.isoformat()
                                self.redis_client.setex(key, 300, json.dumps(followup))
            
            if processed > 0:
                self.logger.info(f"Processed {processed} scheduled escalations")
                
        except Exception as e:
            self.logger.error(f"Error processing scheduled escalations: {e}")