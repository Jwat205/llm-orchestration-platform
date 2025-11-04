"""
Multi-Factor Authentication Handler
Supports TOTP, SMS, Email, and Hardware Token MFA
"""

import pyotp
import qrcode
import io
import base64
import secrets
import hashlib
import hmac
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from enum import Enum
import logging
import requests
from cryptography.fernet import Fernet


logger = logging.getLogger(__name__)


class MFAMethod(Enum):
    """Supported MFA methods"""
    TOTP = "totp"
    SMS = "sms"
    EMAIL = "email"
    HARDWARE_TOKEN = "hardware_token"
    BACKUP_CODES = "backup_codes"


class TOTPProvider:
    """Time-based One-Time Password provider"""
    
    def __init__(self, issuer_name: str = "LLM API Platform"):
        self.issuer_name = issuer_name
    
    def generate_secret(self) -> str:
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    def generate_qr_code(self, secret: str, user_email: str) -> str:
        """Generate QR code for TOTP setup"""
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user_email,
            issuer_name=self.issuer_name
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 string
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    def verify_token(self, secret: str, token: str, window: int = 1) -> bool:
        """Verify TOTP token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, window=window)
    
    def get_current_token(self, secret: str) -> str:
        """Get current TOTP token (for testing)"""
        totp = pyotp.TOTP(secret)
        return totp.now()


class SMSProvider:
    """SMS-based MFA provider"""
    
    def __init__(self, api_key: str, api_url: str, sender_id: str):
        self.api_key = api_key
        self.api_url = api_url
        self.sender_id = sender_id
    
    def send_code(self, phone_number: str, code: str) -> bool:
        """Send MFA code via SMS"""
        try:
            message = f"Your verification code is: {code}. This code expires in 5 minutes."
            
            payload = {
                'to': phone_number,
                'from': self.sender_id,
                'text': message
            }
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            logger.info(f"SMS sent successfully to {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS to {phone_number}: {e}")
            return False


class EmailProvider:
    """Email-based MFA provider"""
    
    def __init__(self, smtp_config: Dict[str, Any]):
        self.smtp_config = smtp_config
    
    def send_code(self, email: str, code: str) -> bool:
        """Send MFA code via email"""
        try:
            import smtplib
            from email.mime.text import MimeText
            from email.mime.multipart import MimeMultipart
            
            msg = MimeMultipart()
            msg['From'] = self.smtp_config['from_email']
            msg['To'] = email
            msg['Subject'] = "Your Verification Code"
            
            body = f"""
            Your verification code is: {code}
            
            This code will expire in 5 minutes.
            
            If you didn't request this code, please ignore this email.
            """
            
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port'])
            server.starttls()
            server.login(self.smtp_config['username'], self.smtp_config['password'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {e}")
            return False


class BackupCodeGenerator:
    """Backup codes generator and validator"""
    
    @staticmethod
    def generate_codes(count: int = 10) -> List[str]:
        """Generate backup codes"""
        codes = []
        for _ in range(count):
            code = secrets.token_hex(4).upper()
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)
        return codes
    
    @staticmethod
    def hash_codes(codes: List[str]) -> List[str]:
        """Hash backup codes for storage"""
        hashed_codes = []
        for code in codes:
            # Remove formatting and convert to lowercase
            clean_code = code.replace('-', '').lower()
            hashed = hashlib.sha256(clean_code.encode()).hexdigest()
            hashed_codes.append(hashed)
        return hashed_codes
    
    @staticmethod
    def verify_code(code: str, hashed_codes: List[str]) -> bool:
        """Verify backup code against hashed codes"""
        clean_code = code.replace('-', '').lower()
        code_hash = hashlib.sha256(clean_code.encode()).hexdigest()
        return code_hash in hashed_codes


class MFAHandler:
    """Main MFA handler coordinating all MFA methods"""
    
    def __init__(self, 
                 encryption_key: bytes,
                 totp_issuer: str = "LLM API Platform",
                 sms_config: Optional[Dict[str, Any]] = None,
                 email_config: Optional[Dict[str, Any]] = None):
        self.fernet = Fernet(encryption_key)
        self.totp_provider = TOTPProvider(totp_issuer)
        self.sms_provider = SMSProvider(**sms_config) if sms_config else None
        self.email_provider = EmailProvider(email_config) if email_config else None
        self.pending_codes: Dict[str, Dict[str, Any]] = {}
    
    def setup_totp(self, user_id: str, user_email: str) -> Dict[str, Any]:
        """Setup TOTP for user"""
        secret = self.totp_provider.generate_secret()
        qr_code = self.totp_provider.generate_qr_code(secret, user_email)
        
        # Encrypt secret for storage
        encrypted_secret = self.fernet.encrypt(secret.encode()).decode()
        
        return {
            'secret': encrypted_secret,
            'qr_code': qr_code,
            'backup_codes': BackupCodeGenerator.generate_codes()
        }
    
    def verify_totp(self, user_id: str, encrypted_secret: str, token: str) -> bool:
        """Verify TOTP token"""
        try:
            secret = self.fernet.decrypt(encrypted_secret.encode()).decode()
            return self.totp_provider.verify_token(secret, token)
        except Exception as e:
            logger.error(f"TOTP verification failed for user {user_id}: {e}")
            return False
    
    def send_sms_code(self, user_id: str, phone_number: str) -> bool:
        """Send SMS MFA code"""
        if not self.sms_provider:
            logger.error("SMS provider not configured")
            return False
        
        code = self._generate_numeric_code()
        expiry = datetime.utcnow() + timedelta(minutes=5)
        
        self.pending_codes[f"{user_id}_sms"] = {
            'code': code,
            'expiry': expiry,
            'attempts': 0
        }
        
        return self.sms_provider.send_code(phone_number, code)
    
    def send_email_code(self, user_id: str, email: str) -> bool:
        """Send email MFA code"""
        if not self.email_provider:
            logger.error("Email provider not configured")
            return False
        
        code = self._generate_numeric_code()
        expiry = datetime.utcnow() + timedelta(minutes=5)
        
        self.pending_codes[f"{user_id}_email"] = {
            'code': code,
            'expiry': expiry,
            'attempts': 0
        }
        
        return self.email_provider.send_code(email, code)
    
    def verify_sms_code(self, user_id: str, code: str) -> bool:
        """Verify SMS MFA code"""
        return self._verify_pending_code(f"{user_id}_sms", code)
    
    def verify_email_code(self, user_id: str, code: str) -> bool:
        """Verify email MFA code"""
        return self._verify_pending_code(f"{user_id}_email", code)
    
    def verify_backup_code(self, user_id: str, code: str, hashed_codes: List[str]) -> bool:
        """Verify backup code"""
        return BackupCodeGenerator.verify_code(code, hashed_codes)
    
    def generate_backup_codes(self, user_id: str) -> List[str]:
        """Generate new backup codes"""
        return BackupCodeGenerator.generate_codes()
    
    def _generate_numeric_code(self, length: int = 6) -> str:
        """Generate numeric code for SMS/Email"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(length)])
    
    def _verify_pending_code(self, key: str, code: str) -> bool:
        """Verify pending SMS/Email code"""
        if key not in self.pending_codes:
            return False
        
        pending = self.pending_codes[key]
        
        # Check expiry
        if datetime.utcnow() > pending['expiry']:
            del self.pending_codes[key]
            return False
        
        # Check attempts
        pending['attempts'] += 1
        if pending['attempts'] > 3:
            del self.pending_codes[key]
            return False
        
        # Verify code
        if pending['code'] == code:
            del self.pending_codes[key]
            return True
        
        return False
    
    def cleanup_expired_codes(self):
        """Remove expired pending codes"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, data in self.pending_codes.items()
            if now > data['expiry']
        ]
        
        for key in expired_keys:
            del self.pending_codes[key]


class MFAPolicy:
    """MFA policy enforcement"""
    
    def __init__(self):
        self.required_methods: Dict[str, List[MFAMethod]] = {}
        self.grace_period_hours = 24
    
    def set_required_methods(self, user_role: str, methods: List[MFAMethod]):
        """Set required MFA methods for user role"""
        self.required_methods[user_role] = methods
    
    def is_mfa_required(self, user_role: str) -> bool:
        """Check if MFA is required for user role"""
        return user_role in self.required_methods
    
    def get_required_methods(self, user_role: str) -> List[MFAMethod]:
        """Get required MFA methods for user role"""
        return self.required_methods.get(user_role, [])
    
    def is_method_sufficient(self, user_role: str, method: MFAMethod) -> bool:
        """Check if MFA method is sufficient for user role"""
        required = self.get_required_methods(user_role)
        return method in required or not required
    
    def is_within_grace_period(self, last_mfa_time: datetime) -> bool:
        """Check if user is within MFA grace period"""
        if not last_mfa_time:
            return False
        
        grace_expiry = last_mfa_time + timedelta(hours=self.grace_period_hours)
        return datetime.utcnow() < grace_expiry


class MFASession:
    """MFA session management"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def start_mfa_challenge(self, user_id: str, required_methods: List[MFAMethod]) -> str:
        """Start MFA challenge session"""
        session_id = secrets.token_urlsafe(32)
        
        self.active_sessions[session_id] = {
            'user_id': user_id,
            'required_methods': required_methods,
            'completed_methods': [],
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(minutes=15)
        }
        
        return session_id
    
    def complete_mfa_method(self, session_id: str, method: MFAMethod) -> bool:
        """Mark MFA method as completed"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        
        if datetime.utcnow() > session['expires_at']:
            del self.active_sessions[session_id]
            return False
        
        if method not in session['completed_methods']:
            session['completed_methods'].append(method)
        
        return True
    
    def is_mfa_complete(self, session_id: str) -> bool:
        """Check if MFA challenge is complete"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        required = set(session['required_methods'])
        completed = set(session['completed_methods'])
        
        return required.issubset(completed)
    
    def get_remaining_methods(self, session_id: str) -> List[MFAMethod]:
        """Get remaining MFA methods to complete"""
        if session_id not in self.active_sessions:
            return []
        
        session = self.active_sessions[session_id]
        required = set(session['required_methods'])
        completed = set(session['completed_methods'])
        
        return list(required - completed)
    
    def cleanup_expired_sessions(self):
        """Remove expired MFA sessions"""
        now = datetime.utcnow()
        expired_sessions = [
            session_id for session_id, data in self.active_sessions.items()
            if now > data['expires_at']
        ]
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]