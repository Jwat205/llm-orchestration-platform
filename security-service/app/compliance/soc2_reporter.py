"""
SOC2 Compliance Reporter
Generates SOC2 compliance reports and evidence collection
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging


logger = logging.getLogger(__name__)


class SOC2TrustServiceCriteria(Enum):
    """SOC2 Trust Service Criteria"""
    SECURITY = "security"
    AVAILABILITY = "availability"
    PROCESSING_INTEGRITY = "processing_integrity"
    CONFIDENTIALITY = "confidentiality"
    PRIVACY = "privacy"


class ComplianceStatus(Enum):
    """Compliance status levels"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_ASSESSED = "not_assessed"


@dataclass
class ControlEvidence:
    """Evidence for a control"""
    control_id: str
    evidence_type: str
    description: str
    collected_at: datetime
    evidence_data: Dict[str, Any]
    assessment_period: str
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['collected_at'] = self.collected_at.isoformat()
        return data


@dataclass
class ControlAssessment:
    """Assessment of a control"""
    control_id: str
    control_name: str
    criteria: SOC2TrustServiceCriteria
    status: ComplianceStatus
    last_assessed: datetime
    evidence: List[ControlEvidence]
    gaps: List[str]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['criteria'] = self.criteria.value
        data['status'] = self.status.value
        data['last_assessed'] = self.last_assessed.isoformat()
        data['evidence'] = [e.to_dict() for e in self.evidence]
        return data


