"""
Threat Detection System
Real-time threat detection and response system
"""

import re
import ipaddress
import geoip2.database
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging
from collections import defaultdict, deque
import hashlib
import json


logger = logging.getLogger(__name__)


class ThreatType(Enum):
    """Types of security threats"""
    BRUTE_FORCE = "brute_force"
    DDoS = "ddos"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    MALICIOUS_IP = "malicious_ip"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    CREDENTIAL_STUFFING = "credential_stuffing"
    BOT_ACTIVITY = "bot_activity"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class ThreatLevel(Enum):
    """Threat severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ThreatEvent:
    """Threat event data class"""
    id: str
    threat_type: ThreatType
    threat_level: ThreatLevel
    source_ip: str
    target: str
    timestamp: datetime
    description: str
    evidence: Dict[str, Any]
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    blocked: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['threat_type'] = self.threat_type.value
        data['threat_level'] = self.threat_level.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


class IPIntelligence:
    """IP address intelligence and reputation checking"""
    
    def __init__(self, geoip_db_path: Optional[str] = None):
        self.malicious_ips: Set[str] = set()
        self.whitelist_ips: Set[str] = set()
        self.geo_reader = None
        
        if geoip_db_path:
            try:
                self.geo_reader = geoip2.database.Reader(geoip_db_path)
            except Exception as e:
                logger.error(f"Failed to load GeoIP database: {e}")
    
    def add_malicious_ip(self, ip: str):
        """Add IP to malicious list"""
        self.malicious_ips.add(ip)
    
    def add_whitelist_ip(self, ip: str):
        """Add IP to whitelist"""
        self.whitelist_ips.add(ip)
    
    def is_malicious(self, ip: str) -> bool:
        """Check if IP is known malicious"""
        return ip in self.malicious_ips
    
    def is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted"""
        return ip in self.whitelist_ips
    
    def get_geo_info(self, ip: str) -> Dict[str, Any]:
        """Get geographical information for IP"""
        if not self.geo_reader:
            return {}
        
        try:
            response = self.geo_reader.city(ip)
            return {
                'country': response.country.name,
                'country_code': response.country.iso_code,
                'city': response.city.name,
                'latitude': float(response.location.latitude) if response.location.latitude else None,
                'longitude': float(response.location.longitude) if response.location.longitude else None,
                'timezone': str(response.location.time_zone) if response.location.time_zone else None
            }
        except Exception as e:
            logger.error(f"GeoIP lookup failed for {ip}: {e}")
            return {}
    
    def is_tor_exit_node(self, ip: str) -> bool:
        """Check if IP is a known Tor exit node"""
        # This would typically query a Tor exit node list API
        # For now, return False as placeholder
        return False
    
    def check_reputation(self, ip: str) -> Dict[str, Any]:
        """Check IP reputation from multiple sources"""
        reputation = {
            'malicious': self.is_malicious(ip),
            'whitelisted': self.is_whitelisted(ip),
            'tor_exit_node': self.is_tor_exit_node(ip),
            'geo_info': self.get_geo_info(ip)
        }
        
        return reputation


class BruteForceDetector:
    """Brute force attack detection"""
    
    def __init__(self, 
                 max_attempts: int = 5,
                 time_window: int = 300,  # 5 minutes
                 lockout_duration: int = 3600):  # 1 hour
        self.max_attempts = max_attempts
        self.time_window = time_window
        self.lockout_duration = lockout_duration
        self.failed_attempts: Dict[str, deque] = defaultdict(deque)
        self.locked_ips: Dict[str, datetime] = {}
    
    def record_failed_attempt(self, ip: str, username: str = None) -> bool:
        """Record failed login attempt and check for brute force"""
        now = datetime.utcnow()
        key = f"{ip}:{username}" if username else ip
        
        # Clean old attempts
        cutoff = now - timedelta(seconds=self.time_window)
        while self.failed_attempts[key] and self.failed_attempts[key][0] < cutoff:
            self.failed_attempts[key].popleft()
        
        # Add current attempt
        self.failed_attempts[key].append(now)
        
        # Check if threshold exceeded
        if len(self.failed_attempts[key]) >= self.max_attempts:
            self.locked_ips[ip] = now + timedelta(seconds=self.lockout_duration)
            logger.warning(f"Brute force detected from {ip} for user {username}")
            return True
        
        return False
    
    def is_locked(self, ip: str) -> bool:
        """Check if IP is currently locked"""
        if ip not in self.locked_ips:
            return False
        
        if datetime.utcnow() > self.locked_ips[ip]:
            del self.locked_ips[ip]
            return False
        
        return True
    
    def unlock_ip(self, ip: str):
        """Manually unlock IP"""
        if ip in self.locked_ips:
            del self.locked_ips[ip]


