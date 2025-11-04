"""
Deprecation Management System
Handles deprecation warnings, sunset schedules, and version retirement
"""

import re
import json
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging
from packaging import version
import warnings

logger = logging.getLogger(__name__)


class DeprecationLevel(Enum):
    """Levels of deprecation"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SUNSET = "sunset"


class DeprecationScope(Enum):
    """Scope of deprecation"""
    VERSION = "version"
    ENDPOINT = "endpoint"
    PARAMETER = "parameter"
    RESPONSE_FIELD = "response_field"
    FEATURE = "feature"


@dataclass
class DeprecationNotice:
    """Represents a deprecation notice"""
    notice_id: str
    scope: DeprecationScope
    target: str  # version, endpoint path, parameter name, etc.
    level: DeprecationLevel
    deprecated_in: str  # version when deprecation was announced
    removed_in: Optional[str]  # version when feature will be removed
    sunset_date: Optional[datetime]  # date when feature will be sunset
    message: str
    replacement: Optional[str]  # what to use instead
    migration_guide_url: Optional[str]
    created_at: datetime
    last_warned_at: Optional[datetime]
    warning_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['scope'] = self.scope.value
        data['level'] = self.level.value
        data['created_at'] = self.created_at.isoformat()
        if self.sunset_date:
            data['sunset_date'] = self.sunset_date.isoformat()
        if self.last_warned_at:
            data['last_warned_at'] = self.last_warned_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeprecationNotice':
        data['scope'] = DeprecationScope(data['scope'])
        data['level'] = DeprecationLevel(data['level'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('sunset_date'):
            data['sunset_date'] = datetime.fromisoformat(data['sunset_date'])
        if data.get('last_warned_at'):
            data['last_warned_at'] = datetime.fromisoformat(data['last_warned_at'])
        return cls(**data)
    
    def is_sunset(self) -> bool:
        """Check if this deprecation has reached sunset"""
        if self.level == DeprecationLevel.SUNSET:
            return True
        
        if self.sunset_date:
            return datetime.utcnow() > self.sunset_date
        
        return False
    
    def days_until_sunset(self) -> Optional[int]:
        """Get days until sunset"""
        if not self.sunset_date:
            return None
        
        delta = self.sunset_date - datetime.utcnow()
        return delta.days if delta.days > 0 else 0


class DeprecationFormatter:
    """Formats deprecation messages for different contexts"""
    
    @staticmethod
    def format_http_header(notice: DeprecationNotice) -> str:
        """Format deprecation notice for HTTP header"""
        message = f"{notice.target} is deprecated"
        
        if notice.removed_in:
            message += f" and will be removed in version {notice.removed_in}"
        elif notice.sunset_date:
            message += f" and will be sunset on {notice.sunset_date.strftime('%Y-%m-%d')}"
        
        if notice.replacement:
            message += f". Use {notice.replacement} instead"
        
        return message
    
    @staticmethod
    def format_log_warning(notice: DeprecationNotice, context: Dict[str, Any] = None) -> str:
        """Format deprecation notice for logging"""
        context = context or {}
        
        message = f"DEPRECATION WARNING: {notice.target} ({notice.scope.value}) is deprecated"
        
        if notice.removed_in:
            message += f" since version {notice.deprecated_in} and will be removed in {notice.removed_in}"
        
        if notice.sunset_date:
            days_left = notice.days_until_sunset()
            if days_left is not None:
                message += f". Sunset in {days_left} days ({notice.sunset_date.strftime('%Y-%m-%d')})"
        
        if notice.replacement:
            message += f". Migration: Use {notice.replacement}"
        
        if context:
            message += f". Context: {json.dumps(context)}"
        
        return message
    
    @staticmethod
    def format_api_response(notice: DeprecationNotice) -> Dict[str, Any]:
        """Format deprecation notice for API response"""
        return {
            "type": "deprecation_warning",
            "level": notice.level.value,
            "message": notice.message,
            "deprecated_feature": notice.target,
            "deprecated_in_version": notice.deprecated_in,
            "removed_in_version": notice.removed_in,
            "sunset_date": notice.sunset_date.isoformat() if notice.sunset_date else None,
            "replacement": notice.replacement,
            "migration_guide": notice.migration_guide_url,
            "days_until_sunset": notice.days_until_sunset()
        }


class DeprecationTracker:
    """Tracks deprecation usage and generates statistics"""
    
    def __init__(self):
        self.usage_stats: Dict[str, Dict[str, Any]] = {}
        self.client_warnings: Dict[str, Set[str]] = {}  # client_id -> set of notice_ids
    
    def record_usage(self, notice_id: str, client_id: str = None, 
                    endpoint: str = None, user_agent: str = None):
        """Record usage of deprecated feature"""
        if notice_id not in self.usage_stats:
            self.usage_stats[notice_id] = {
                'total_usage': 0,
                'unique_clients': set(),
                'endpoints': set(),
                'user_agents': set(),
                'first_seen': datetime.utcnow(),
                'last_seen': datetime.utcnow()
            }
        
        stats = self.usage_stats[notice_id]
        stats['total_usage'] += 1
        stats['last_seen'] = datetime.utcnow()
        
        if client_id:
            stats['unique_clients'].add(client_id)
            
            # Track warnings per client
            if client_id not in self.client_warnings:
                self.client_warnings[client_id] = set()
            self.client_warnings[client_id].add(notice_id)
        
        if endpoint:
            stats['endpoints'].add(endpoint)
        
        if user_agent:
            stats['user_agents'].add(user_agent)
    
    def get_usage_summary(self, notice_id: str) -> Optional[Dict[str, Any]]:
        """Get usage summary for a deprecation notice"""
        if notice_id not in self.usage_stats:
            return None
        
        stats = self.usage_stats[notice_id]
        
        return {
            'notice_id': notice_id,
            'total_usage': stats['total_usage'],
            'unique_clients': len(stats['unique_clients']),
            'affected_endpoints': len(stats['endpoints']),
            'user_agents': len(stats['user_agents']),
            'first_seen': stats['first_seen'].isoformat(),
            'last_seen': stats['last_seen'].isoformat(),
            'usage_trend': self._calculate_usage_trend(notice_id)
        }
    
    def _calculate_usage_trend(self, notice_id: str) -> str:
        """Calculate usage trend (increasing/decreasing/stable)"""
        # Simplified implementation - in practice, you'd analyze historical data
        return "stable"
    
    def get_client_deprecation_summary(self, client_id: str) -> Dict[str, Any]:
        """Get deprecation summary for a specific client"""
        if client_id not in self.client_warnings:
            return {
                'client_id': client_id,
                'deprecation_warnings': 0,
                'notices': []
            }
        
        notice_ids = self.client_warnings[client_id]
        
        return {
            'client_id': client_id,
            'deprecation_warnings': len(notice_ids),
            'notices': list(notice_ids)
        }


class SunsetScheduler:
    """Manages sunset schedules for deprecated features"""
    
    def __init__(self):
        self.sunset_callbacks: Dict[str, List[Callable]] = {}
        self.grace_periods = {
            DeprecationScope.VERSION: timedelta(days=365),  # 1 year for versions
            DeprecationScope.ENDPOINT: timedelta(days=180),  # 6 months for endpoints
            DeprecationScope.PARAMETER: timedelta(days=90),  # 3 months for parameters
            DeprecationScope.RESPONSE_FIELD: timedelta(days=90),  # 3 months for fields
            DeprecationScope.FEATURE: timedelta(days=180),  # 6 months for features
        }
    
    def register_sunset_callback(self, notice_id: str, callback: Callable):
        """Register callback to be called when feature is sunset"""
        if notice_id not in self.sunset_callbacks:
            self.sunset_callbacks[notice_id] = []
        
        self.sunset_callbacks[notice_id].append(callback)
    
    def calculate_sunset_date(self, notice: DeprecationNotice, 
                            custom_grace_period: timedelta = None) -> datetime:
        """Calculate sunset date for a deprecation notice"""
        grace_period = custom_grace_period or self.grace_periods.get(
            notice.scope, 
            timedelta(days=180)  # default 6 months
        )
        
        return notice.created_at + grace_period
    
    def get_sunset_schedule(self, days_ahead: int = 90) -> List[Dict[str, Any]]:
        """Get features scheduled for sunset within specified days"""
        cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
        sunset_schedule = []
        
        # This would typically query your deprecation storage
        # For now, return empty list as placeholder
        return sunset_schedule
    
    def execute_sunset_callbacks(self, notice_id: str):
        """Execute registered callbacks for sunset feature"""
        if notice_id in self.sunset_callbacks:
            for callback in self.sunset_callbacks[notice_id]:
                try:
                    callback(notice_id)
                except Exception as e:
                    logger.error(f"Sunset callback error for {notice_id}: {e}")


class DeprecationManager:
    """Main deprecation management system"""
    
    def __init__(self):
        self.notices: Dict[str, DeprecationNotice] = {}
        self.tracker = DeprecationTracker()
        self.scheduler = SunsetScheduler()
        self.formatter = DeprecationFormatter()
        self._load_notices()
    
    def add_deprecation(self, 
                       scope: DeprecationScope,
                       target: str,
                       deprecated_in: str,
                       message: str,
                       level: DeprecationLevel = DeprecationLevel.WARNING,
                       removed_in: str = None,
                       sunset_date: datetime = None,
                       replacement: str = None,
                       migration_guide_url: str = None) -> str:
        """Add a new deprecation notice"""
        
        notice_id = f"{scope.value}_{target}_{deprecated_in}".replace("/", "_").replace(".", "_")
        
        # Calculate sunset date if not provided
        if not sunset_date and not removed_in:
            notice = DeprecationNotice(
                notice_id=notice_id,
                scope=scope,
                target=target,
                level=level,
                deprecated_in=deprecated_in,
                removed_in=removed_in,
                sunset_date=None,
                message=message,
                replacement=replacement,
                migration_guide_url=migration_guide_url,
                created_at=datetime.utcnow(),
                last_warned_at=None
            )
            sunset_date = self.scheduler.calculate_sunset_date(notice)
        
        notice = DeprecationNotice(
            notice_id=notice_id,
            scope=scope,
            target=target,
            level=level,
            deprecated_in=deprecated_in,
            removed_in=removed_in,
            sunset_date=sunset_date,
            message=message,
            replacement=replacement,
            migration_guide_url=migration_guide_url,
            created_at=datetime.utcnow(),
            last_warned_at=None
        )
        
        self.notices[notice_id] = notice
        self._save_notices()
        
        logger.info(f"Added deprecation notice: {notice_id}")
        return notice_id
    
    def get_deprecation_warnings(self, 
                               api_version: str = None,
                               endpoint: str = None,
                               parameters: List[str] = None) -> List[DeprecationNotice]:
        """Get applicable deprecation warnings"""
        warnings = []
        
        for notice in self.notices.values():
            if notice.is_sunset():
                continue
            
            if self._is_applicable(notice, api_version, endpoint, parameters):
                warnings.append(notice)
        
        return warnings
    
    def record_deprecation_usage(self, notice_id: str, client_id: str = None,
                               endpoint: str = None, user_agent: str = None):
        """Record usage of deprecated feature"""
        if notice_id in self.notices:
            notice = self.notices[notice_id]
            notice.warning_count += 1
            notice.last_warned_at = datetime.utcnow()
            
            self.tracker.record_usage(notice_id, client_id, endpoint, user_agent)
            
            # Log warning based on level
            context = {
                'client_id': client_id,
                'endpoint': endpoint,
                'user_agent': user_agent
            }
            
            log_message = self.formatter.format_log_warning(notice, context)
            
            if notice.level == DeprecationLevel.CRITICAL:
                logger.critical(log_message)
            elif notice.level == DeprecationLevel.WARNING:
                logger.warning(log_message)
            else:
                logger.info(log_message)
    
    def get_deprecation_headers(self, notices: List[DeprecationNotice]) -> Dict[str, str]:
        """Generate HTTP headers for deprecation warnings"""
        headers = {}
        
        if not notices:
            return headers
        
        # Add deprecation header
        if len(notices) == 1:
            headers['Deprecation'] = self.formatter.format_http_header(notices[0])
        else:
            headers['Deprecation'] = f"Multiple features deprecated. See response body for details."
        
        # Add sunset header for most critical
        critical_notices = [n for n in notices if n.level == DeprecationLevel.CRITICAL]
        if critical_notices:
            notice = min(critical_notices, key=lambda n: n.sunset_date or datetime.max)
            if notice.sunset_date:
                headers['Sunset'] = notice.sunset_date.strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        return headers
    
    def get_deprecation_response_data(self, notices: List[DeprecationNotice]) -> List[Dict[str, Any]]:
        """Generate deprecation data for API response"""
        return [self.formatter.format_api_response(notice) for notice in notices]
    
    def check_version_deprecation(self, api_version: str) -> Optional[DeprecationNotice]:
        """Check if a specific API version is deprecated"""
        for notice in self.notices.values():
            if (notice.scope == DeprecationScope.VERSION and 
                notice.target == api_version and 
                not notice.is_sunset()):
                return notice
        return None
    
    def check_endpoint_deprecation(self, endpoint_path: str) -> List[DeprecationNotice]:
        """Check if an endpoint is deprecated"""
        warnings = []
        
        for notice in self.notices.values():
            if (notice.scope == DeprecationScope.ENDPOINT and 
                not notice.is_sunset()):
                
                # Check for exact match or pattern match
                if notice.target == endpoint_path or self._path_matches_pattern(endpoint_path, notice.target):
                    warnings.append(notice)
        
        return warnings
    
    def cleanup_sunset_features(self) -> List[str]:
        """Remove features that have reached sunset"""
        sunset_notices = []
        
        for notice_id, notice in list(self.notices.items()):
            if notice.is_sunset():
                sunset_notices.append(notice_id)
                
                # Execute sunset callbacks
                self.scheduler.execute_sunset_callbacks(notice_id)
                
                # Remove the notice
                del self.notices[notice_id]
        
        if sunset_notices:
            self._save_notices()
            logger.info(f"Cleaned up {len(sunset_notices)} sunset features")
        
        return sunset_notices
    
    def get_deprecation_report(self) -> Dict[str, Any]:
        """Generate comprehensive deprecation report"""
        now = datetime.utcnow()
        
        active_notices = [n for n in self.notices.values() if not n.is_sunset()]
        sunset_soon = [n for n in active_notices if n.days_until_sunset() and n.days_until_sunset() <= 30]
        
        # Group by scope
        by_scope = {}
        for notice in active_notices:
            scope = notice.scope.value
            if scope not in by_scope:
                by_scope[scope] = []
            by_scope[scope].append(notice.to_dict())
        
        # Usage statistics
        usage_summary = {}
        for notice_id in self.notices.keys():
            summary = self.tracker.get_usage_summary(notice_id)
            if summary:
                usage_summary[notice_id] = summary
        
        return {
            'generated_at': now.isoformat(),
            'summary': {
                'total_deprecations': len(active_notices),
                'critical_deprecations': len([n for n in active_notices if n.level == DeprecationLevel.CRITICAL]),
                'sunset_soon': len(sunset_soon),
                'total_warnings_issued': sum(n.warning_count for n in active_notices)
            },
            'by_scope': by_scope,
            'sunset_schedule': [n.to_dict() for n in sunset_soon],
            'usage_statistics': usage_summary
        }
    
    def _is_applicable(self, notice: DeprecationNotice, api_version: str = None,
                      endpoint: str = None, parameters: List[str] = None) -> bool:
        """Check if deprecation notice applies to current request"""
        if notice.scope == DeprecationScope.VERSION:
            return api_version == notice.target
        
        elif notice.scope == DeprecationScope.ENDPOINT:
            if endpoint:
                return endpoint == notice.target or self._path_matches_pattern(endpoint, notice.target)
        
        elif notice.scope == DeprecationScope.PARAMETER:
            if parameters:
                return notice.target in parameters
        
        return False
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches deprecation pattern"""
        # Simple pattern matching - could be enhanced
        if "*" in pattern:
            regex_pattern = pattern.replace("*", ".*")
            return bool(re.match(regex_pattern, path))
        
        return path == pattern
    
    def _load_notices(self):
        """Load deprecation notices from storage"""
        # Placeholder - would load from database or file
        pass
    
    def _save_notices(self):
        """Save deprecation notices to storage"""
        # Placeholder - would save to database or file
        pass