class SecurityControlsAssessor:
    """Assesses security controls for SOC2 compliance"""
    
    def __init__(self):
        self.control_assessments: Dict[str, ControlAssessment] = {}
        self.evidence_store: List[ControlEvidence] = []
    
    def assess_access_controls(self, access_logs: List[Dict[str, Any]]) -> ControlAssessment:
        """Assess logical access controls"""
        control_id = "CC6.1"
        evidence = []
        gaps = []
        recommendations = []
        
        # Check for multi-factor authentication
        mfa_enabled_logins = sum(1 for log in access_logs if log.get('mfa_verified', False))
        total_logins = len(access_logs)
        mfa_percentage = (mfa_enabled_logins / total_logins * 100) if total_logins > 0 else 0
        
        evidence.append(ControlEvidence(
            control_id=control_id,
            evidence_type="access_logs",
            description="Multi-factor authentication usage analysis",
            collected_at=datetime.utcnow(),
            evidence_data={
                'total_logins': total_logins,
                'mfa_enabled_logins': mfa_enabled_logins,
                'mfa_percentage': mfa_percentage
            },
            assessment_period="current"
        ))
        
        # Determine compliance status
        if mfa_percentage >= 95:
            status = ComplianceStatus.COMPLIANT
        elif mfa_percentage >= 80:
            status = ComplianceStatus.PARTIALLY_COMPLIANT
            gaps.append("MFA not enforced for all users")
            recommendations.append("Implement mandatory MFA for all user accounts")
        else:
            status = ComplianceStatus.NON_COMPLIANT
            gaps.append("Insufficient MFA coverage")
            recommendations.append("Implement comprehensive MFA enforcement")
        
        assessment = ControlAssessment(
            control_id=control_id,
            control_name="Logical Access Controls",
            criteria=SOC2TrustServiceCriteria.SECURITY,
            status=status,
            last_assessed=datetime.utcnow(),
            evidence=evidence,
            gaps=gaps,
            recommendations=recommendations
        )
        
        self.control_assessments[control_id] = assessment
        return assessment
    
    def assess_encryption_controls(self, encryption_status: Dict[str, Any]) -> ControlAssessment:
        """Assess encryption controls"""
        control_id = "CC6.7"
        evidence = []
        gaps = []
        recommendations = []
        
        # Check data at rest encryption
        data_at_rest_encrypted = encryption_status.get('data_at_rest_encrypted', False)
        data_in_transit_encrypted = encryption_status.get('data_in_transit_encrypted', False)
        encryption_strength = encryption_status.get('encryption_strength', 'unknown')
        
        evidence.append(ControlEvidence(
            control_id=control_id,
            evidence_type="encryption_assessment",
            description="Data encryption implementation review",
            collected_at=datetime.utcnow(),
            evidence_data=encryption_status,
            assessment_period="current"
        ))
        
        # Determine compliance status
        if data_at_rest_encrypted and data_in_transit_encrypted and encryption_strength in ['AES-256', 'RSA-2048']:
            status = ComplianceStatus.COMPLIANT
        elif data_at_rest_encrypted or data_in_transit_encrypted:
            status = ComplianceStatus.PARTIALLY_COMPLIANT
            if not data_at_rest_encrypted:
                gaps.append("Data at rest not encrypted")
                recommendations.append("Implement encryption for data at rest")
            if not data_in_transit_encrypted:
                gaps.append("Data in transit not encrypted")
                recommendations.append("Implement TLS encryption for data in transit")
        else:
            status = ComplianceStatus.NON_COMPLIANT
            gaps.append("No encryption implemented")
            recommendations.append("Implement comprehensive encryption strategy")
        
        assessment = ControlAssessment(
            control_id=control_id,
            control_name="Data Encryption",
            criteria=SOC2TrustServiceCriteria.CONFIDENTIALITY,
            status=status,
            last_assessed=datetime.utcnow(),
            evidence=evidence,
            gaps=gaps,
            recommendations=recommendations
        )
        
        self.control_assessments[control_id] = assessment
        return assessment
    
    def assess_monitoring_controls(self, monitoring_data: Dict[str, Any]) -> ControlAssessment:
        """Assess system monitoring controls"""
        control_id = "CC7.1"
        evidence = []
        gaps = []
        recommendations = []
        
        # Check monitoring coverage
        monitoring_enabled = monitoring_data.get('monitoring_enabled', False)
        log_retention_days = monitoring_data.get('log_retention_days', 0)
        alerting_configured = monitoring_data.get('alerting_configured', False)
        incident_response_time = monitoring_data.get('avg_incident_response_time_hours', 0)
        
        evidence.append(ControlEvidence(
            control_id=control_id,
            evidence_type="monitoring_assessment",
            description="System monitoring and logging review",
            collected_at=datetime.utcnow(),
            evidence_data=monitoring_data,
            assessment_period="current"
        ))
        
        # Determine compliance status
        compliance_score = 0
        if monitoring_enabled:
            compliance_score += 25
        else:
            gaps.append("System monitoring not enabled")
            recommendations.append("Implement comprehensive system monitoring")
        
        if log_retention_days >= 90:
            compliance_score += 25
        else:
            gaps.append(f"Log retention period too short: {log_retention_days} days")
            recommendations.append("Implement 90+ day log retention policy")
        
        if alerting_configured:
            compliance_score += 25
        else:
            gaps.append("Security alerting not configured")
            recommendations.append("Configure automated security alerts")
        
        if incident_response_time <= 4:
            compliance_score += 25
        else:
            gaps.append(f"Incident response time too slow: {incident_response_time} hours")
            recommendations.append("Improve incident response procedures")
        
        if compliance_score >= 75:
            status = ComplianceStatus.COMPLIANT
        elif compliance_score >= 50:
            status = ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            status = ComplianceStatus.NON_COMPLIANT
        
        assessment = ControlAssessment(
            control_id=control_id,
            control_name="System Monitoring",
            criteria=SOC2TrustServiceCriteria.SECURITY,
            status=status,
            last_assessed=datetime.utcnow(),
            evidence=evidence,
            gaps=gaps,
            recommendations=recommendations
        )
        
        self.control_assessments[control_id] = assessment
        return assessment


class AvailabilityAssessor:
    """Assesses availability controls"""
    
    def assess_system_availability(self, uptime_data: Dict[str, Any]) -> ControlAssessment:
        """Assess system availability controls"""
        control_id = "A1.1"
        evidence = []
        gaps = []
        recommendations = []
        
        # Check uptime metrics
        uptime_percentage = uptime_data.get('uptime_percentage', 0)
        planned_downtime_hours = uptime_data.get('planned_downtime_hours', 0)
        unplanned_downtime_hours = uptime_data.get('unplanned_downtime_hours', 0)
        backup_procedures = uptime_data.get('backup_procedures_tested', False)
        
        evidence.append(ControlEvidence(
            control_id=control_id,
            evidence_type="availability_metrics",
            description="System availability and uptime analysis",
            collected_at=datetime.utcnow(),
            evidence_data=uptime_data,
            assessment_period="monthly"
        ))
        
        # Determine compliance status
        if uptime_percentage >= 99.9 and backup_procedures:
            status = ComplianceStatus.COMPLIANT
        elif uptime_percentage >= 99.5:
            status = ComplianceStatus.PARTIALLY_COMPLIANT
            if unplanned_downtime_hours > 8:
                gaps.append("Excessive unplanned downtime")
                recommendations.append("Improve system reliability and redundancy")
            if not backup_procedures:
                gaps.append("Backup procedures not tested")
                recommendations.append("Implement regular backup testing")
        else:
            status = ComplianceStatus.NON_COMPLIANT
            gaps.append("Insufficient system availability")
            recommendations.append("Implement high availability architecture")
        
        assessment = ControlAssessment(
            control_id=control_id,
            control_name="System Availability",
            criteria=SOC2TrustServiceCriteria.AVAILABILITY,
            status=status,
            last_assessed=datetime.utcnow(),
            evidence=evidence,
            gaps=gaps,
            recommendations=recommendations
        )
        
        return assessment


