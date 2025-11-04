"""
Session Manager
Handles secure session management with Redis backend
"""

import redis
import json
import secrets
import hashlib
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from cryptography.fernet import Fernet


logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session states"""
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    SUSPICIOUS = "suspicious"


@dataclass
class SessionInfo:
    """Session information data class"""
    session_id: str
    user_id: str
    user_email: str
    user_role: str
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    state: SessionState
    mfa_verified: bool
    permissions: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        data['expires_at'] = self.expires_at.isoformat()
        data['state'] = self.state.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionInfo':
        """Create from dictionary"""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        data['state'] = SessionState(data['state'])
        return cls(**data)


class SessionTokenGenerator:
    """Secure session token generator"""
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate cryptographically secure session ID"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_csrf_token() -> str:
        """Generate CSRF token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_session_id(session_id: str) -> str:
        """Hash session ID for storage"""
        return hashlib.sha256(session_id.encode()).hexdigest()


class SessionStore:
    """Redis-based session storage"""
    
    def __init__(self, redis_client: redis.Redis, encryption_key: bytes):
        self.redis = redis_client
        self.fernet = Fernet(encryption_key)
        self.session_prefix = "session:"
        self.user_sessions_prefix = "user_sessions:"
    
    def store_session(self, session_info: SessionInfo) -> bool:
        """Store session in Redis"""
        try:
            session_data = json.dumps(session_info.to_dict())
            encrypted_data = self.fernet.encrypt(session_data.encode()).decode()
            
            # Store session data
            session_key = f"{self.session_prefix}{session_info.session_id}"
            ttl = int((session_info.expires_at - datetime.utcnow()).total_seconds())
            
            self.redis.setex(session_key, ttl, encrypted_data)
            
            # Track user sessions
            user_sessions_key = f"{self.user_sessions_prefix}{session_info.user_id}"
            self.redis.sadd(user_sessions_key, session_info.session_id)
            self.redis.expire(user_sessions_key, ttl)
            
            logger.info(f"Session stored: {session_info.session_id} for user {session_info.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store session {session_info.session_id}: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Retrieve session from Redis"""
        try:
            session_key = f"{self.session_prefix}{session_id}"
            encrypted_data = self.redis.get(session_key)
            
            if not encrypted_data:
                return None
            
            session_data = self.fernet.decrypt(encrypted_data.encode()).decode()
            session_dict = json.loads(session_data)
            
            return SessionInfo.from_dict(session_dict)
            
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}")
            return None
    
    def update_session(self, session_info: SessionInfo) -> bool:
        """Update existing session"""
        return self.store_session(session_info)
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete session from Redis"""
        try:
            session_key = f"{self.session_prefix}{session_id}"
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            
            # Remove session data
            self.redis.delete(session_key)
            
            # Remove from user sessions set
            self.redis.srem(user_sessions_key, session_id)
            
            logger.info(f"Session deleted: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def get_user_sessions(self, user_id: str) -> List[str]:
        """Get all session IDs for a user"""
        try:
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            session_ids = self.redis.smembers(user_sessions_key)
            return [sid.decode() for sid in session_ids]
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {e}")
            return []
    
    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions (Redis TTL handles this automatically)"""
        # Redis TTL automatically removes expired keys
        # This method is for manual cleanup if needed
        cleaned = 0
        try:
            pattern = f"{self.session_prefix}*"
            for key in self.redis.scan_iter(match=pattern):
                if self.redis.ttl(key) <= 0:
                    self.redis.delete(key)
                    cleaned += 1
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
        
        return cleaned