class DDoSDetector:
    """DDoS attack detection"""
    
    def __init__(self,
                 request_threshold: int = 100,
                 time_window: int = 60,  # 1 minute
                 unique_ip_threshold: int = 50):
        self.request_threshold = request_threshold
        self.time_window = time_window
        self.unique_ip_threshold = unique_ip_threshold
        self.request_counts: Dict[str, deque] = defaultdict(deque)
        self.global_requests: deque = deque()
    
    def record_request(self, ip: str) -> bool:
        """Record request and check for DDoS"""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.time_window)
        
        # Clean old requests
        while self.global_requests and self.global_requests[0][0] < cutoff:
            self.global_requests.popleft()
        
        while self.request_counts[ip] and self.request_counts[ip][0] < cutoff:
            self.request_counts[ip].popleft()
        
        # Add current request
        self.global_requests.append((now, ip))
        self.request_counts[ip].append(now)
        
        # Check for DDoS patterns
        total_requests = len(self.global_requests)
        unique_ips = len(set(req[1] for req in self.global_requests))
        
        # Single IP flooding
        if len(self.request_counts[ip]) > self.request_threshold:
            return True
        
        # Distributed attack
        if total_requests > self.request_threshold * 2 and unique_ips > self.unique_ip_threshold:
            return True
        
        return False


class PayloadAnalyzer:
    """Analyze request payloads for malicious content"""
    
    def __init__(self):
        # SQL injection patterns
        self.sql_patterns = [
            r"('|(\\-)+|;|\||\*|%|\?|=)",
            r"(union|select|insert|delete|update|drop|create|alter|exec|execute)",
            r"(script|javascript|vbscript|onload|onerror|onclick)"
        ]
        
        # XSS patterns
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>"
        ]
        
        # Path traversal patterns
        self.traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c"
        ]
    
    def analyze_payload(self, payload: str) -> Dict[str, Any]:
        """Analyze payload for malicious patterns"""
        results = {
            'sql_injection': False,
            'xss': False,
            'path_traversal': False,
            'suspicious_patterns': []
        }
        
        payload_lower = payload.lower()
        
        # Check SQL injection
        for pattern in self.sql_patterns:
            if re.search(pattern, payload_lower, re.IGNORECASE):
                results['sql_injection'] = True
                results['suspicious_patterns'].append(f"SQL: {pattern}")
        
        # Check XSS
        for pattern in self.xss_patterns:
            if re.search(pattern, payload_lower, re.IGNORECASE):
                results['xss'] = True
                results['suspicious_patterns'].append(f"XSS: {pattern}")
        
        # Check path traversal
        for pattern in self.traversal_patterns:
            if re.search(pattern, payload_lower, re.IGNORECASE):
                results['path_traversal'] = True
                results['suspicious_patterns'].append(f"Traversal: {pattern}")
        
        return results


