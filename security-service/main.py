# security-service/app/main.py
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from typing import Optional, Dict, List
import uvicorn

from .auth.sso_providers import SSOProviderManager
from .monitoring.security_scanner import SecurityScanner
from .monitoring.threat_detector import ThreatDetector
from .monitoring.anomaly_detector import AnomalyDetector
from .compliance.gdpr_handler import GDPRHandler
from .compliance.soc2_reporter import SOC2Reporter
from .compliance.audit_exporter import AuditExporter
from .encryption.key_manager import KeyManager
from .encryption.data_encryption import DataEncryption
from .encryption.secure_storage import SecureStorage
from .models import SecurityEvent, ThreatAlert, ComplianceReport
from .config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Security Service")
    
    # Initialize background services
    security_scanner = SecurityScanner()
    threat_detector = ThreatDetector()
    anomaly_detector = AnomalyDetector()
    
    # Start background tasks
    asyncio.create_task(security_scanner.run_continuous_scan())
    asyncio.create_task(threat_detector.monitor_threats())
    asyncio.create_task(anomaly_detector.detect_anomalies())
    
    yield
    
    # Shutdown
    logger.info("Shutting down Security Service")

app = FastAPI(
    title="Security Service",
    description="Enterprise Security and Compliance Service",
    version="1.0.0",
    lifespan=lifespan
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=settings.ALLOWED_HOSTS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Dependency for authentication
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate JWT token and return user info"""
    from .auth.jwt_handler import verify_token
    
    try:
        payload = verify_token(credentials.credentials)
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# SSO Management Endpoints
@app.post("/api/v1/sso/initiate")
async def initiate_sso_login(
    organization_id: str,
    provider: str = "saml",
    user_info: dict = Depends(get_current_user)
):
    """Initiate SSO login process"""
    try:
        sso_manager = SSOProviderManager()
        login_url = await sso_manager.initiate_login(organization_id, provider)
        
        return {
            "anomalies": anomalies,
            "organization_id": organization_id,
            "detection_type": detection_type,
            "anomaly_score": anomaly_detector.calculate_anomaly_score(anomalies)
        }
    except Exception as e:
        logger.error(f"Failed to get anomaly detection: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve anomaly data")

# Compliance Management Endpoints
@app.get("/api/v1/compliance/frameworks")
async def get_compliance_frameworks(
    user_info: dict = Depends(get_current_user)
):
    """Get available compliance frameworks"""
    return {
        "frameworks": [
            {
                "id": "soc2",
                "name": "SOC 2 Type II",
                "description": "Service Organization Control 2",
                "categories": ["security", "availability", "processing_integrity", "confidentiality", "privacy"]
            },
            {
                "id": "gdpr",
                "name": "GDPR",
                "description": "General Data Protection Regulation",
                "categories": ["lawfulness", "data_subject_rights", "security", "breach_management"]
            },
            {
                "id": "hipaa",
                "name": "HIPAA",
                "description": "Health Insurance Portability and Accountability Act",
                "categories": ["administrative", "physical", "technical"]
            },
            {
                "id": "pci_dss",
                "name": "PCI DSS",
                "description": "Payment Card Industry Data Security Standard",
                "categories": ["network_security", "data_protection", "vulnerability_management"]
            }
        ]
    }

@app.post("/api/v1/compliance/assess/{framework}")
async def run_compliance_assessment(
    framework: str,
    organization_id: str,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(get_current_user)
):
    """Run compliance assessment for specific framework"""
    try:
        if framework == "soc2":
            reporter = SOC2Reporter()
            background_tasks.add_task(
                reporter.run_assessment,
                organization_id,
                user_info["user_id"]
            )
        elif framework == "gdpr":
            handler = GDPRHandler()
            background_tasks.add_task(
                handler.run_assessment,
                organization_id,
                user_info["user_id"]
            )
        else:
            raise HTTPException(status_code=400, detail=f"Framework {framework} not supported")
        
        return {
            "success": True,
            "message": f"{framework.upper()} assessment initiated",
            "organization_id": organization_id,
            "framework": framework
        }
    except Exception as e:
        logger.error(f"Compliance assessment failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate compliance assessment")

@app.get("/api/v1/compliance/reports/{organization_id}")
async def get_compliance_reports(
    organization_id: str,
    framework: Optional[str] = None,
    limit: int = 10,
    user_info: dict = Depends(get_current_user)
):
    """Get compliance reports for organization"""
    try:
        exporter = AuditExporter()
        reports = await exporter.get_compliance_reports(
            organization_id,
            framework,
            limit
        )
        
        return {
            "reports": reports,
            "organization_id": organization_id,
            "framework": framework,
            "total": len(reports)
        }
    except Exception as e:
        logger.error(f"Failed to get compliance reports: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve compliance reports")

@app.get("/api/v1/compliance/dashboard/{organization_id}")
async def get_compliance_dashboard(
    organization_id: str,
    user_info: dict = Depends(get_current_user)
):
    """Get compliance dashboard data"""
    try:
        soc2_reporter = SOC2Reporter()
        gdpr_handler = GDPRHandler()
        
        # Get latest compliance scores
        dashboard_data = {
            "organization_id": organization_id,
            "frameworks": {
                "soc2": await soc2_reporter.get_compliance_summary(organization_id),
                "gdpr": await gdpr_handler.get_compliance_summary(organization_id)
            },
            "overall_score": 0,
            "critical_issues": [],
            "recent_assessments": []
        }
        
        # Calculate overall score
        scores = []
        for framework_data in dashboard_data["frameworks"].values():
            if framework_data.get("score"):
                scores.append(framework_data["score"])
        
        if scores:
            dashboard_data["overall_score"] = sum(scores) / len(scores)
        
        return dashboard_data
    except Exception as e:
        logger.error(f"Failed to get compliance dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve compliance dashboard")

# Encryption and Key Management Endpoints
@app.post("/api/v1/encryption/keys/rotate")
async def rotate_encryption_keys(
    organization_id: str,
    background_tasks: BackgroundTasks,
    key_type: str = "master",
    *,
    user_info: dict = Depends(get_current_user)
):
    """Rotate encryption keys"""
    try:
        key_manager = KeyManager()
        
        background_tasks.add_task(
            key_manager.rotate_keys,
            organization_id,
            key_type,
            user_info["user_id"]
        )
        
        return {
            "success": True,
            "message": f"{key_type} key rotation initiated",
            "organization_id": organization_id,
            "key_type": key_type
        }
    except Exception as e:
        logger.error(f"Key rotation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate key rotation")

@app.get("/api/v1/encryption/status/{organization_id}")
async def get_encryption_status(
    organization_id: str,
    user_info: dict = Depends(get_current_user)
):
    """Get encryption status for organization"""
    try:
        encryption = DataEncryption()
        status = await encryption.get_encryption_status(organization_id)
        
        return {
            "organization_id": organization_id,
            "encryption_status": status,
            "algorithms": encryption.get_supported_algorithms(),
            "key_rotation_schedule": encryption.get_rotation_schedule(organization_id)
        }
    except Exception as e:
        logger.error(f"Failed to get encryption status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve encryption status")

@app.post("/api/v1/data/encrypt")
async def encrypt_data(
    data: dict,
    organization_id: str,
    encryption_context: Optional[dict] = None,
    user_info: dict = Depends(get_current_user)
):
    """Encrypt sensitive data"""
    try:
        encryption = DataEncryption()
        encrypted_data = await encryption.encrypt_data(
            data,
            organization_id,
            encryption_context or {}
        )
        
        return {
            "success": True,
            "encrypted_data": encrypted_data,
            "encryption_metadata": {
                "algorithm": encryption.get_algorithm(),
                "key_version": encryption.get_key_version(organization_id),
                "encrypted_at": encryption.get_timestamp()
            }
        }
    except Exception as e:
        logger.error(f"Data encryption failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to encrypt data")

@app.post("/api/v1/data/decrypt")
async def decrypt_data(
    encrypted_data: str,
    organization_id: str,
    encryption_context: Optional[dict] = None,
    user_info: dict = Depends(get_current_user)
):
    """Decrypt sensitive data"""
    try:
        encryption = DataEncryption()
        decrypted_data = await encryption.decrypt_data(
            encrypted_data,
            organization_id,
            encryption_context or {}
        )
        
        return {
            "success": True,
            "decrypted_data": decrypted_data
        }
    except Exception as e:
        logger.error(f"Data decryption failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to decrypt data")

# Audit and Logging Endpoints
@app.get("/api/v1/audit/logs/{organization_id}")
async def get_audit_logs(
    organization_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
    user_info: dict = Depends(get_current_user)
):
    """Get audit logs for organization"""
    try:
        exporter = AuditExporter()
        logs = await exporter.get_audit_logs(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            action=action,
            user_id=user_id,
            limit=limit
        )
        
        return {
            "logs": logs,
            "organization_id": organization_id,
            "total": len(logs),
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "action": action,
                "user_id": user_id
            }
        }
    except Exception as e:
        logger.error(f"Failed to get audit logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")

@app.post("/api/v1/audit/export")
async def export_audit_data(
    organization_id: str,
    background_tasks: BackgroundTasks,
    date_range: dict = {},
    export_format: str = "json",
    user_info: dict = Depends(get_current_user)
):
    """Export audit data for compliance"""
    try:
        exporter = AuditExporter()
        
        background_tasks.add_task(
            exporter.export_audit_data,
            organization_id,
            export_format,
            date_range,
            user_info["user_id"]
        )
        
        return {
            "success": True,
            "message": f"Audit data export initiated ({export_format})",
            "organization_id": organization_id,
            "export_format": export_format
        }
    except Exception as e:
        logger.error(f"Audit export failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate audit export")

# Health and Status Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "security-service",
        "version": "1.0.0",
        "timestamp": "2024-01-01T00:00:00Z"
    }

@app.get("/api/v1/status")
async def get_service_status(user_info: dict = Depends(get_current_user)):
    """Get detailed service status"""
    try:
        scanner = SecurityScanner()
        threat_detector = ThreatDetector()
        anomaly_detector = AnomalyDetector()
        
        return {
            "service": "security-service",
            "status": "operational",
            "components": {
                "security_scanner": await scanner.get_status(),
                "threat_detector": await threat_detector.get_status(),
                "anomaly_detector": await anomaly_detector.get_status(),
                "encryption": "operational",
                "compliance": "operational"
            },
            "metrics": {
                "uptime": "99.9%",
                "response_time": "<50ms",
                "active_scans": await scanner.get_active_scan_count(),
                "threats_detected": await threat_detector.get_threat_count(),
                "anomalies_detected": await anomaly_detector.get_anomaly_count()
            }
        }
    except Exception as e:
        logger.error(f"Failed to get service status: {e}")
        return {
            "service": "security-service",
            "status": "degraded",
            "error": str(e)
        }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True
    )

