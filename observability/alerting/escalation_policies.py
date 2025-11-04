"""
Escalation Policies for LLM API Platform
Manages alert escalation, on-call schedules, and incident response automation.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json

from .alert_rules import Alert, AlertSeverity, AlertStatus
from .notification_channels import NotificationManager, notification_manager

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    LEVEL_1 = "level_1"  # First responders
    LEVEL_2 = "level_2"  # Senior engineers
    LEVEL_3 = "level_3"  # Management
    LEVEL_4 = "level_4"  # Executive


@dataclass
class OnCallSchedule:
    """Defines on-call schedule for a team or individual"""
    id: str
    name: str
    timezone: str
    schedule_type: str  # "daily", "weekly", "monthly"
    rotation: List[str]  # List of user IDs or team names
    current_index: int = 0
    last_rotation: Optional[datetime] = None


@dataclass
class EscalationStep:
    """Single step in an escalation policy"""
    level: EscalationLevel
    delay_minutes: int
    notification_channels: List[str]
    on_call_schedules: List[str] = field(default_factory=list)
    conditions: Optional[Dict[str, Any]] = None
    max_attempts: int = 3


@dataclass
class EscalationPolicy:
    """Complete escalation policy definition"""
    id: str
    name: str
    description: str
    steps: List[EscalationStep]
    filters: Optional[Dict[str, Any]] = None
    enabled: bool = True


@dataclass
class EscalationInstance:
    """Active escalation for a specific alert"""
    id: str
    policy_id: str
    alert_id: str
    current_step: int
    started_at: datetime
    last_escalation: Optional[datetime] = None
    acknowledgments: List[str] = field(default_factory=list)
    resolved: bool = False


class EscalationManager:
    """Manages escalation policies and active escalations"""

    def __init__(self, notification_manager: NotificationManager):
        self.notification_manager = notification_manager
        self.policies: Dict[str, EscalationPolicy] = {}
        self.schedules: Dict[str, OnCallSchedule] = {}
        self.active_escalations: Dict[str, EscalationInstance] = {}
        self.escalation_history: deque = deque(maxlen=10000)
        self.acknowledgments: Dict[str, List[str]] = defaultdict(list)

    def add_policy(self, policy: EscalationPolicy):
        """Add or update an escalation policy"""
        self.policies[policy.id] = policy
        logger.info(f"Added escalation policy: {policy.name}")

    def remove_policy(self, policy_id: str):
        """Remove an escalation policy"""
        if policy_id in self.policies:
            del self.policies[policy_id]
            # Stop any active escalations for this policy
            escalations_to_stop = [
                esc_id for esc_id, esc in self.active_escalations.items()
                if esc.policy_id == policy_id
            ]
            for esc_id in escalations_to_stop:
                self.stop_escalation(esc_id, "Policy removed")
            logger.info(f"Removed escalation policy: {policy_id}")

    def add_schedule(self, schedule: OnCallSchedule):
        """Add or update an on-call schedule"""
        self.schedules[schedule.id] = schedule
        logger.info(f"Added on-call schedule: {schedule.name}")

    def remove_schedule(self, schedule_id: str):
        """Remove an on-call schedule"""
        if schedule_id in self.schedules:
            del self.schedules[schedule_id]
            logger.info(f"Removed on-call schedule: {schedule_id}")

    async def handle_alert(self, alert: Alert):
        """Handle alert with appropriate escalation policy"""
        # Find matching policy
        policy = self._find_matching_policy(alert)
        if not policy:
            logger.warning(f"No escalation policy found for alert: {alert.name}")
            return

        # Check if escalation already exists
        existing_escalation = self._find_active_escalation(alert.id)
        if existing_escalation:
            if alert.status == AlertStatus.RESOLVED:
                await self.stop_escalation(existing_escalation.id, "Alert resolved")
            return

        # Start new escalation
        if alert.status == AlertStatus.FIRING:
            await self.start_escalation(alert, policy)

    def _find_matching_policy(self, alert: Alert) -> Optional[EscalationPolicy]:
        """Find escalation policy that matches alert"""
        for policy in self.policies.values():
            if not policy.enabled:
                continue

            if policy.filters:
                if not self._alert_matches_filters(alert, policy.filters):
                    continue

            return policy

        return None

    def _alert_matches_filters(self, alert: Alert, filters: Dict[str, Any]) -> bool:
        """Check if alert matches policy filters"""
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

        # Service filter
        if 'service' in filters and alert.labels:
            if alert.labels.get('service') != filters['service']:
                return False

        return True

    def _find_active_escalation(self, alert_id: str) -> Optional[EscalationInstance]:
        """Find active escalation for alert"""
        for escalation in self.active_escalations.values():
            if escalation.alert_id == alert_id and not escalation.resolved:
                return escalation
        return None

    async def start_escalation(self, alert: Alert, policy: EscalationPolicy):
        """Start escalation for an alert"""
        escalation_id = f"esc_{alert.id}_{int(datetime.now().timestamp())}"

        escalation = EscalationInstance(
            id=escalation_id,
            policy_id=policy.id,
            alert_id=alert.id,
            current_step=0,
            started_at=datetime.now()
        )

        self.active_escalations[escalation_id] = escalation
        self.escalation_history.append(escalation)

        logger.info(f"Started escalation {escalation_id} for alert {alert.name} using policy {policy.name}")

        # Execute first step immediately
        await self._execute_escalation_step(escalation, policy, alert)

    async def stop_escalation(self, escalation_id: str, reason: str = ""):
        """Stop an active escalation"""
        if escalation_id in self.active_escalations:
            escalation = self.active_escalations[escalation_id]
            escalation.resolved = True

            # Move to history
            self.escalation_history.append(escalation)
            del self.active_escalations[escalation_id]

            logger.info(f"Stopped escalation {escalation_id}: {reason}")

    async def _execute_escalation_step(self, escalation: EscalationInstance, policy: EscalationPolicy, alert: Alert):
        """Execute current escalation step"""
        if escalation.current_step >= len(policy.steps):
            logger.warning(f"Escalation {escalation.id} reached maximum steps")
            return

        step = policy.steps[escalation.current_step]

        # Check step conditions
        if step.conditions and not self._check_step_conditions(step.conditions, alert):
            logger.info(f"Step {escalation.current_step} conditions not met, skipping")
            escalation.current_step += 1
            await self._schedule_next_step(escalation, policy, alert)
            return

        # Get notification targets
        targets = await self._get_notification_targets(step)

        # Send notifications
        for target in targets:
            try:
                await self.notification_manager.send_notification(alert, target)
            except Exception as e:
                logger.error(f"Failed to send escalation notification to {target}: {e}")

        escalation.last_escalation = datetime.now()

        logger.info(f"Executed escalation step {escalation.current_step} for alert {alert.name}")

        # Schedule next step if not acknowledged
        await self._schedule_next_step(escalation, policy, alert)

    async def _get_notification_targets(self, step: EscalationStep) -> List[str]:
        """Get notification targets for escalation step"""
        targets = step.notification_channels.copy()

        # Add on-call targets
        for schedule_id in step.on_call_schedules:
            if schedule_id in self.schedules:
                on_call_person = self.get_current_on_call(schedule_id)
                if on_call_person:
                    # This would map to specific notification channels for the person
                    targets.extend(self._get_person_notification_channels(on_call_person))

        return list(set(targets))  # Remove duplicates

    def _get_person_notification_channels(self, person: str) -> List[str]:
        """Get notification channels for a person (placeholder)"""
        # This would integrate with your user management system
        # to get preferred notification channels for each person
        return [f"{person}_email", f"{person}_slack"]

    async def _schedule_next_step(self, escalation: EscalationInstance, policy: EscalationPolicy, alert: Alert):
        """Schedule next escalation step"""
        if escalation.current_step + 1 >= len(policy.steps):
            logger.warning(f"Escalation {escalation.id} reached final step")
            return

        current_step = policy.steps[escalation.current_step]
        delay_seconds = current_step.delay_minutes * 60

        # Schedule next step
        asyncio.get_event_loop().call_later(
            delay_seconds,
            lambda: asyncio.create_task(self._escalate_to_next_step(escalation.id, alert))
        )

    async def _escalate_to_next_step(self, escalation_id: str, alert: Alert):
        """Escalate to next step"""
        if escalation_id not in self.active_escalations:
            return

        escalation = self.active_escalations[escalation_id]

        # Check if alert was acknowledged or resolved
        if self.is_acknowledged(alert.id) or alert.status == AlertStatus.RESOLVED:
            await self.stop_escalation(escalation_id, "Alert acknowledged or resolved")
            return

        # Check if policy still exists
        if escalation.policy_id not in self.policies:
            await self.stop_escalation(escalation_id, "Policy no longer exists")
            return

        policy = self.policies[escalation.policy_id]
        escalation.current_step += 1

        logger.info(f"Escalating {escalation_id} to step {escalation.current_step}")

        await self._execute_escalation_step(escalation, policy, alert)

    def _check_step_conditions(self, conditions: Dict[str, Any], alert: Alert) -> bool:
        """Check if escalation step conditions are met"""
        # Time-based conditions
        if 'time_range' in conditions:
            current_time = datetime.now().time()
            start_time = datetime.strptime(conditions['time_range']['start'], '%H:%M').time()
            end_time = datetime.strptime(conditions['time_range']['end'], '%H:%M').time()

            if not (start_time <= current_time <= end_time):
                return False

        # Day-based conditions
        if 'days' in conditions:
            current_day = datetime.now().strftime('%A').lower()
            if current_day not in [day.lower() for day in conditions['days']]:
                return False

        # Alert age condition
        if 'min_alert_age_minutes' in conditions:
            alert_age = (datetime.now() - alert.started_at).total_seconds() / 60
            if alert_age < conditions['min_alert_age_minutes']:
                return False

        return True

    def acknowledge_alert(self, alert_id: str, user_id: str):
        """Acknowledge an alert"""
        self.acknowledgments[alert_id].append(user_id)
        logger.info(f"Alert {alert_id} acknowledged by {user_id}")

        # Stop escalation if active
        for escalation in self.active_escalations.values():
            if escalation.alert_id == alert_id:
                escalation.acknowledgments.append(user_id)
                asyncio.create_task(self.stop_escalation(escalation.id, f"Acknowledged by {user_id}"))

    def is_acknowledged(self, alert_id: str) -> bool:
        """Check if alert is acknowledged"""
        return len(self.acknowledgments.get(alert_id, [])) > 0

    def get_current_on_call(self, schedule_id: str) -> Optional[str]:
        """Get current on-call person for schedule"""
        if schedule_id not in self.schedules:
            return None

        schedule = self.schedules[schedule_id]

        # Simple rotation logic (can be enhanced)
        if not schedule.rotation:
            return None

        # Check if rotation is needed
        now = datetime.now()
        if schedule.last_rotation:
            if schedule.schedule_type == "daily":
                next_rotation = schedule.last_rotation + timedelta(days=1)
            elif schedule.schedule_type == "weekly":
                next_rotation = schedule.last_rotation + timedelta(weeks=1)
            else:  # monthly
                next_rotation = schedule.last_rotation + timedelta(days=30)

            if now >= next_rotation:
                schedule.current_index = (schedule.current_index + 1) % len(schedule.rotation)
                schedule.last_rotation = now
        else:
            schedule.last_rotation = now

        return schedule.rotation[schedule.current_index]

    def get_escalation_stats(self) -> Dict[str, Any]:
        """Get escalation statistics"""
        recent_escalations = [
            esc for esc in self.escalation_history
            if esc.started_at > datetime.now() - timedelta(hours=24)
        ]

        return {
            'policies': {
                'total': len(self.policies),
                'enabled': len([p for p in self.policies.values() if p.enabled])
            },
            'schedules': {
                'total': len(self.schedules)
            },
            'active_escalations': len(self.active_escalations),
            'recent_escalations': {
                'total': len(recent_escalations),
                'by_policy': defaultdict(int)
            }
        }


# Pre-defined escalation policies
def get_default_escalation_policies() -> List[EscalationPolicy]:
    """Get default escalation policies"""
    return [
        EscalationPolicy(
            id="critical_alerts",
            name="Critical Alerts Escalation",
            description="Immediate escalation for critical alerts",
            filters={'severity': ['critical']},
            steps=[
                EscalationStep(
                    level=EscalationLevel.LEVEL_1,
                    delay_minutes=0,  # Immediate
                    notification_channels=['sre_slack', 'sre_pagerduty'],
                    on_call_schedules=['sre_primary']
                ),
                EscalationStep(
                    level=EscalationLevel.LEVEL_2,
                    delay_minutes=15,
                    notification_channels=['engineering_manager_slack', 'engineering_manager_email'],
                    on_call_schedules=['engineering_manager']
                ),
                EscalationStep(
                    level=EscalationLevel.LEVEL_3,
                    delay_minutes=30,
                    notification_channels=['cto_email', 'executive_slack']
                )
            ]
        ),

        EscalationPolicy(
            id="warning_alerts",
            name="Warning Alerts Escalation",
            description="Standard escalation for warning alerts",
            filters={'severity': ['warning']},
            steps=[
                EscalationStep(
                    level=EscalationLevel.LEVEL_1,
                    delay_minutes=5,
                    notification_channels=['dev_team_slack'],
                    on_call_schedules=['dev_on_call']
                ),
                EscalationStep(
                    level=EscalationLevel.LEVEL_2,
                    delay_minutes=30,
                    notification_channels=['senior_engineer_slack'],
                    on_call_schedules=['senior_on_call']
                )
            ]
        ),

        EscalationPolicy(
            id="business_hours_only",
            name="Business Hours Escalation",
            description="Escalation only during business hours",
            filters={'labels': {'priority': 'business_hours'}},
            steps=[
                EscalationStep(
                    level=EscalationLevel.LEVEL_1,
                    delay_minutes=0,
                    notification_channels=['dev_team_email'],
                    conditions={
                        'time_range': {'start': '09:00', 'end': '17:00'},
                        'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                    }
                )
            ]
        )
    ]


# Default on-call schedules
def get_default_schedules() -> List[OnCallSchedule]:
    """Get default on-call schedules"""
    return [
        OnCallSchedule(
            id="sre_primary",
            name="SRE Primary On-Call",
            timezone="UTC",
            schedule_type="weekly",
            rotation=["alice", "bob", "charlie"]
        ),
        OnCallSchedule(
            id="dev_on_call",
            name="Development Team On-Call",
            timezone="UTC",
            schedule_type="daily",
            rotation=["dev1", "dev2", "dev3", "dev4"]
        ),
        OnCallSchedule(
            id="engineering_manager",
            name="Engineering Manager",
            timezone="UTC",
            schedule_type="weekly",
            rotation=["eng_manager_1", "eng_manager_2"]
        )
    ]


# Global escalation manager
escalation_manager = EscalationManager(notification_manager)

# Initialize with default policies and schedules
for policy in get_default_escalation_policies():
    escalation_manager.add_policy(policy)

for schedule in get_default_schedules():
    escalation_manager.add_schedule(schedule)

# Export key components
__all__ = [
    'EscalationPolicy',
    'EscalationStep',
    'EscalationInstance',
    'OnCallSchedule',
    'EscalationManager',
    'EscalationLevel',
    'escalation_manager',
    'get_default_escalation_policies',
    'get_default_schedules'
]