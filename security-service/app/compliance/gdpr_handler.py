"""
GDPR Compliance Handler
Handles GDPR compliance requirements including data processing, consent, and user rights
"""

import json
import hashlib
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging
from cryptography.fernet import Fernet


logger = logging.getLogger(__name__)


class ConsentType(Enum):
    """Types of user consent"""
    MARKETING = "marketing"
    ANALYTICS = "analytics"
    FUNCTIONAL = "functional"
    NECESSARY = "necessary"
    THIRD_PARTY = "third_party"


class DataProcessingPurpose(Enum):
    """Purposes for data processing"""
    SERVICE_PROVISION = "service_provision"
    SECURITY = "security"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    LEGAL_COMPLIANCE = "legal_compliance"
    CUSTOMER_SUPPORT = "customer_support"


class LegalBasis(Enum):
    """Legal basis for processing personal data"""
    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_TASK = "public_task"
    LEGITIMATE_INTERESTS = "legitimate_interests"


@dataclass
class ConsentRecord:
    """User consent record"""
    user_id: str
    consent_type: ConsentType
    granted: bool
    timestamp: datetime
    ip_address: str
    user_agent: str
    version: str
    withdrawn_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['consent_type'] = self.consent_type.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.withdrawn_at:
            data['withdrawn_at'] = self.withdrawn_at.isoformat()
        return data


@dataclass
class DataProcessingRecord:
    """Data processing activity record"""
    id: str
    user_id: str
    data_type: str
    purpose: DataProcessingPurpose
    legal_basis: LegalBasis
    timestamp: datetime
    retention_period: timedelta
    third_parties: List[str]
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['purpose'] = self.purpose.value
        data['legal_basis'] = self.legal_basis.value
        data['timestamp'] = self.timestamp.isoformat()
        data['retention_period'] = self.retention_period.total_seconds()
        return data


@dataclass
class DataSubjectRequest:
    """Data subject request (DSR)"""
    id: str
    user_id: str
    request_type: str  # access, rectification, erasure, portability, restriction
    timestamp: datetime
    status: str  # pending, processing, completed, rejected
    completed_at: Optional[datetime] = None
    response_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data


class ConsentManager:
    """Manages user consent records"""
    
    def __init__(self, encryption_key: bytes):
        self.fernet = Fernet(encryption_key)
        self.consent_records: Dict[str, List[ConsentRecord]] = {}
    
    def record_consent(self,
                      user_id: str,
                      consent_type: ConsentType,
                      granted: bool,
                      ip_address: str,
                      user_agent: str,
                      version: str = "1.0") -> ConsentRecord:
        """Record user consent"""
        consent = ConsentRecord(
            user_id=user_id,
            consent_type=consent_type,
            granted=granted,
            timestamp=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent,
            version=version
        )
        
        if user_id not in self.consent_records:
            self.consent_records[user_id] = []
        
        self.consent_records[user_id].append(consent)
        
        logger.info(f"Consent recorded for user {user_id}: {consent_type.value} = {granted}")
        return consent
    
    def withdraw_consent(self,
                        user_id: str,
                        consent_type: ConsentType) -> bool:
        """Withdraw user consent"""
        if user_id not in self.consent_records:
            return False
        
        # Find the latest consent record for this type
        user_consents = self.consent_records[user_id]
        for consent in reversed(user_consents):
            if (consent.consent_type == consent_type and 
                consent.granted and 
                consent.withdrawn_at is None):
                
                consent.withdrawn_at = datetime.utcnow()
                logger.info(f"Consent withdrawn for user {user_id}: {consent_type.value}")
                return True
        
        return False
    
    def get_current_consent(self,
                           user_id: str,
                           consent_type: ConsentType) -> Optional[bool]:
        """Get current consent status"""
        if user_id not in self.consent_records:
            return None
        
        # Find the latest consent record for this type
        user_consents = self.consent_records[user_id]
        for consent in reversed(user_consents):
            if consent.consent_type == consent_type:
                if consent.withdrawn_at is not None:
                    return False
                return consent.granted
        
        return None
    
    def get_consent_history(self, user_id: str) -> List[ConsentRecord]:
        """Get complete consent history for user"""
        return self.consent_records.get(user_id, [])
    
    def export_consent_data(self, user_id: str) -> Dict[str, Any]:
        """Export consent data for user (for data portability)"""
        consents = self.get_consent_history(user_id)
        return {
            'user_id': user_id,
            'consent_records': [consent.to_dict() for consent in consents],
            'exported_at': datetime.utcnow().isoformat()
        }


