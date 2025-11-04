"""
Audit Log Exporter
Exports audit logs in various formats for compliance and investigation
"""

import json
import csv
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
import zipfile
import io


logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Supported export formats"""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    SIEM = "siem"
    CEF = "cef"  # Common Event Format


class AuditEventType(Enum):
    """Types of audit events"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM_CONFIGURATION = "system_configuration"
    SECURITY_EVENT = "security_event"
    ADMIN_ACTION = "admin_action"


class AuditLogExporter:
    """Main audit log exporter"""
    
    def __init__(self):
        self.audit_logs: List[Dict[str, Any]] = []
    
    def add_audit_event(self, 
                       event_type: AuditEventType,
                       user_id: str,
                       action: str,
                       resource: str,
                       ip_address: str,
                       user_agent: str = "",
                       result: str = "success",
                       details: Dict[str, Any] = None) -> str:
        """Add audit event to log"""
        
        event_id = f"{event_type.value}_{int(datetime.utcnow().timestamp())}_{len(self.audit_logs)}"
        
        audit_event = {
            'event_id': event_id,
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type.value,
            'user_id': user_id,
            'action': action,
            'resource': resource,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'result': result,
            'details': details or {}
        }
        
        self.audit_logs.append(audit_event)
        logger.info(f"Audit event recorded: {event_id}")
        
        return event_id
    
    def export_logs(self, 
                   format_type: ExportFormat,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   event_types: Optional[List[AuditEventType]] = None,
                   user_ids: Optional[List[str]] = None) -> str:
        """Export audit logs in specified format"""
        
        # Filter logs based on criteria
        filtered_logs = self._filter_logs(start_date, end_date, event_types, user_ids)
        
        if format_type == ExportFormat.JSON:
            return self._export_json(filtered_logs)
        elif format_type == ExportFormat.CSV:
            return self._export_csv(filtered_logs)
        elif format_type == ExportFormat.XML:
            return self._export_xml(filtered_logs)
        elif format_type == ExportFormat.SIEM:
            return self._export_siem(filtered_logs)
        elif format_type == ExportFormat.CEF:
            return self._export_cef(filtered_logs)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def export_compressed(self, 
                         format_type: ExportFormat,
                         **filter_kwargs) -> bytes:
        """Export logs as compressed archive"""
        
        exported_data = self.export_logs(format_type, **filter_kwargs)
        
        # Create compressed archive
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            filename = f"audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format_type.value}"
            zip_file.writestr(filename, exported_data)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    def _filter_logs(self, 
                    start_date: Optional[datetime],
                    end_date: Optional[datetime],
                    event_types: Optional[List[AuditEventType]],
                    user_ids: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Filter audit logs based on criteria"""
        
        filtered_logs = self.audit_logs.copy()
        
        # Filter by date range
        if start_date:
            filtered_logs = [
                log for log in filtered_logs
                if datetime.fromisoformat(log['timestamp']) >= start_date
            ]
        
        if end_date:
            filtered_logs = [
                log for log in filtered_logs
                if datetime.fromisoformat(log['timestamp']) <= end_date
            ]
        
        # Filter by event types
        if event_types:
            event_type_values = [et.value for et in event_types]
            filtered_logs = [
                log for log in filtered_logs
                if log['event_type'] in event_type_values
            ]
        
        # Filter by user IDs
        if user_ids:
            filtered_logs = [
                log for log in filtered_logs
                if log['user_id'] in user_ids
            ]
        
        return filtered_logs
    
    def _export_json(self, logs: List[Dict[str, Any]]) -> str:
        """Export logs as JSON"""
        export_data = {
            'export_metadata': {
                'exported_at': datetime.utcnow().isoformat(),
                'format': 'json',
                'record_count': len(logs)
            },
            'audit_logs': logs
        }
        
        return json.dumps(export_data, indent=2)
    
    def _export_csv(self, logs: List[Dict[str, Any]]) -> str:
        """Export logs as CSV"""
        if not logs:
            return "No audit logs to export"
        
        output = io.StringIO()
        
        # Define CSV columns
        fieldnames = [
            'event_id', 'timestamp', 'event_type', 'user_id', 'action',
            'resource', 'ip_address', 'user_agent', 'result', 'details'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for log in logs:
            # Flatten details for CSV export
            csv_row = log.copy()
            csv_row['details'] = json.dumps(log['details']) if log['details'] else ''
            writer.writerow(csv_row)
        
        return output.getvalue()
    
    def _export_xml(self, logs: List[Dict[str, Any]]) -> str:
        """Export logs as XML"""
        root = ET.Element('audit_logs')
        
        # Add metadata
        metadata = ET.SubElement(root, 'metadata')
        ET.SubElement(metadata, 'exported_at').text = datetime.utcnow().isoformat()
        ET.SubElement(metadata, 'format').text = 'xml'
        ET.SubElement(metadata, 'record_count').text = str(len(logs))
        
        # Add log entries
        logs_element = ET.SubElement(root, 'logs')
        
        for log in logs:
            log_element = ET.SubElement(logs_element, 'audit_event')
            
            for key, value in log.items():
                if key == 'details' and isinstance(value, dict):
                    details_element = ET.SubElement(log_element, 'details')
                    for detail_key, detail_value in value.items():
                        detail_element = ET.SubElement(details_element, 'detail')
                        detail_element.set('name', detail_key)
                        detail_element.text = str(detail_value)
                else:
                    element = ET.SubElement(log_element, key)
                    element.text = str(value) if value is not None else ''
        
        return ET.tostring(root, encoding='unicode')
    
    def _export_siem(self, logs: List[Dict[str, Any]]) -> str:
        """Export logs in SIEM-friendly format (JSON Lines)"""
        output_lines = []
        
        for log in logs:
            # Enhance log with SIEM-specific fields
            siem_log = {
                'timestamp': log['timestamp'],
                'source': 'llm_api_platform',
                'event_type': log['event_type'],
                'severity': self._get_event_severity(log),
                'user': log['user_id'],
                'source_ip': log['ip_address'],
                'action': log['action'],
                'object': log['resource'],
                'result': log['result'],
                'raw_event': log
            }
            
            output_lines.append(json.dumps(siem_log))
        
        return '\n'.join(output_lines)
    
    def _export_cef(self, logs: List[Dict[str, Any]]) -> str:
        """Export logs in Common Event Format (CEF)"""
        output_lines = []
        
        for log in logs:
            # CEF format: CEF:Version|Device Vendor|Device Product|Device Version|Device Event Class ID|Name|Severity|Extension
            cef_line = (
                f"CEF:0|LLM_API_Platform|API_Security|1.0|"
                f"{log['event_type']}|{log['action']}|"
                f"{self._get_event_severity_numeric(log)}|"
                f"rt={log['timestamp']} "
                f"src={log['ip_address']} "
                f"suser={log['user_id']} "
                f"act={log['action']} "
                f"outcome={log['result']} "
                f"request={log['resource']}"
            )
            
            output_lines.append(cef_line)
        
        return '\n'.join(output_lines)
    
    def _get_event_severity(self, log: Dict[str, Any]) -> str:
        """Determine event severity"""
        event_type = log['event_type']
        result = log['result']
        
        if event_type == AuditEventType.SECURITY_EVENT.value:
            return 'high'
        elif event_type == AuditEventType.ADMIN_ACTION.value:
            return 'medium'
        elif result == 'failure':
            return 'medium'
        else:
            return 'low'
    
    def _get_event_severity_numeric(self, log: Dict[str, Any]) -> int:
        """Get numeric severity for CEF format"""
        severity = self._get_event_severity(log)
        severity_map = {
            'low': 3,
            'medium': 6,
            'high': 9
        }
        return severity_map.get(severity, 3)
    
    def generate_audit_report(self, 
                             start_date: datetime,
                             end_date: datetime) -> Dict[str, Any]:
        """Generate comprehensive audit report"""
        
        filtered_logs = self._filter_logs(start_date, end_date, None, None)
        
        # Calculate statistics
        total_events = len(filtered_logs)
        events_by_type = {}
        events_by_user = {}
        events_by_result = {}
        failed_events = []
        
        for log in filtered_logs:
            # Count by type
            event_type = log['event_type']
            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
            
            # Count by user
            user_id = log['user_id']
            events_by_user[user_id] = events_by_user.get(user_id, 0) + 1
            
            # Count by result
            result = log['result']
            events_by_result[result] = events_by_result.get(result, 0) + 1
            
            # Collect failed events
            if result == 'failure':
                failed_events.append(log)
        
        # Generate report
        report = {
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': {
                'total_events': total_events,
                'unique_users': len(events_by_user),
                'failed_events': len(failed_events),
                'success_rate': ((total_events - len(failed_events)) / total_events * 100) if total_events > 0 else 0
            },
            'statistics': {
                'events_by_type': events_by_type,
                'events_by_user': dict(sorted(events_by_user.items(), key=lambda x: x[1], reverse=True)[:10]),
                'events_by_result': events_by_result
            },
            'security_highlights': {
                'failed_authentication_attempts': len([
                    log for log in failed_events 
                    if log['event_type'] == AuditEventType.AUTHENTICATION.value
                ]),
                'unauthorized_access_attempts': len([
                    log for log in failed_events 
                    if log['event_type'] == AuditEventType.AUTHORIZATION.value
                ]),
                'security_events': len([
                    log for log in filtered_logs 
                    if log['event_type'] == AuditEventType.SECURITY_EVENT.value
                ])
            },
            'compliance_indicators': {
                'data_access_logged': len([
                    log for log in filtered_logs 
                    if log['event_type'] == AuditEventType.DATA_ACCESS.value
                ]),
                'admin_actions_logged': len([
                    log for log in filtered_logs 
                    if log['event_type'] == AuditEventType.ADMIN_ACTION.value
                ]),
                'configuration_changes': len([
                    log for log in filtered_logs 
                    if log['event_type'] == AuditEventType.SYSTEM_CONFIGURATION.value
                ])
            },
            'generated_at': datetime.utcnow().isoformat()
        }
        
        return report
    
    def search_logs(self, 
                   query: str,
                   search_fields: List[str] = None) -> List[Dict[str, Any]]:
        """Search audit logs"""
        
        if not search_fields:
            search_fields = ['action', 'resource', 'user_id', 'ip_address']
        
        matching_logs = []
        query_lower = query.lower()
        
        for log in self.audit_logs:
            match_found = False
            
            for field in search_fields:
                if field in log and query_lower in str(log[field]).lower():
                    match_found = True
                    break
                
                # Search in details
                if field == 'details' and log['details']:
                    for detail_value in log['details'].values():
                        if query_lower in str(detail_value).lower():
                            match_found = True
                            break
            
            if match_found:
                matching_logs.append(log)
        
        return matching_logs
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get overall log statistics"""
        
        if not self.audit_logs:
            return {'total_logs': 0}
        
        # Calculate date range
        timestamps = [datetime.fromisoformat(log['timestamp']) for log in self.audit_logs]
        earliest = min(timestamps)
        latest = max(timestamps)
        
        # Count by event type
        event_type_counts = {}
        for log in self.audit_logs:
            event_type = log['event_type']
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        return {
            'total_logs': len(self.audit_logs),
            'date_range': {
                'earliest': earliest.isoformat(),
                'latest': latest.isoformat(),
                'span_days': (latest - earliest).days
            },
            'event_type_distribution': event_type_counts,
            'unique_users': len(set(log['user_id'] for log in self.audit_logs)),
            'unique_ip_addresses': len(set(log['ip_address'] for log in self.audit_logs))
        }