class SessionManager:
    """Main session manager"""
    
    def __init__(self, 
                 session_store: SessionStore,
                 default_session_timeout: int = 3600,  # 1 hour
                 max_sessions_per_user: int = 5,
                 require_mfa_for_sensitive: bool = True):
        self.store = session_store
        self.default_timeout = default_session_timeout
        self.max_sessions_per_user = max_sessions_per_user
        self.require_mfa_for_sensitive = require_mfa_for_sensitive
        self.active_sessions: Dict[str, datetime] = {}  # In-memory tracking
    
    def create_session(self, 
                      user_id: str,
                      user_email: str,
                      user_role: str,
                      ip_address: str,
                      user_agent: str,
                      permissions: List[str],
                      session_timeout: Optional[int] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Optional[SessionInfo]:
        """Create new session"""
        try:
            # Check session limits
            existing_sessions = self.store.get_user_sessions(user_id)
            if len(existing_sessions) >= self.max_sessions_per_user:
                # Remove oldest session
                self._cleanup_oldest_session(user_id, existing_sessions)
            
            # Generate session
            session_id = SessionTokenGenerator.generate_session_id()
            now = datetime.utcnow()
            timeout = session_timeout or self.default_timeout
            expires_at = now + timedelta(seconds=timeout)
            
            session_info = SessionInfo(
                session_id=session_id,
                user_id=user_id,
                user_email=user_email,
                user_role=user_role,
                ip_address=ip_address,
                user_agent=user_agent,
                created_at=now,
                last_activity=now,
                expires_at=expires_at,
                state=SessionState.ACTIVE,
                mfa_verified=False,
                permissions=permissions,
                metadata=metadata or {}
            )
            
            if self.store.store_session(session_info):
                self.active_sessions[session_id] = now
                logger.info(f"Session created for user {user_id}: {session_id}")
                return session_info
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to create session for user {user_id}: {e}")
            return None
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session by ID"""
        return self.store.get_session(session_id)
    
    def validate_session(self, session_id: str, ip_address: str) -> Optional[SessionInfo]:
        """Validate session and update last activity"""
        session_info = self.store.get_session(session_id)
        
        if not session_info:
            return None
        
        now = datetime.utcnow()
        
        # Check expiration
        if now > session_info.expires_at:
            session_info.state = SessionState.EXPIRED
            self.store.update_session(session_info)
            return None
        
        # Check for suspicious activity
        if self._is_suspicious_activity(session_info, ip_address):
            session_info.state = SessionState.SUSPICIOUS
            self.store.update_session(session_info)
            logger.warning(f"Suspicious activity detected for session {session_id}")
            return None
        
        # Update last activity
        session_info.last_activity = now
        session_info.ip_address = ip_address  # Update current IP
        self.store.update_session(session_info)
        self.active_sessions[session_id] = now
        
        return session_info
    
    def extend_session(self, session_id: str, additional_seconds: int = None) -> bool:
        """Extend session expiration"""
        session_info = self.store.get_session(session_id)
        
        if not session_info or session_info.state != SessionState.ACTIVE:
            return False
        
        extension = additional_seconds or self.default_timeout
        session_info.expires_at = datetime.utcnow() + timedelta(seconds=extension)
        
        return self.store.update_session(session_info)
    
    def terminate_session(self, session_id: str) -> bool:
        """Terminate specific session"""
        session_info = self.store.get_session(session_id)
        
        if not session_info:
            return False
        
        session_info.state = SessionState.TERMINATED
        self.store.update_session(session_info)
        
        # Remove from storage after marking as terminated
        success = self.store.delete_session(session_id, session_info.user_id)
        
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        return success
    
    def terminate_user_sessions(self, user_id: str, except_session: Optional[str] = None) -> int:
        """Terminate all sessions for a user"""
        session_ids = self.store.get_user_sessions(user_id)
        terminated = 0
        
        for session_id in session_ids:
            if except_session and session_id == except_session:
                continue
                
            if self.terminate_session(session_id):
                terminated += 1
        
        logger.info(f"Terminated {terminated} sessions for user {user_id}")
        return terminated
    
    def update_mfa_status(self, session_id: str, mfa_verified: bool) -> bool:
        """Update MFA verification status"""
        session_info = self.store.get_session(session_id)
        
        if not session_info:
            return False
        
        session_info.mfa_verified = mfa_verified
        return self.store.update_session(session_info)
    
    def check_permission(self, session_id: str, required_permission: str) -> bool:
        """Check if session has required permission"""
        session_info = self.store.get_session(session_id)
        
        if not session_info or session_info.state != SessionState.ACTIVE:
            return False
        
        # Check if MFA is required for sensitive operations
        if (self.require_mfa_for_sensitive and 
            required_permission.startswith('admin') and 
            not session_info.mfa_verified):
            return False
        
        return required_permission in session_info.permissions
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        return len(self.active_sessions)
    
    def get_user_active_sessions(self, user_id: str) -> List[SessionInfo]:
        """Get all active sessions for a user"""
        session_ids = self.store.get_user_sessions(user_id)
        active_sessions = []
        
        for session_id in session_ids:
            session_info = self.store.get_session(session_id)
            if session_info and session_info.state == SessionState.ACTIVE:
                active_sessions.append(session_info)
        
        return active_sessions
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        cleaned = self.store.cleanup_expired_sessions()
        
        # Clean up in-memory tracking
        now = datetime.utcnow()
        expired_sessions = [
            sid for sid, last_activity in self.active_sessions.items()
            if (now - last_activity).total_seconds() > self.default_timeout
        ]
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
        
        return cleaned + len(expired_sessions)
    
    def _cleanup_oldest_session(self, user_id: str, session_ids: List[str]):
        """Remove the oldest session for a user"""
        oldest_session_id = None
        oldest_time = datetime.utcnow()
        
        for session_id in session_ids:
            session_info = self.store.get_session(session_id)
            if session_info and session_info.created_at < oldest_time:
                oldest_time = session_info.created_at
                oldest_session_id = session_id
        
        if oldest_session_id:
            self.terminate_session(oldest_session_id)
    
    def _is_suspicious_activity(self, session_info: SessionInfo, current_ip: str) -> bool:
        """Check for suspicious session activity"""
        # Check for IP address changes (basic check)
        if session_info.ip_address != current_ip:
            # Log IP change but don't automatically mark as suspicious
            # In production, you might want more sophisticated geo-location checks
            logger.info(f"IP change detected for session {session_info.session_id}: "
                       f"{session_info.ip_address} -> {current_ip}")
        
        # Check for rapid session creation (could indicate session hijacking)
        now = datetime.utcnow()
        time_since_creation = (now - session_info.created_at).total_seconds()
        
        if time_since_creation < 60:  # Less than 1 minute old
            user_sessions = self.store.get_user_sessions(session_info.user_id)
            if len(user_sessions) > 3:  # Multiple rapid sessions
                return True
        
        return False


class SessionMiddleware:
    """Session middleware for request processing"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
    
    def process_request(self, request) -> Optional[SessionInfo]:
        """Process incoming request for session validation"""
        # Extract session ID from cookie, header, or token
        session_id = self._extract_session_id(request)
        
        if not session_id:
            return None
        
        # Get client IP
        ip_address = self._get_client_ip(request)
        
        # Validate session
        return self.session_manager.validate_session(session_id, ip_address)
    
    def _extract_session_id(self, request) -> Optional[str]:
        """Extract session ID from request"""
        # Check Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        
        # Check cookie
        return request.cookies.get('session_id')
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address from request"""
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        return getattr(request, 'remote_addr', 'unknown')