class ProcessingIntegrityAssessor:
    """Assesses processing integrity controls"""
    
    def assess_data_processing_integrity(self, processing_data: Dict[str, Any]) -> ControlAssessment:
        """Assess data processing integrity controls"""
        control_id = "PI1.1"
        evidence = []
        gaps = []
        recommendations = []
        
        # Check data validation
        input_validation = processing_data.get('input_validation_enabled', False)
        data_checksums = processing_data.get('data_integrity_checks', False)
        error_handling = processing_data.get('error_handling_implemented', False)
        audit_trails = processing_data.get('processing_audit_trails', False)
        
        evidence.append(ControlEvidence(
            control_id=control_id,
            evidence_type="processing_integrity",
            description="Data processing integrity controls review",
            collected_at=datetime.utcnow(),
            evidence_data=processing_data,
            assessment_period="current"
        ))
        
        # Calculate compliance score
        compliance_score = 0
        if input_validation:
            compliance_score += 25
        else:
            gaps.append("Input validation not implemented")
            recommendations.append("Implement comprehensive input validation")
        
        if data_checksums:
            compliance_score += 25
        else:
            gaps.append("Data integrity checks not implemented")
            recommendations.append("Implement data integrity verification")
        
        if error_handling:
            compliance_score += 25
        else:
            gaps.append("Error handling not comprehensive")
            recommendations.append("Improve error handling procedures")
        
        if audit_trails:
            compliance_score += 25
        else:
            gaps.append("Processing audit trails incomplete")
            recommendations.append("Implement comprehensive audit logging")
        
        if compliance_score >= 75:
            status = ComplianceStatus.COMPLIANT
        elif compliance_score >= 50:
            status = ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            status = ComplianceStatus.NON_COMPLIANT
        
        assessment = ControlAssessment(
            control_id=control_id,
            control_name="Data Processing Integrity",
            criteria=SOC2TrustServiceCriteria.PROCESSING_INTEGRITY,
            status=status,
            last_assessed=datetime.utcnow(),
            evidence=evidence,
            gaps=gaps,
            recommendations=recommendations
        )
        
        return assessment


