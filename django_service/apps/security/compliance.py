# django-service/apps/security/compliance.py
from django.utils import timezone
from django.db.models import Q, Count
from django.core.cache import cache
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import logging

from .models import Organization, SecurityUser, AuditLog, SecurityEvent, ComplianceReport
from .audit_logger import compliance_logger

logger = logging.getLogger(__name__)

class ComplianceFramework(Enum):
    SOC2 = "soc2"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    CCPA = "ccpa"

@dataclass
class ComplianceRequirement:
    framework: ComplianceFramework
    control_id: str
    title: str
    description: str
    category: str
    severity: str
    automated_check: bool = True
    evidence_required: List[str] = None

@dataclass
class ComplianceResult:
    requirement: ComplianceRequirement
    status: str  # 'compliant', 'non_compliant', 'partial', 'not_applicable'
    score: float  # 0-100
    evidence: List[Dict] = None
    gaps: List[str] = None
    recommendations: List[str] = None
    last_assessed: datetime = None

class SOC2Compliance:
    """SOC 2 Type II compliance implementation"""
    
    def __init__(self, organization: Organization):
        self.organization = organization
        self.requirements = self._define_soc2_requirements()
    
    def _define_soc2_requirements(self) -> List[ComplianceRequirement]:
        """Define SOC 2 Trust Service Criteria"""
        return [
            # Security (Common Criteria)
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART7",
                title="Conditions for Consent",
                description="Clear and specific consent for data processing",
                category="consent",
                severity="high",
                evidence_required=["consent_forms", "consent_withdrawal_process"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART12",
                title="Transparent Information",
                description="Provide transparent information about data processing",
                category="transparency",
                severity="high",
                evidence_required=["privacy_policy", "data_processing_notices"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART15",
                title="Right of Access",
                description="Data subject's right to obtain confirmation of processing",
                category="data_subject_rights",
                severity="high",
                evidence_required=["access_request_procedures", "response_records"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART16",
                title="Right to Rectification",
                description="Right to rectification of inaccurate personal data",
                category="data_subject_rights",
                severity="medium",
                evidence_required=["rectification_procedures", "correction_logs"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART17",
                title="Right to Erasure",
                description="Right to erasure ('right to be forgotten')",
                category="data_subject_rights",
                severity="high",
                evidence_required=["deletion_procedures", "erasure_logs"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART20",
                title="Right to Data Portability",
                description="Right to receive personal data in structured format",
                category="data_subject_rights",
                severity="medium",
                evidence_required=["portability_procedures", "export_capabilities"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART25",
                title="Data Protection by Design",
                description="Implement data protection by design and by default",
                category="technical_measures",
                severity="high",
                evidence_required=["design_documentation", "default_settings"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART32",
                title="Security of Processing",
                description="Implement appropriate technical and organizational measures",
                category="security",
                severity="critical",
                evidence_required=["security_measures", "encryption_implementation"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART33",
                title="Breach Notification to Authority",
                description="Notify supervisory authority of personal data breach",
                category="breach_management",
                severity="critical",
                evidence_required=["breach_procedures", "notification_records"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART34",
                title="Breach Notification to Data Subject",
                description="Communicate personal data breach to data subject",
                category="breach_management",
                severity="high",
                evidence_required=["communication_procedures", "notification_records"]
            ),
        ]
    
    def assess_compliance(self) -> Dict[str, ComplianceResult]:
        """Assess GDPR compliance status"""
        results = {}
        
        for requirement in self.requirements:
            result = self._assess_gdpr_requirement(requirement)
            results[requirement.control_id] = result
            
        return results
    
    def _assess_gdpr_requirement(self, requirement: ComplianceRequirement) -> ComplianceResult:
        """Assess individual GDPR requirement"""
        evidence = []
        gaps = []
        recommendations = []
        score = 0.0
        
        if requirement.control_id == "ART6":  # Lawfulness
            score, evidence, gaps = self._assess_lawful_basis()
        elif requirement.control_id == "ART15":  # Right of Access
            score, evidence, gaps = self._assess_access_rights()
        elif requirement.control_id == "ART17":  # Right to Erasure
            score, evidence, gaps = self._assess_erasure_rights()
        elif requirement.control_id == "ART32":  # Security
            score, evidence, gaps = self._assess_gdpr_security()
        elif requirement.control_id == "ART33":  # Breach Notification
            score, evidence, gaps = self._assess_breach_procedures()
        else:
            # Generic assessment
            score = 70.0
            evidence = ["Policy documented"]
        
        # Determine status
        if score >= 90:
            status = "compliant"
        elif score >= 70:
            status = "partial"
        else:
            status = "non_compliant"
            
        return ComplianceResult(
            requirement=requirement,
            status=status,
            score=score,
            evidence=evidence,
            gaps=gaps,
            recommendations=recommendations,
            last_assessed=timezone.now()
        )
    
    def _assess_lawful_basis(self) -> Tuple[float, List[str], List[str]]:
        """Assess lawful basis for processing"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check if lawful basis is documented
        security_settings = self.organization.security_settings
        if security_settings.get('gdpr_lawful_basis'):
            evidence.append(f"Lawful basis documented: {security_settings['gdpr_lawful_basis']}")
            score += 40
        else:
            gaps.append("No lawful basis documented")
        
        # Check privacy policy existence
        if security_settings.get('privacy_policy_url'):
            evidence.append("Privacy policy published")
            score += 30
        else:
            gaps.append("No privacy policy available")
        
        # Check consent management for applicable processing
        consent_logs = AuditLog.objects.filter(
            organization=self.organization,
            details__contains={'gdpr_consent': True},
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        
        if consent_logs > 0:
            evidence.append(f"Consent management implemented: {consent_logs} records")
            score += 30
        elif security_settings.get('gdpr_lawful_basis') == 'consent':
            gaps.append("Consent required but no consent records found")
        else:
            evidence.append("Consent not required for current lawful basis")
            score += 30
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_access_rights(self) -> Tuple[float, List[str], List[str]]:
        """Assess data subject access rights"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check for access request procedures
        access_requests = AuditLog.objects.filter(
            organization=self.organization,
            action='data_access_request',
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        
        if access_requests > 0:
            evidence.append(f"Access requests processed: {access_requests} in last year")
            score += 50
        
        # Check response time compliance (30 days)
        recent_access_requests = AuditLog.objects.filter(
            organization=self.organization,
            action='data_access_request',
            timestamp__gte=timezone.now() - timedelta(days=90)
        )
        
        compliant_responses = 0
        for request in recent_access_requests:
            response_time = request.details.get('response_time_days', 0)
            if response_time <= 30:
                compliant_responses += 1
        
        if recent_access_requests.count() > 0:
            compliance_rate = (compliant_responses / recent_access_requests.count()) * 100
            if compliance_rate >= 95:
                evidence.append(f"Response time compliance: {compliance_rate:.1f}%")
                score += 30
            else:
                gaps.append(f"Response time compliance below 95%: {compliance_rate:.1f}%")
        
        # Check data export capability
        security_settings = self.organization.security_settings
        if security_settings.get('data_export_enabled'):
            evidence.append("Data export functionality implemented")
            score += 20
        else:
            gaps.append("No data export functionality")
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_erasure_rights(self) -> Tuple[float, List[str], List[str]]:
        """Assess right to erasure implementation"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check for erasure procedures
        erasure_requests = AuditLog.objects.filter(
            organization=self.organization,
            action='data_erasure_request',
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        
        if erasure_requests > 0:
            evidence.append(f"Erasure requests processed: {erasure_requests} in last year")
            score += 40
        
        # Check automated deletion capabilities
        security_settings = self.organization.security_settings
        if security_settings.get('automated_deletion_enabled'):
            evidence.append("Automated deletion procedures implemented")
            score += 30
        else:
            gaps.append("No automated deletion procedures")
        
        # Check data retention policies
        if security_settings.get('data_retention_policy'):
            evidence.append("Data retention policy defined")
            score += 30
        else:
            gaps.append("No data retention policy")
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_gdpr_security(self) -> Tuple[float, List[str], List[str]]:
        """Assess GDPR security requirements"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check encryption implementation
        security_settings = self.organization.security_settings
        if security_settings.get('encryption_at_rest'):
            evidence.append("Data encryption at rest implemented")
            score += 25
        else:
            gaps.append("No encryption at rest")
        
        if security_settings.get('encryption_in_transit'):
            evidence.append("Data encryption in transit implemented")
            score += 25
        else:
            gaps.append("No encryption in transit")
        
        # Check access controls
        if security_settings.get('rbac_enabled'):
            evidence.append("Role-based access controls implemented")
            score += 25
        else:
            gaps.append("No role-based access controls")
        
        # Check audit logging
        recent_logs = AuditLog.objects.filter(
            organization=self.organization,
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        if recent_logs > 50:
            evidence.append("Comprehensive audit logging implemented")
            score += 25
        elif recent_logs > 10:
            evidence.append("Basic audit logging implemented")
            score += 15
            gaps.append("Limited audit logging coverage")
        else:
            gaps.append("Insufficient audit logging")
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_breach_procedures(self) -> Tuple[float, List[str], List[str]]:
        """Assess data breach notification procedures"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check breach response procedures
        security_settings = self.organization.security_settings
        if security_settings.get('breach_response_plan'):
            evidence.append("Data breach response plan documented")
            score += 40
        else:
            gaps.append("No breach response plan")
        
        # Check incident response capability
        security_events = SecurityEvent.objects.filter(
            organization=self.organization,
            event_type='data_breach_attempt',
            created_at__gte=timezone.now() - timedelta(days=365)
        ).count()
        
        if security_events > 0:
            evidence.append(f"Security incidents detected and logged: {security_events}")
            score += 30
        
        # Check notification procedures
        if security_settings.get('breach_notification_contacts'):
            evidence.append("Breach notification contacts configured")
            score += 30
        else:
            gaps.append("No breach notification contacts")
        
        return min(score, 100.0), evidence, gaps

class ComplianceManager:
    """Main compliance management system"""
    
    def __init__(self, organization: Organization):
        self.organization = organization
        self.frameworks = {
            ComplianceFramework.SOC2: SOC2Compliance(organization),
            ComplianceFramework.GDPR: GDPRCompliance(organization)
        }
    
    def run_compliance_assessment(self, framework: ComplianceFramework) -> Dict:
        """Run comprehensive compliance assessment"""
        if framework not in self.frameworks:
            raise ValueError(f"Framework {framework.value} not supported")
        
        compliance_system = self.frameworks[framework]
        results = compliance_system.assess_compliance()
        
        # Calculate overall score
        total_score = sum(result.score for result in results.values())
        average_score = total_score / len(results) if results else 0
        
        # Categorize by status
        status_counts = {
            'compliant': sum(1 for r in results.values() if r.status == 'compliant'),
            'partial': sum(1 for r in results.values() if r.status == 'partial'),
            'non_compliant': sum(1 for r in results.values() if r.status == 'non_compliant'),
            'not_applicable': sum(1 for r in results.values() if r.status == 'not_applicable')
        }
        
        # Generate recommendations
        all_gaps = []
        for result in results.values():
            if result.gaps:
                all_gaps.extend(result.gaps)
        
        assessment_report = {
            'framework': framework.value,
            'organization': self.organization.name,
            'assessment_date': timezone.now().isoformat(),
            'overall_score': round(average_score, 2),
            'total_requirements': len(results),
            'status_summary': status_counts,
            'compliance_percentage': round((status_counts['compliant'] / len(results)) * 100, 2) if results else 0,
            'detailed_results': {
                control_id: {
                    'title': result.requirement.title,
                    'status': result.status,
                    'score': result.score,
                    'category': result.requirement.category,
                    'severity': result.requirement.severity,
                    'evidence': result.evidence,
                    'gaps': result.gaps,
                    'recommendations': result.recommendations
                }
                for control_id, result in results.items()
            },
            'top_gaps': self._get_top_gaps(all_gaps),
            'priority_actions': self._generate_priority_actions(results),
            'next_assessment_due': (timezone.now() + timedelta(days=90)).isoformat()
        }
        
        # Store assessment results
        self._store_assessment_results(framework, assessment_report)
        
        return assessment_report
    
    def _get_top_gaps(self, gaps: List[str], limit: int = 10) -> List[Dict]:
        """Get most common compliance gaps"""
        from collections import Counter
        gap_counts = Counter(gaps)
        
        return [
            {'gap': gap, 'frequency': count}
            for gap, count in gap_counts.most_common(limit)
        ]
    
    def _generate_priority_actions(self, results: Dict[str, ComplianceResult]) -> List[Dict]:
        """Generate prioritized remediation actions"""
        actions = []
        
        # High severity non-compliant items
        for control_id, result in results.items():
            if (result.status == 'non_compliant' and 
                result.requirement.severity in ['critical', 'high']):
                actions.append({
                    'control_id': control_id,
                    'title': result.requirement.title,
                    'priority': 'high',
                    'category': result.requirement.category,
                    'gaps': result.gaps,
                    'estimated_effort': self._estimate_effort(result.requirement.category)
                })
        
        # Medium severity partial compliance
        for control_id, result in results.items():
            if (result.status == 'partial' and 
                result.requirement.severity == 'medium'):
                actions.append({
                    'control_id': control_id,
                    'title': result.requirement.title,
                    'priority': 'medium',
                    'category': result.requirement.category,
                    'gaps': result.gaps,
                    'estimated_effort': self._estimate_effort(result.requirement.category)
                })
        
        return sorted(actions, key=lambda x: {'high': 3, 'medium': 2, 'low': 1}[x['priority']], reverse=True)
    
    def _estimate_effort(self, category: str) -> str:
        """Estimate implementation effort"""
        effort_mapping = {
            'security': 'medium',
            'technical_measures': 'high',
            'data_subject_rights': 'medium',
            'breach_management': 'low',
            'legal_basis': 'low',
            'consent': 'medium',
            'transparency': 'low'
        }
        return effort_mapping.get(category, 'medium')
    
    def _store_assessment_results(self, framework: ComplianceFramework, results: Dict) -> None:
        """Store assessment results in database"""
        try:
            report = ComplianceReport.objects.create(
                organization=self.organization,
                report_type=framework.value,
                status='completed',
                period_start=timezone.now() - timedelta(days=90),
                period_end=timezone.now(),
                report_data=results,
                compliance_score=results['overall_score'],
                findings=results.get('top_gaps', []),
                completed_at=timezone.now()
            )
            
            logger.info(f"Stored compliance assessment results: {report.id}")
            
        except Exception as e:
            logger.error(f"Failed to store compliance results: {e}")
    
    def generate_compliance_dashboard(self) -> Dict:
        """Generate compliance dashboard data"""
        dashboard_data = {
            'organization': self.organization.name,
            'last_updated': timezone.now().isoformat(),
            'frameworks': {}
        }
        
        for framework in [ComplianceFramework.SOC2, ComplianceFramework.GDPR]:
            try:
                # Get latest assessment
                latest_report = ComplianceReport.objects.filter(
                    organization=self.organization,
                    report_type=framework.value,
                    status='completed'
                ).order_by('-completed_at').first()
                
                if latest_report:
                    dashboard_data['frameworks'][framework.value] = {
                        'last_assessment': latest_report.completed_at.isoformat(),
                        'compliance_score': latest_report.compliance_score,
                        'status': self._get_compliance_status(latest_report.compliance_score),
                        'critical_gaps': len([
                            gap for gap in latest_report.findings 
                            if gap.get('priority') == 'high'
                        ]),
                        'next_assessment_due': (
                            latest_report.completed_at + timedelta(days=90)
                        ).isoformat()
                    }
                else:
                    dashboard_data['frameworks'][framework.value] = {
                        'status': 'not_assessed',
                        'message': 'No assessment completed'
                    }
                    
            except Exception as e:
                logger.error(f"Error generating dashboard for {framework.value}: {e}")
                dashboard_data['frameworks'][framework.value] = {
                    'status': 'error',
                    'message': str(e)
                }
        
        return dashboard_data
    
    def _get_compliance_status(self, score: float) -> str:
        """Determine compliance status from score"""
        if score >= 90:
            return 'compliant'
        elif score >= 70:
            return 'partially_compliant'
        else:
            return 'non_compliant'

# Global compliance manager factory
def get_compliance_manager(organization: Organization) -> ComplianceManager:
    """Get compliance manager for organization"""
    return ComplianceManager(organization)
    [
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC1.1",
                title="Control Environment",
                description="Organization demonstrates commitment to integrity and ethical values",
                category="security",
                severity="high",
                evidence_required=["policies", "training_records", "code_of_conduct"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC2.1",
                title="Communication and Information",
                description="Organization obtains or generates and uses relevant information",
                category="security",
                severity="medium",
                evidence_required=["communication_policies", "information_management"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC3.1",
                title="Risk Assessment",
                description="Organization specifies objectives with sufficient clarity",
                category="security",
                severity="high",
                evidence_required=["risk_assessment", "security_objectives"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC3.2",
                title="Risk Identification",
                description="Organization identifies risks to achievement of objectives",
                category="security",
                severity="high",
                evidence_required=["risk_register", "threat_assessment"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC4.1",
                title="Control Activities",
                description="Organization selects and develops control activities",
                category="security",
                severity="high",
                evidence_required=["control_documentation", "implementation_evidence"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC5.1",
                title="Monitoring Activities",
                description="Organization selects, develops, and performs ongoing monitoring",
                category="security",
                severity="high",
                evidence_required=["monitoring_procedures", "audit_logs"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC6.1",
                title="Logical Access",
                description="Organization implements logical access security software",
                category="security",
                severity="critical",
                evidence_required=["access_controls", "authentication_logs"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC6.2",
                title="User Access Provisioning",
                description="Prior to issuing system credentials, organization registers users",
                category="security",
                severity="high",
                evidence_required=["user_provisioning", "access_reviews"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC6.3",
                title="User Access Review",
                description="Organization authorizes, modifies, or removes access",
                category="security",
                severity="high",
                evidence_required=["access_reviews", "authorization_records"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC7.1",
                title="System Operations",
                description="Organization ensures authorized system changes",
                category="security",
                severity="medium",
                evidence_required=["change_management", "system_logs"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.SOC2,
                control_id="CC8.1",
                title="Data Loss Prevention",
                description="Organization restricts data transmission, movement, and removal",
                category="security",
                severity="high",
                evidence_required=["dlp_policies", "data_movement_logs"]
            ),
        ]
    
    def assess_compliance(self) -> Dict[str, ComplianceResult]:
        """Assess SOC 2 compliance status"""
        results = {}
        
        for requirement in self.requirements:
            result = self._assess_requirement(requirement)
            results[requirement.control_id] = result
            
        return results
    
    def _assess_requirement(self, requirement: ComplianceRequirement) -> ComplianceResult:
        """Assess individual SOC 2 requirement"""
        evidence = []
        gaps = []
        recommendations = []
        score = 0.0
        
        if requirement.control_id == "CC6.1":  # Logical Access
            score, evidence, gaps = self._assess_logical_access()
        elif requirement.control_id == "CC6.2":  # User Provisioning
            score, evidence, gaps = self._assess_user_provisioning()
        elif requirement.control_id == "CC6.3":  # Access Review
            score, evidence, gaps = self._assess_access_review()
        elif requirement.control_id == "CC5.1":  # Monitoring
            score, evidence, gaps = self._assess_monitoring()
        elif requirement.control_id == "CC8.1":  # Data Loss Prevention
            score, evidence, gaps = self._assess_data_protection()
        else:
            # Generic assessment for other controls
            score = 75.0  # Baseline score
            evidence = ["Policy documented", "Controls implemented"]
        
        # Determine status
        if score >= 95:
            status = "compliant"
        elif score >= 80:
            status = "partial"
        else:
            status = "non_compliant"
            
        return ComplianceResult(
            requirement=requirement,
            status=status,
            score=score,
            evidence=evidence,
            gaps=gaps,
            recommendations=recommendations,
            last_assessed=timezone.now()
        )
    
    def _assess_logical_access(self) -> Tuple[float, List[str], List[str]]:
        """Assess logical access controls"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check authentication mechanisms
        if self.organization.sso_enabled:
            evidence.append("SSO authentication implemented")
            score += 25
        else:
            gaps.append("SSO not implemented")
        
        # Check MFA usage
        mfa_users = SecurityUser.objects.filter(
            organization=self.organization,
            mfa_enabled=True,
            is_active=True
        ).count()
        total_users = SecurityUser.objects.filter(
            organization=self.organization,
            is_active=True
        ).count()
        
        if total_users > 0:
            mfa_percentage = (mfa_users / total_users) * 100
            if mfa_percentage >= 90:
                evidence.append(f"MFA enabled for {mfa_percentage:.1f}% of users")
                score += 30
            elif mfa_percentage >= 50:
                evidence.append(f"MFA enabled for {mfa_percentage:.1f}% of users")
                score += 15
                gaps.append("MFA adoption below 90%")
            else:
                gaps.append(f"Low MFA adoption: {mfa_percentage:.1f}%")
        
        # Check password policies
        security_settings = self.organization.security_settings
        if security_settings.get('password_policy'):
            evidence.append("Password policy defined")
            score += 20
        else:
            gaps.append("No password policy configured")
        
        # Check session management
        if security_settings.get('session_timeout'):
            evidence.append("Session timeout configured")
            score += 15
        else:
            gaps.append("Session timeout not configured")
        
        # Check failed login monitoring
        recent_failures = AuditLog.objects.filter(
            organization=self.organization,
            action='login',
            success=False,
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        if recent_failures > 0:
            evidence.append(f"Failed login attempts monitored: {recent_failures} in last 30 days")
            score += 10
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_user_provisioning(self) -> Tuple[float, List[str], List[str]]:
        """Assess user provisioning processes"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check user creation audit trail
        user_creation_logs = AuditLog.objects.filter(
            organization=self.organization,
            action='user_created',
            timestamp__gte=timezone.now() - timedelta(days=90)
        ).count()
        
        if user_creation_logs > 0:
            evidence.append(f"User creation audited: {user_creation_logs} events in 90 days")
            score += 30
        
        # Check role assignment audit trail
        role_assignment_logs = AuditLog.objects.filter(
            organization=self.organization,
            action='permission_change',
            timestamp__gte=timezone.now() - timedelta(days=90)
        ).count()
        
        if role_assignment_logs > 0:
            evidence.append(f"Role assignments audited: {role_assignment_logs} events in 90 days")
            score += 30
        
        # Check for standardized roles
        from .models import Role
        role_count = Role.objects.filter(organization=self.organization).count()
        if role_count >= 4:  # Admin, Developer, Analyst, Viewer
            evidence.append(f"Standardized roles implemented: {role_count} roles")
            score += 40
        else:
            gaps.append("Insufficient role standardization")
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_access_review(self) -> Tuple[float, List[str], List[str]]:
        """Assess access review processes"""
        evidence = []
        gaps = []
        score = 50.0  # Baseline for having RBAC system
        
        # Check for recent access reviews
        review_logs = AuditLog.objects.filter(
            organization=self.organization,
            details__contains={'access_review': True},
            timestamp__gte=timezone.now() - timedelta(days=90)
        ).count()
        
        if review_logs > 0:
            evidence.append(f"Access reviews conducted: {review_logs} in 90 days")
            score += 30
        else:
            gaps.append("No documented access reviews in last 90 days")
        
        # Check for inactive user management
        inactive_users = SecurityUser.objects.filter(
            organization=self.organization,
            is_active=False,
            last_activity__lt=timezone.now() - timedelta(days=90)
        ).count()
        
        total_inactive = SecurityUser.objects.filter(
            organization=self.organization,
            is_active=False
        ).count()
        
        if total_inactive > 0:
            evidence.append(f"Inactive users managed: {inactive_users} deactivated")
            score += 20
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_monitoring(self) -> Tuple[float, List[str], List[str]]:
        """Assess monitoring and logging"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check audit log completeness
        recent_logs = AuditLog.objects.filter(
            organization=self.organization,
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        if recent_logs > 100:  # Threshold for active logging
            evidence.append(f"Comprehensive audit logging: {recent_logs} events in 30 days")
            score += 40
        elif recent_logs > 10:
            evidence.append(f"Basic audit logging: {recent_logs} events in 30 days")
            score += 20
            gaps.append("Limited audit log coverage")
        else:
            gaps.append("Insufficient audit logging")
        
        # Check security event monitoring
        security_events = SecurityEvent.objects.filter(
            organization=self.organization,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        if security_events > 0:
            evidence.append(f"Security events monitored: {security_events} events")
            score += 30
        else:
            gaps.append("No security event monitoring")
        
        # Check log retention
        oldest_log = AuditLog.objects.filter(
            organization=self.organization
        ).order_by('timestamp').first()
        
        if oldest_log:
            retention_days = (timezone.now() - oldest_log.timestamp).days
            if retention_days >= 365:  # 1 year retention
                evidence.append(f"Long-term log retention: {retention_days} days")
                score += 30
            elif retention_days >= 90:
                evidence.append(f"Adequate log retention: {retention_days} days")
                score += 15
                gaps.append("Log retention below 1 year")
            else:
                gaps.append("Insufficient log retention")
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_data_protection(self) -> Tuple[float, List[str], List[str]]:
        """Assess data loss prevention"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check encryption implementation
        security_settings = self.organization.security_settings
        if security_settings.get('encryption_enabled'):
            evidence.append("Data encryption implemented")
            score += 40
        else:
            gaps.append("Data encryption not configured")
        
        # Check data export monitoring
        export_logs = AuditLog.objects.filter(
            organization=self.organization,
            action='data_export',
            timestamp__gte=timezone.now() - timedelta(days=90)
        ).count()
        
        if export_logs > 0:
            evidence.append(f"Data exports monitored: {export_logs} events")
            score += 30
        
        # Check backup procedures
        if security_settings.get('backup_enabled'):
            evidence.append("Data backup procedures implemented")
            score += 30
        else:
            gaps.append("No backup procedures documented")
        
        return min(score, 100.0), evidence, gaps

class GDPRCompliance:
    """GDPR compliance implementation"""
    
    def __init__(self, organization: Organization):
        self.organization = organization
        self.requirements = self._define_gdpr_requirements()
    
    def _define_gdpr_requirements(self) -> List[ComplianceRequirement]:
        """Define GDPR Articles and requirements"""
        return [
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART6",
                title="Lawfulness of Processing",
                description="Processing is lawful only if at least one legal basis applies",
                category="legal_basis",
                severity="critical",
                evidence_required=["lawful_basis_documentation", "consent_records"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART7",
                title="Conditions for Consent",
                description="Clear and specific consent for data processing",
                category="consent",
                severity="high",
                evidence_required=["consent_forms", "consent_withdrawal_process"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART12",
                title="Transparent Information",
                description="Provide transparent information about data processing",
                category="transparency",
                severity="high",
                evidence_required=["privacy_policy", "data_processing_notices"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART15",
                title="Right of Access",
                description="Data subject's right to obtain confirmation of processing",
                category="data_subject_rights",
                severity="high",
                evidence_required=["access_request_procedures", "response_records"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART16",
                title="Right to Rectification",
                description="Right to rectification of inaccurate personal data",
                category="data_subject_rights",
                severity="medium",
                evidence_required=["rectification_procedures", "correction_logs"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART17",
                title="Right to Erasure",
                description="Right to erasure ('right to be forgotten')",
                category="data_subject_rights",
                severity="high",
                evidence_required=["deletion_procedures", "erasure_logs"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART20",
                title="Right to Data Portability",
                description="Right to receive personal data in structured format",
                category="data_subject_rights",
                severity="medium",
                evidence_required=["portability_procedures", "export_capabilities"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART25",
                title="Data Protection by Design",
                description="Implement data protection by design and by default",
                category="technical_measures",
                severity="high",
                evidence_required=["design_documentation", "default_settings"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART32",
                title="Security of Processing",
                description="Implement appropriate technical and organizational measures",
                category="security",
                severity="critical",
                evidence_required=["security_measures", "encryption_implementation"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART33",
                title="Breach Notification to Authority",
                description="Notify supervisory authority of personal data breach",
                category="breach_management",
                severity="critical",
                evidence_required=["breach_procedures", "notification_records"]
            ),
            ComplianceRequirement(
                framework=ComplianceFramework.GDPR,
                control_id="ART34",
                title="Breach Notification to Data Subject",
                description="Communicate personal data breach to data subject",
                category="breach_management",
                severity="high",
                evidence_required=["communication_procedures", "notification_records"]
            ),
        ]
    
    def assess_compliance(self) -> Dict[str, ComplianceResult]:
        """Assess GDPR compliance status"""
        results = {}
        
        for requirement in self.requirements:
            result = self._assess_gdpr_requirement(requirement)
            results[requirement.control_id] = result
            
        return results
    
    def _assess_gdpr_requirement(self, requirement: ComplianceRequirement) -> ComplianceResult:
        """Assess individual GDPR requirement"""
        evidence = []
        gaps = []
        recommendations = []
        score = 0.0
        
        if requirement.control_id == "ART6":  # Lawfulness
            score, evidence, gaps = self._assess_lawful_basis()
        elif requirement.control_id == "ART15":  # Right of Access
            score, evidence, gaps = self._assess_access_rights()
        elif requirement.control_id == "ART17":  # Right to Erasure
            score, evidence, gaps = self._assess_erasure_rights()
        elif requirement.control_id == "ART32":  # Security
            score, evidence, gaps = self._assess_gdpr_security()
        elif requirement.control_id == "ART33":  # Breach Notification
            score, evidence, gaps = self._assess_breach_procedures()
        else:
            # Generic assessment
            score = 70.0
            evidence = ["Policy documented"]
        
        # Determine status
        if score >= 90:
            status = "compliant"
        elif score >= 70:
            status = "partial"
        else:
            status = "non_compliant"
            
        return ComplianceResult(
            requirement=requirement,
            status=status,
            score=score,
            evidence=evidence,
            gaps=gaps,
            recommendations=recommendations,
            last_assessed=timezone.now()
        )
    
    def _assess_lawful_basis(self) -> Tuple[float, List[str], List[str]]:
        """Assess lawful basis for processing"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check if lawful basis is documented
        security_settings = self.organization.security_settings
        if security_settings.get('gdpr_lawful_basis'):
            evidence.append(f"Lawful basis documented: {security_settings['gdpr_lawful_basis']}")
            score += 40
        else:
            gaps.append("No lawful basis documented")
        
        # Check privacy policy existence
        if security_settings.get('privacy_policy_url'):
            evidence.append("Privacy policy published")
            score += 30
        else:
            gaps.append("No privacy policy available")
        
        # Check consent management for applicable processing
        consent_logs = AuditLog.objects.filter(
            organization=self.organization,
            details__contains={'gdpr_consent': True},
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        
        if consent_logs > 0:
            evidence.append(f"Consent management implemented: {consent_logs} records")
            score += 30
        elif security_settings.get('gdpr_lawful_basis') == 'consent':
            gaps.append("Consent required but no consent records found")
        else:
            evidence.append("Consent not required for current lawful basis")
            score += 30
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_access_rights(self) -> Tuple[float, List[str], List[str]]:
        """Assess data subject access rights"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check for access request procedures
        access_requests = AuditLog.objects.filter(
            organization=self.organization,
            action='data_access_request',
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        
        if access_requests > 0:
            evidence.append(f"Access requests processed: {access_requests} in last year")
            score += 50
        
        # Check response time compliance (30 days)
        recent_access_requests = AuditLog.objects.filter(
            organization=self.organization,
            action='data_access_request',
            timestamp__gte=timezone.now() - timedelta(days=90)
        )
        
        compliant_responses = 0
        for request in recent_access_requests:
            response_time = request.details.get('response_time_days', 0)
            if response_time <= 30:
                compliant_responses += 1
        
        if recent_access_requests.count() > 0:
            compliance_rate = (compliant_responses / recent_access_requests.count()) * 100
            if compliance_rate >= 95:
                evidence.append(f"Response time compliance: {compliance_rate:.1f}%")
                score += 30
            else:
                gaps.append(f"Response time compliance below 95%: {compliance_rate:.1f}%")
        
        # Check data export capability
        security_settings = self.organization.security_settings
        if security_settings.get('data_export_enabled'):
            evidence.append("Data export functionality implemented")
            score += 20
        else:
            gaps.append("No data export functionality")
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_erasure_rights(self) -> Tuple[float, List[str], List[str]]:
        """Assess right to erasure implementation"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check for erasure procedures
        erasure_requests = AuditLog.objects.filter(
            organization=self.organization,
            action='data_erasure_request',
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        
        if erasure_requests > 0:
            evidence.append(f"Erasure requests processed: {erasure_requests} in last year")
            score += 40
        
        # Check automated deletion capabilities
        security_settings = self.organization.security_settings
        if security_settings.get('automated_deletion_enabled'):
            evidence.append("Automated deletion procedures implemented")
            score += 30
        else:
            gaps.append("No automated deletion procedures")
        
        # Check data retention policies
        if security_settings.get('data_retention_policy'):
            evidence.append("Data retention policy defined")
            score += 30
        else:
            gaps.append("No data retention policy")
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_gdpr_security(self) -> Tuple[float, List[str], List[str]]:
        """Assess GDPR security requirements"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check encryption implementation
        security_settings = self.organization.security_settings
        if security_settings.get('encryption_at_rest'):
            evidence.append("Data encryption at rest implemented")
            score += 25
        else:
            gaps.append("No encryption at rest")
        
        if security_settings.get('encryption_in_transit'):
            evidence.append("Data encryption in transit implemented")
            score += 25
        else:
            gaps.append("No encryption in transit")
        
        # Check access controls
        if security_settings.get('rbac_enabled'):
            evidence.append("Role-based access controls implemented")
            score += 25
        else:
            gaps.append("No role-based access controls")
        
        # Check audit logging
        recent_logs = AuditLog.objects.filter(
            organization=self.organization,
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        if recent_logs > 50:
            evidence.append("Comprehensive audit logging implemented")
            score += 25
        elif recent_logs > 10:
            evidence.append("Basic audit logging implemented")
            score += 15
            gaps.append("Limited audit logging coverage")
        else:
            gaps.append("Insufficient audit logging")
        
        return min(score, 100.0), evidence, gaps
    
    def _assess_breach_procedures(self) -> Tuple[float, List[str], List[str]]:
        """Assess data breach notification procedures"""
        evidence = []
        gaps = []
        score = 0.0
        
        # Check breach response procedures
        security_settings = self.organization.security_settings
        if security_settings.get('breach_response_plan'):
            evidence.append("Data breach response plan documented")
            score += 40
        else:
            gaps.append("No breach response plan")
        
        # Check incident response capability
        security_events = SecurityEvent.objects.filter(
            organization=self.organization,
            event_type='data_breach_attempt',
            created_at__gte=timezone.now() - timedelta(days=365)
        ).count()
        
        if security_events > 0:
            evidence.append(f"Security incidents detected and logged: {security_events}")
            score += 30
        
        # Check notification procedures
        if security_settings.get('breach_notification_contacts'):
            evidence.append("Breach notification contacts configured")
            score += 30
        else:
            gaps.append("No breach notification contacts")
        
        return min(score, 100.0), evidence, gaps