class DataProcessingLogger:
    """Logs data processing activities"""
    
    def __init__(self):
        self.processing_records: List[DataProcessingRecord] = []
    
    def log_processing(self,
                      user_id: str,
                      data_type: str,
                      purpose: DataProcessingPurpose,
                      legal_basis: LegalBasis,
                      retention_period: timedelta,
                      third_parties: List[str] = None,
                      description: str = "") -> str:
        """Log data processing activity"""
        record_id = hashlib.md5(
            f"{user_id}{data_type}{purpose.value}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]
        
        record = DataProcessingRecord(
            id=record_id,
            user_id=user_id,
            data_type=data_type,
            purpose=purpose,
            legal_basis=legal_basis,
            timestamp=datetime.utcnow(),
            retention_period=retention_period,
            third_parties=third_parties or [],
            description=description
        )
        
        self.processing_records.append(record)
        
        logger.info(f"Data processing logged: {record_id} for user {user_id}")
        return record_id
    
    def get_user_processing_records(self, user_id: str) -> List[DataProcessingRecord]:
        """Get processing records for user"""
        return [record for record in self.processing_records if record.user_id == user_id]
    
    def get_records_by_purpose(self, purpose: DataProcessingPurpose) -> List[DataProcessingRecord]:
        """Get records by processing purpose"""
        return [record for record in self.processing_records if record.purpose == purpose]
    
    def cleanup_expired_records(self) -> int:
        """Remove records past their retention period"""
        now = datetime.utcnow()
        initial_count = len(self.processing_records)
        
        self.processing_records = [
            record for record in self.processing_records
            if now - record.timestamp < record.retention_period
        ]
        
        cleaned_count = initial_count - len(self.processing_records)
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired processing records")
        
        return cleaned_count


class DataSubjectRightsHandler:
    """Handles data subject rights requests"""
    
    def __init__(self, consent_manager: ConsentManager, processing_logger: DataProcessingLogger):
        self.consent_manager = consent_manager
        self.processing_logger = processing_logger
        self.requests: Dict[str, DataSubjectRequest] = {}
    
    def submit_access_request(self, user_id: str) -> str:
        """Submit data access request (Article 15)"""
        request_id = f"access_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        request = DataSubjectRequest(
            id=request_id,
            user_id=user_id,
            request_type="access",
            timestamp=datetime.utcnow(),
            status="pending"
        )
        
        self.requests[request_id] = request
        logger.info(f"Data access request submitted: {request_id}")
        
        return request_id
    
    def submit_erasure_request(self, user_id: str) -> str:
        """Submit data erasure request (Article 17 - Right to be forgotten)"""
        request_id = f"erasure_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        request = DataSubjectRequest(
            id=request_id,
            user_id=user_id,
            request_type="erasure",
            timestamp=datetime.utcnow(),
            status="pending"
        )
        
        self.requests[request_id] = request
        logger.info(f"Data erasure request submitted: {request_id}")
        
        return request_id
    
    def submit_portability_request(self, user_id: str) -> str:
        """Submit data portability request (Article 20)"""
        request_id = f"portability_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        request = DataSubjectRequest(
            id=request_id,
            user_id=user_id,
            request_type="portability",
            timestamp=datetime.utcnow(),
            status="pending"
        )
        
        self.requests[request_id] = request
        logger.info(f"Data portability request submitted: {request_id}")
        
        return request_id
    
    def process_access_request(self, request_id: str) -> Dict[str, Any]:
        """Process data access request"""
        if request_id not in self.requests:
            raise ValueError(f"Request {request_id} not found")
        
        request = self.requests[request_id]
        if request.request_type != "access":
            raise ValueError(f"Request {request_id} is not an access request")
        
        request.status = "processing"
        
        # Compile user data
        user_data = {
            'user_id': request.user_id,
            'consent_records': self.consent_manager.export_consent_data(request.user_id),
            'processing_records': [
                record.to_dict() for record in 
                self.processing_logger.get_user_processing_records(request.user_id)
            ],
            'generated_at': datetime.utcnow().isoformat()
        }
        
        request.status = "completed"
        request.completed_at = datetime.utcnow()
        request.response_data = user_data
        
        logger.info(f"Data access request completed: {request_id}")
        return user_data
    
    def process_portability_request(self, request_id: str) -> Dict[str, Any]:
        """Process data portability request"""
        if request_id not in self.requests:
            raise ValueError(f"Request {request_id} not found")
        
        request = self.requests[request_id]
        if request.request_type != "portability":
            raise ValueError(f"Request {request_id} is not a portability request")
        
        request.status = "processing"
        
        # Export user data in structured format
        export_data = {
            'user_id': request.user_id,
            'consent_data': self.consent_manager.export_consent_data(request.user_id),
            'processing_history': [
                record.to_dict() for record in 
                self.processing_logger.get_user_processing_records(request.user_id)
            ],
            'export_format': 'JSON',
            'exported_at': datetime.utcnow().isoformat()
        }
        
        request.status = "completed"
        request.completed_at = datetime.utcnow()
        request.response_data = export_data
        
        logger.info(f"Data portability request completed: {request_id}")
        return export_data
    
    def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get request status"""
        if request_id not in self.requests:
            return None
        
        return self.requests[request_id].to_dict()


class GDPRComplianceChecker:
    """Checks GDPR compliance"""
    
    def __init__(self, consent_manager: ConsentManager, processing_logger: DataProcessingLogger):
        self.consent_manager = consent_manager
        self.processing_logger = processing_logger
    
    def check_consent_compliance(self, user_id: str) -> Dict[str, Any]:
        """Check consent compliance for user"""
        consent_history = self.consent_manager.get_consent_history(user_id)
        
        compliance_status = {
            'user_id': user_id,
            'compliant': True,
            'issues': [],
            'consent_summary': {}
        }
        
        # Check each consent type
        for consent_type in ConsentType:
            current_consent = self.consent_manager.get_current_consent(user_id, consent_type)
            compliance_status['consent_summary'][consent_type.value] = current_consent
            
            # Check if processing is happening without consent
            if current_consent is False or current_consent is None:
                processing_records = self.processing_logger.get_user_processing_records(user_id)
                
                # Check if there's processing that requires this consent
                if consent_type == ConsentType.MARKETING:
                    marketing_processing = [
                        r for r in processing_records 
                        if r.purpose == DataProcessingPurpose.MARKETING
                    ]
                    
                    if marketing_processing and current_consent is not True:
                        compliance_status['compliant'] = False
                        compliance_status['issues'].append(
                            f"Marketing processing without {consent_type.value} consent"
                        )
        
        return compliance_status
    
    def check_retention_compliance(self) -> Dict[str, Any]:
        """Check data retention compliance"""
        expired_records = []
        now = datetime.utcnow()
        
        for record in self.processing_logger.processing_records:
            if now - record.timestamp > record.retention_period:
                expired_records.append(record.id)
        
        compliance_status = {
            'compliant': len(expired_records) == 0,
            'expired_records_count': len(expired_records),
            'expired_record_ids': expired_records,
            'checked_at': now.isoformat()
        }
        
        if not compliance_status['compliant']:
            logger.warning(f"Found {len(expired_records)} records past retention period")
        
        return compliance_status
    
    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'retention_compliance': self.check_retention_compliance(),
            'processing_summary': {
                'total_records': len(self.processing_logger.processing_records),
                'by_purpose': {},
                'by_legal_basis': {}
            },
            'consent_summary': {
                'total_users': len(self.consent_manager.consent_records),
                'by_consent_type': {}
            }
        }
        
        # Processing summary
        for record in self.processing_logger.processing_records:
            purpose = record.purpose.value
            legal_basis = record.legal_basis.value
            
            if purpose not in report['processing_summary']['by_purpose']:
                report['processing_summary']['by_purpose'][purpose] = 0
            report['processing_summary']['by_purpose'][purpose] += 1
            
            if legal_basis not in report['processing_summary']['by_legal_basis']:
                report['processing_summary']['by_legal_basis'][legal_basis] = 0
            report['processing_summary']['by_legal_basis'][legal_basis] += 1
        
        # Consent summary
        for user_id, consents in self.consent_manager.consent_records.items():
            for consent in consents:
                consent_type = consent.consent_type.value
                if consent_type not in report['consent_summary']['by_consent_type']:
                    report['consent_summary']['by_consent_type'][consent_type] = {
                        'granted': 0,
                        'withdrawn': 0
                    }
                
                if consent.granted and consent.withdrawn_at is None:
                    report['consent_summary']['by_consent_type'][consent_type]['granted'] += 1
                elif consent.withdrawn_at is not None:
                    report['consent_summary']['by_consent_type'][consent_type]['withdrawn'] += 1
        
        return report


class GDPRHandler:
    """Main GDPR compliance handler"""
    
    def __init__(self, encryption_key: bytes):
        self.consent_manager = ConsentManager(encryption_key)
        self.processing_logger = DataProcessingLogger()
        self.rights_handler = DataSubjectRightsHandler(self.consent_manager, self.processing_logger)
        self.compliance_checker = GDPRComplianceChecker(self.consent_manager, self.processing_logger)
    
    def record_consent(self, user_id: str, consent_type: ConsentType, granted: bool, 
                      ip_address: str, user_agent: str) -> ConsentRecord:
        """Record user consent"""
        return self.consent_manager.record_consent(
            user_id, consent_type, granted, ip_address, user_agent
        )
    
    def log_data_processing(self, user_id: str, data_type: str, 
                           purpose: DataProcessingPurpose, legal_basis: LegalBasis,
                           retention_period: timedelta, description: str = "") -> str:
        """Log data processing activity"""
        return self.processing_logger.log_processing(
            user_id, data_type, purpose, legal_basis, retention_period, [], description
        )
    
    def handle_data_subject_request(self, user_id: str, request_type: str) -> str:
        """Handle data subject rights request"""
        if request_type == "access":
            return self.rights_handler.submit_access_request(user_id)
        elif request_type == "erasure":
            return self.rights_handler.submit_erasure_request(user_id)
        elif request_type == "portability":
            return self.rights_handler.submit_portability_request(user_id)
        else:
            raise ValueError(f"Unsupported request type: {request_type}")
    
    def process_data_subject_request(self, request_id: str) -> Dict[str, Any]:
        """Process pending data subject request"""
        request = self.rights_handler.requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        if request.request_type == "access":
            return self.rights_handler.process_access_request(request_id)
        elif request.request_type == "portability":
            return self.rights_handler.process_portability_request(request_id)
        else:
            raise ValueError(f"Processing not implemented for {request.request_type}")
    
    def check_compliance(self, user_id: str = None) -> Dict[str, Any]:
        """Check GDPR compliance"""
        if user_id:
            return self.compliance_checker.check_consent_compliance(user_id)
        else:
            return self.compliance_checker.generate_compliance_report()
    
    def cleanup_expired_data(self) -> int:
        """Clean up data past retention period"""
        return self.processing_logger.cleanup_expired_records()