class SOC2Reporter:
    """Main SOC2 compliance reporter"""
    
    def __init__(self):
        self.security_assessor = SecurityControlsAssessor()
        self.availability_assessor = AvailabilityAssessor()
        self.processing_integrity_assessor = ProcessingIntegrityAssessor()
        self.assessment_history: List[Dict[str, Any]] = []
    
    def run_comprehensive_assessment(self, 
                                   access_logs: List[Dict[str, Any]],
                                   encryption_status: Dict[str, Any],
                                   monitoring_data: Dict[str, Any],
                                   uptime_data: Dict[str, Any],
                                   processing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run comprehensive SOC2 assessment"""
        
        assessments = []
        
        # Security assessments
        assessments.append(self.security_assessor.assess_access_controls(access_logs))
        assessments.append(self.security_assessor.assess_encryption_controls(encryption_status))
        assessments.append(self.security_assessor.assess_monitoring_controls(monitoring_data))
        
        # Availability assessment
        assessments.append(self.availability_assessor.assess_system_availability(uptime_data))
        
        # Processing integrity assessment
        assessments.append(self.processing_integrity_assessor.assess_data_processing_integrity(processing_data))
        
        # Calculate overall compliance
        total_controls = len(assessments)
        compliant_controls = sum(1 for a in assessments if a.status == ComplianceStatus.COMPLIANT)
        partially_compliant = sum(1 for a in assessments if a.status == ComplianceStatus.PARTIALLY_COMPLIANT)
        
        overall_compliance_percentage = ((compliant_controls + (partially_compliant * 0.5)) / total_controls) * 100
        
        # Generate report
        report = {
            'report_id': f"soc2_{int(datetime.utcnow().timestamp())}",
            'generated_at': datetime.utcnow().isoformat(),
            'assessment_period': {
                'start': (datetime.utcnow() - timedelta(days=30)).isoformat(),
                'end': datetime.utcnow().isoformat()
            },
            'overall_compliance': {
                'percentage': round(overall_compliance_percentage, 2),
                'total_controls': total_controls,
                'compliant_controls': compliant_controls,
                'partially_compliant_controls': partially_compliant,
                'non_compliant_controls': total_controls - compliant_controls - partially_compliant
            },
            'criteria_summary': self._generate_criteria_summary(assessments),
            'control_assessments': [assessment.to_dict() for assessment in assessments],
            'recommendations': self._consolidate_recommendations(assessments),
            'critical_gaps': self._identify_critical_gaps(assessments)
        }
        
        # Store assessment
        self.assessment_history.append(report)
        
        logger.info(f"SOC2 assessment completed: {overall_compliance_percentage}% compliant")
        
        return report
    
    def _generate_criteria_summary(self, assessments: List[ControlAssessment]) -> Dict[str, Any]:
        """Generate summary by trust service criteria"""
        criteria_summary = {}
        
        for criteria in SOC2TrustServiceCriteria:
            criteria_assessments = [a for a in assessments if a.criteria == criteria]
            
            if criteria_assessments:
                compliant = sum(1 for a in criteria_assessments if a.status == ComplianceStatus.COMPLIANT)
                total = len(criteria_assessments)
                
                criteria_summary[criteria.value] = {
                    'total_controls': total,
                    'compliant_controls': compliant,
                    'compliance_percentage': (compliant / total) * 100 if total > 0 else 0
                }
        
        return criteria_summary
    
    def _consolidate_recommendations(self, assessments: List[ControlAssessment]) -> List[str]:
        """Consolidate recommendations from all assessments"""
        all_recommendations = []
        for assessment in assessments:
            all_recommendations.extend(assessment.recommendations)
        
        # Remove duplicates while preserving order
        unique_recommendations = []
        for rec in all_recommendations:
            if rec not in unique_recommendations:
                unique_recommendations.append(rec)
        
        return unique_recommendations
    
    def _identify_critical_gaps(self, assessments: List[ControlAssessment]) -> List[Dict[str, Any]]:
        """Identify critical compliance gaps"""
        critical_gaps = []
        
        for assessment in assessments:
            if assessment.status == ComplianceStatus.NON_COMPLIANT:
                critical_gaps.append({
                    'control_id': assessment.control_id,
                    'control_name': assessment.control_name,
                    'criteria': assessment.criteria.value,
                    'gaps': assessment.gaps
                })
        
        return critical_gaps
    
    def generate_attestation_report(self, assessment_report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate SOC2 Type II attestation report format"""
        attestation = {
            'report_type': 'SOC 2 Type II',
            'service_organization': {
                'name': 'LLM API Platform',
                'description': 'AI/ML API Services'
            },
            'report_period': assessment_report['assessment_period'],
            'trust_service_categories': list(SOC2TrustServiceCriteria.__members__.keys()),
            'management_assertion': {
                'design_effectiveness': assessment_report['overall_compliance']['percentage'] >= 80,
                'operating_effectiveness': assessment_report['overall_compliance']['percentage'] >= 75
            },
            'control_deficiencies': assessment_report['critical_gaps'],
            'recommendations': assessment_report['recommendations'],
            'independent_service_auditor_report': {
                'opinion': 'Qualified' if assessment_report['overall_compliance']['percentage'] >= 75 else 'Adverse',
                'basis_for_opinion': 'Based on automated assessment of control implementation'
            }
        }
        
        return attestation
    
    def get_compliance_trend(self, days: int = 90) -> Dict[str, Any]:
        """Get compliance trend over time"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_assessments = [
            report for report in self.assessment_history
            if datetime.fromisoformat(report['generated_at']) > cutoff
        ]
        
        if not recent_assessments:
            return {'trend': 'no_data'}
        
        # Calculate trend
        compliance_scores = [report['overall_compliance']['percentage'] for report in recent_assessments]
        
        if len(compliance_scores) < 2:
            return {'trend': 'insufficient_data', 'current_score': compliance_scores[0]}
        
        trend_direction = 'improving' if compliance_scores[-1] > compliance_scores[0] else 'declining'
        if compliance_scores[-1] == compliance_scores[0]:
            trend_direction = 'stable'
        
        return {
            'trend': trend_direction,
            'current_score': compliance_scores[-1],
            'previous_score': compliance_scores[0],
            'change': compliance_scores[-1] - compliance_scores[0],
            'assessment_count': len(compliance_scores)
        }