class ThreatDetector:
    """Main threat detection system"""
    
    def __init__(self, geoip_db_path: Optional[str] = None):
        self.ip_intelligence = IPIntelligence(geoip_db_path)
        self.brute_force_detector = BruteForceDetector()
        self.ddos_detector = DDoSDetector()
        self.payload_analyzer = PayloadAnalyzer()
        self.threat_events: List[ThreatEvent] = []
        self.blocked_ips: Set[str] = set()
    
    def analyze_request(self, 
                      ip: str,
                      user_agent: str,
                      request_path: str,
                      request_payload: str = "",
                      user_id: str = None,
                      session_id: str = None) -> List[ThreatEvent]:
        """Analyze incoming request for threats"""
        threats = []
        
        # Check IP reputation
        reputation = self.ip_intelligence.check_reputation(ip)
        if reputation['malicious']:
            threat = self._create_threat_event(
                ThreatType.MALICIOUS_IP,
                ThreatLevel.HIGH,
                ip,
                request_path,
                "Request from known malicious IP",
                {'reputation': reputation},
                user_id,
                session_id
            )
            threats.append(threat)
        
        # Check for DDoS
        if self.ddos_detector.record_request(ip):
            threat = self._create_threat_event(
                ThreatType.DDoS,
                ThreatLevel.CRITICAL,
                ip,
                request_path,
                "DDoS attack pattern detected",
                {'request_rate': 'high'},
                user_id,
                session_id
            )
            threats.append(threat)
        
        # Analyze payload for malicious content
        if request_payload:
            payload_analysis = self.payload_analyzer.analyze_payload(request_payload)
            
            if payload_analysis['sql_injection']:
                threat = self._create_threat_event(
                    ThreatType.SQL_INJECTION,
                    ThreatLevel.CRITICAL,
                    ip,
                    request_path,
                    "SQL injection attempt detected",
                    payload_analysis,
                    user_id,
                    session_id
                )
                threats.append(threat)
            
            if payload_analysis['xss']:
                threat = self._create_threat_event(
                    ThreatType.XSS,
                    ThreatLevel.HIGH,
                    ip,
                    request_path,
                    "Cross-site scripting attempt detected",
                    payload_analysis,
                    user_id,
                    session_id
                )
                threats.append(threat)
        
        # Check user agent for bot patterns
        if self._is_suspicious_user_agent(user_agent):
            threat = self._create_threat_event(
                ThreatType.BOT_ACTIVITY,
                ThreatLevel.MEDIUM,
                ip,
                request_path,
                "Suspicious bot activity detected",
                {'user_agent': user_agent},
                user_id,
                session_id
            )
            threats.append(threat)
        
        return threats
    
    def record_failed_login(self, ip: str, username: str = None) -> Optional[ThreatEvent]:
        """Record failed login attempt"""
        if self.brute_force_detector.record_failed_attempt(ip, username):
            threat = self._create_threat_event(
                ThreatType.BRUTE_FORCE,
                ThreatLevel.HIGH,
                ip,
                "login",
                "Brute force attack detected",
                {'username': username, 'locked': True}
            )
            return threat
        
        return None
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        return ip in self.blocked_ips or self.brute_force_detector.is_locked(ip)
    
    def block_ip(self, ip: str, duration: int = 3600):
        """Block IP address"""
        self.blocked_ips.add(ip)
        logger.warning(f"IP {ip} has been blocked")
    
    def unblock_ip(self, ip: str):
        """Unblock IP address"""
        self.blocked_ips.discard(ip)
        self.brute_force_detector.unlock_ip(ip)
        logger.info(f"IP {ip} has been unblocked")
    
    def get_threat_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get threat summary for specified time period"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_threats = [t for t in self.threat_events if t.timestamp > cutoff]
        
        summary = {
            'total_threats': len(recent_threats),
            'by_type': defaultdict(int),
            'by_level': defaultdict(int),
            'top_source_ips': defaultdict(int),
            'blocked_ips': len(self.blocked_ips)
        }
        
        for threat in recent_threats:
            summary['by_type'][threat.threat_type.value] += 1
            summary['by_level'][threat.threat_level.value] += 1
            summary['top_source_ips'][threat.source_ip] += 1
        
        # Convert to regular dicts and sort
        summary['by_type'] = dict(summary['by_type'])
        summary['by_level'] = dict(summary['by_level'])
        summary['top_source_ips'] = dict(sorted(
            summary['top_source_ips'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10])
        
        return summary
    
    def _create_threat_event(self,
                           threat_type: ThreatType,
                           threat_level: ThreatLevel,
                           source_ip: str,
                           target: str,
                           description: str,
                           evidence: Dict[str, Any],
                           user_id: str = None,
                           session_id: str = None) -> ThreatEvent:
        """Create and store threat event"""
        event_id = hashlib.md5(
            f"{threat_type.value}{source_ip}{target}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]
        
        threat = ThreatEvent(
            id=event_id,
            threat_type=threat_type,
            threat_level=threat_level,
            source_ip=source_ip,
            target=target,
            timestamp=datetime.utcnow(),
            description=description,
            evidence=evidence,
            user_id=user_id,
            session_id=session_id
        )
        
        self.threat_events.append(threat)
        logger.warning(f"Threat detected: {threat.id} - {threat.description}")
        
        return threat
    
    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent is suspicious"""
        suspicious_patterns = [
            r"bot",
            r"crawler",
            r"spider",
            r"scraper",
            r"curl",
            r"wget",
            r"python-requests",
            r"^$"  # Empty user agent
        ]
        
        user_agent_lower = user_agent.lower()
        
        for pattern in suspicious_patterns:
            if re.search(pattern, user_agent_lower):
                return True
        
        return False


class ThreatResponse:
    """Automated threat response system"""
    
    def __init__(self, threat_detector: ThreatDetector):
        self.threat_detector = threat_detector
        self.auto_block_enabled = True
        self.notification_callbacks = []
    
    def add_notification_callback(self, callback):
        """Add callback for threat notifications"""
        self.notification_callbacks.append(callback)
    
    def respond_to_threat(self, threat: ThreatEvent) -> Dict[str, Any]:
        """Respond to detected threat"""
        actions_taken = []
        
        # Auto-block for critical threats
        if (self.auto_block_enabled and 
            threat.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]):
            
            if threat.threat_type in [ThreatType.DDoS, ThreatType.BRUTE_FORCE, 
                                     ThreatType.SQL_INJECTION, ThreatType.MALICIOUS_IP]:
                self.threat_detector.block_ip(threat.source_ip)
                actions_taken.append(f"Blocked IP: {threat.source_ip}")
        
        # Send notifications
        for callback in self.notification_callbacks:
            try:
                callback(threat)
                actions_taken.append("Notification sent")
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")
        
        # Log response
        logger.info(f"Threat response for {threat.id}: {', '.join(actions_taken)}")
        
        return {
            'threat_id': threat.id,
            'actions_taken': actions_taken,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def enable_auto_block(self):
        """Enable automatic IP blocking"""
        self.auto_block_enabled = True
    
    def disable_auto_block(self):
        """Disable automatic IP blocking"""
        self.auto_block_enabled = False