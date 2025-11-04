"""
Security Scanner
Performs automated security scanning and vulnerability detection
"""

import re
import hashlib
import hmac
import socket
import ssl
import subprocess
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging
import requests
from urllib.parse import urljoin, urlparse
import dns.resolver
import nmap


logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """Security issue severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ScanType(Enum):
    """Types of security scans"""
    VULNERABILITY = "vulnerability"
    PORT_SCAN = "port_scan"
    SSL_CHECK = "ssl_check"
    DNS_CHECK = "dns_check"
    WEB_SCAN = "web_scan"
    CODE_SCAN = "code_scan"
    DEPENDENCY_SCAN = "dependency_scan"


@dataclass
class SecurityFinding:
    """Security finding data class"""
    id: str
    scan_type: ScanType
    severity: SeverityLevel
    title: str
    description: str
    affected_resource: str
    recommendation: str
    evidence: Dict[str, Any]
    timestamp: datetime
    cvss_score: Optional[float] = None
    cve_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['scan_type'] = self.scan_type.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


class VulnerabilityScanner:
    """Generic vulnerability scanner"""
    
    def __init__(self):
        self.findings: List[SecurityFinding] = []
        self.scan_id = None
    
    def generate_finding_id(self) -> str:
        """Generate unique finding ID"""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        return f"{self.scan_id}_{timestamp}_{len(self.findings)}"
    
    def add_finding(self, 
                   scan_type: ScanType,
                   severity: SeverityLevel,
                   title: str,
                   description: str,
                   affected_resource: str,
                   recommendation: str,
                   evidence: Dict[str, Any],
                   cvss_score: Optional[float] = None,
                   cve_id: Optional[str] = None):
        """Add a security finding"""
        finding = SecurityFinding(
            id=self.generate_finding_id(),
            scan_type=scan_type,
            severity=severity,
            title=title,
            description=description,
            affected_resource=affected_resource,
            recommendation=recommendation,
            evidence=evidence,
            timestamp=datetime.utcnow(),
            cvss_score=cvss_score,
            cve_id=cve_id
        )
        
        self.findings.append(finding)
        logger.info(f"Security finding added: {finding.id} - {finding.title}")


class PortScanner(VulnerabilityScanner):
    """Network port scanner"""
    
    def __init__(self):
        super().__init__()
        self.scan_id = "port_scan"
        self.nm = nmap.PortScanner()
    
    def scan_host(self, host: str, port_range: str = "1-1000") -> List[SecurityFinding]:
        """Scan host for open ports"""
        try:
            logger.info(f"Starting port scan of {host}:{port_range}")
            
            self.nm.scan(host, port_range, arguments='-sS -O -A')
            
            for host_ip in self.nm.all_hosts():
                host_info = self.nm[host_ip]
                
                # Check for open ports
                for protocol in host_info.all_protocols():
                    ports = host_info[protocol].keys()
                    
                    for port in ports:
                        port_info = host_info[protocol][port]
                        state = port_info['state']
                        
                        if state == 'open':
                            service = port_info.get('name', 'unknown')
                            version = port_info.get('version', '')
                            product = port_info.get('product', '')
                            
                            severity = self._assess_port_risk(port, service)
                            
                            self.add_finding(
                                scan_type=ScanType.PORT_SCAN,
                                severity=severity,
                                title=f"Open Port Detected: {port}/{protocol}",
                                description=f"Port {port} is open and running {service}",
                                affected_resource=f"{host}:{port}",
                                recommendation=self._get_port_recommendation(port, service),
                                evidence={
                                    'port': port,
                                    'protocol': protocol,
                                    'service': service,
                                    'version': version,
                                    'product': product,
                                    'state': state
                                }
                            )
            
            return self.findings
            
        except Exception as e:
            logger.error(f"Port scan failed for {host}: {e}")
            return []
    
    def _assess_port_risk(self, port: int, service: str) -> SeverityLevel:
        """Assess risk level for open port"""
        # High-risk ports
        high_risk_ports = [21, 22, 23, 135, 139, 445, 1433, 3389, 5432, 5984, 6379]
        # Medium-risk ports
        medium_risk_ports = [25, 53, 110, 143, 993, 995]
        # Common web ports (lower risk if properly configured)
        web_ports = [80, 443, 8080, 8443]
        
        if port in high_risk_ports:
            return SeverityLevel.HIGH
        elif port in medium_risk_ports:
            return SeverityLevel.MEDIUM
        elif port in web_ports:
            return SeverityLevel.LOW
        else:
            return SeverityLevel.INFO
    
    def _get_port_recommendation(self, port: int, service: str) -> str:
        """Get security recommendation for port"""
        recommendations = {
            21: "Disable FTP or use SFTP/FTPS instead",
            22: "Ensure SSH is properly configured with key-based auth",
            23: "Disable Telnet, use SSH instead",
            135: "Disable RPC if not needed, use firewall restrictions",
            139: "Disable NetBIOS if not needed",
            445: "Secure SMB configuration, disable if not needed",
            1433: "Secure SQL Server, use firewall restrictions",
            3389: "Secure RDP configuration, use VPN",
            5432: "Secure PostgreSQL, restrict access",
            6379: "Secure Redis configuration, enable authentication"
        }
        
        return recommendations.get(port, f"Review {service} configuration and restrict access")


class SSLScanner(VulnerabilityScanner):
    """SSL/TLS security scanner"""
    
    def __init__(self):
        super().__init__()
        self.scan_id = "ssl_scan"
    
    def scan_ssl(self, hostname: str, port: int = 443) -> List[SecurityFinding]:
        """Scan SSL/TLS configuration"""
        try:
            logger.info(f"Starting SSL scan of {hostname}:{port}")
            
            # Get SSL certificate info
            cert_info = self._get_certificate_info(hostname, port)
            
            if cert_info:
                self._check_certificate_validity(cert_info, hostname)
                self._check_certificate_strength(cert_info, hostname)
                self._check_ssl_configuration(hostname, port)
            
            return self.findings
            
        except Exception as e:
            logger.error(f"SSL scan failed for {hostname}:{port}: {e}")
            return []
    
    def _get_certificate_info(self, hostname: str, port: int) -> Optional[Dict[str, Any]]:
        """Get SSL certificate information"""
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    return {
                        'certificate': cert,
                        'cipher': cipher,
                        'version': version
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get certificate info for {hostname}: {e}")
            return None
    
    def _check_certificate_validity(self, cert_info: Dict[str, Any], hostname: str):
        """Check certificate validity"""
        cert = cert_info['certificate']
        
        # Check expiration
        not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
        days_until_expiry = (not_after - datetime.utcnow()).days
        
        if days_until_expiry < 0:
            self.add_finding(
                scan_type=ScanType.SSL_CHECK,
                severity=SeverityLevel.CRITICAL,
                title="SSL Certificate Expired",
                description=f"SSL certificate expired on {cert['notAfter']}",
                affected_resource=hostname,
                recommendation="Renew SSL certificate immediately",
                evidence={'expiry_date': cert['notAfter'], 'days_expired': abs(days_until_expiry)}
            )
        elif days_until_expiry < 30:
            self.add_finding(
                scan_type=ScanType.SSL_CHECK,
                severity=SeverityLevel.HIGH,
                title="SSL Certificate Expiring Soon",
                description=f"SSL certificate expires in {days_until_expiry} days",
                affected_resource=hostname,
                recommendation="Renew SSL certificate soon",
                evidence={'expiry_date': cert['notAfter'], 'days_remaining': days_until_expiry}
            )
        
        # Check subject alternative names
        san_extension = None
        for extension in cert.get('extensions', []):
            if 'subjectAltName' in extension:
                san_extension = extension
                break
        
        if san_extension:
            san_names = [name[1] for name in san_extension if name[0] == 'DNS']
            if hostname not in san_names and f"*.{hostname}" not in san_names:
                self.add_finding(
                    scan_type=ScanType.SSL_CHECK,
                    severity=SeverityLevel.MEDIUM,
                    title="SSL Certificate Hostname Mismatch",
                    description=f"Certificate does not include {hostname} in SAN",
                    affected_resource=hostname,
                    recommendation="Ensure certificate includes all required hostnames",
                    evidence={'san_names': san_names, 'requested_hostname': hostname}
                )
    
    def _check_certificate_strength(self, cert_info: Dict[str, Any], hostname: str):
        """Check certificate cryptographic strength"""
        cert = cert_info['certificate']
        
        # Check key size (for RSA)
        if 'publicKey' in cert:
            public_key = cert['publicKey']
            if hasattr(public_key, 'key_size'):
                key_size = public_key.key_size
                if key_size < 2048:
                    self.add_finding(
                        scan_type=ScanType.SSL_CHECK,
                        severity=SeverityLevel.HIGH,
                        title="Weak SSL Certificate Key Size",
                        description=f"Certificate uses {key_size}-bit key",
                        affected_resource=hostname,
                        recommendation="Use at least 2048-bit RSA or 256-bit ECC keys",
                        evidence={'key_size': key_size}
                    )
        
        # Check signature algorithm
        signature_algorithm = cert.get('signatureAlgorithm', '')
        weak_algorithms = ['md5', 'sha1']
        
        for weak_alg in weak_algorithms:
            if weak_alg.lower() in signature_algorithm.lower():
                self.add_finding(
                    scan_type=ScanType.SSL_CHECK,
                    severity=SeverityLevel.HIGH,
                    title="Weak SSL Certificate Signature Algorithm",
                    description=f"Certificate uses weak signature algorithm: {signature_algorithm}",
                    affected_resource=hostname,
                    recommendation="Use SHA-256 or stronger signature algorithm",
                    evidence={'signature_algorithm': signature_algorithm}
                )
    
    def _check_ssl_configuration(self, hostname: str, port: int):
        """Check SSL/TLS configuration"""
        # Check supported protocols
        weak_protocols = ['SSLv2', 'SSLv3', 'TLSv1.0']
        
        for protocol in weak_protocols:
            if self._test_ssl_protocol(hostname, port, protocol):
                severity = SeverityLevel.CRITICAL if 'SSL' in protocol else SeverityLevel.HIGH
                
                self.add_finding(
                    scan_type=ScanType.SSL_CHECK,
                    severity=severity,
                    title=f"Weak SSL/TLS Protocol Supported: {protocol}",
                    description=f"Server supports insecure protocol {protocol}",
                    affected_resource=f"{hostname}:{port}",
                    recommendation=f"Disable {protocol} and use TLS 1.2 or higher",
                    evidence={'protocol': protocol}
                )
    
    def _test_ssl_protocol(self, hostname: str, port: int, protocol: str) -> bool:
        """Test if SSL/TLS protocol is supported"""
        try:
            # This is a simplified check - in production, use tools like testssl.sh
            context = ssl.SSLContext()
            
            protocol_map = {
                'SSLv2': ssl.PROTOCOL_SSLv2 if hasattr(ssl, 'PROTOCOL_SSLv2') else None,
                'SSLv3': ssl.PROTOCOL_SSLv3 if hasattr(ssl, 'PROTOCOL_SSLv3') else None,
                'TLSv1.0': ssl.PROTOCOL_TLSv1 if hasattr(ssl, 'PROTOCOL_TLSv1') else None,
            }
            
            ssl_protocol = protocol_map.get(protocol)
            if not ssl_protocol:
                return False
            
            context.protocol = ssl_protocol
            
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    return True
                    
        except:
            return False


class WebScanner(VulnerabilityScanner):
    """Web application security scanner"""
    
    def __init__(self):
        super().__init__()
        self.scan_id = "web_scan"
        self.session = requests.Session()
        self.session.timeout = 10
    
    def scan_website(self, base_url: str) -> List[SecurityFinding]:
        """Scan website for common vulnerabilities"""
        try:
            logger.info(f"Starting web scan of {base_url}")
            
            # Basic security headers check
            self._check_security_headers(base_url)
            
            # Check for common vulnerabilities
            self._check_sql_injection(base_url)
            self._check_xss_vulnerability(base_url)
            self._check_directory_traversal(base_url)
            self._check_sensitive_files(base_url)
            
            return self.findings
            
        except Exception as e:
            logger.error(f"Web scan failed for {base_url}: {e}")
            return []
    
    def _check_security_headers(self, base_url: str):
        """Check for important security headers"""
        try:
            response = self.session.get(base_url)
            headers = response.headers
            
            # Check for missing security headers
            security_headers = {
                'X-Frame-Options': {
                    'severity': SeverityLevel.MEDIUM,
                    'description': 'Protects against clickjacking attacks'
                },
                'X-Content-Type-Options': {
                    'severity': SeverityLevel.LOW,
                    'description': 'Prevents MIME type sniffing'
                },
                'X-XSS-Protection': {
                    'severity': SeverityLevel.LOW,
                    'description': 'Enables XSS filtering in older browsers'
                },
                'Strict-Transport-Security': {
                    'severity': SeverityLevel.MEDIUM,
                    'description': 'Enforces HTTPS connections'
                },
                'Content-Security-Policy': {
                    'severity': SeverityLevel.HIGH,
                    'description': 'Prevents code injection attacks'
                }
            }
            
            for header, info in security_headers.items():
                if header not in headers:
                    self.add_finding(
                        scan_type=ScanType.WEB_SCAN,
                        severity=info['severity'],
                        title=f"Missing Security Header: {header}",
                        description=f"Server does not set {header} header. {info['description']}",
                        affected_resource=base_url,
                        recommendation=f"Implement {header} header",
                        evidence={'missing_header': header, 'response_headers': dict(headers)}
                    )
            
            # Check for information disclosure headers
            disclosure_headers = ['Server', 'X-Powered-By', 'X-AspNet-Version']
            for header in disclosure_headers:
                if header in headers:
                    self.add_finding(
                        scan_type=ScanType.WEB_SCAN,
                        severity=SeverityLevel.LOW,
                        title=f"Information Disclosure: {header}",
                        description=f"Server reveals information in {header} header",
                        affected_resource=base_url,
                        recommendation=f"Remove or obfuscate {header} header",
                        evidence={'header': header, 'value': headers[header]}
                    )
                    
        except Exception as e:
            logger.error(f"Security headers check failed for {base_url}: {e}")
    
    def _check_sql_injection(self, base_url: str):
        """Basic SQL injection detection"""
        try:
            # Simple SQL injection payloads
            payloads = ["'", "1' OR '1'='1", "'; DROP TABLE users; --"]
            
            # Test common parameters
            test_urls = [
                f"{base_url}?id=1",
                f"{base_url}/search?q=test",
                f"{base_url}/user?id=1"
            ]
            
            for url in test_urls:
                for payload in payloads:
                    test_url = url.replace('=1', f'={payload}').replace('=test', f'={payload}')
                    
                    try:
                        response = self.session.get(test_url)
                        
                        # Look for SQL error messages
                        sql_errors = [
                            'mysql_fetch_array',
                            'ORA-01756',
                            'Microsoft OLE DB Provider for ODBC Drivers',
                            'You have an error in your SQL syntax',
                            'PostgreSQL query failed'
                        ]
                        
                        for error in sql_errors:
                            if error.lower() in response.text.lower():
                                self.add_finding(
                                    scan_type=ScanType.WEB_SCAN,
                                    severity=SeverityLevel.CRITICAL,
                                    title="Potential SQL Injection Vulnerability",
                                    description=f"SQL error message detected in response",
                                    affected_resource=test_url,
                                    recommendation="Implement parameterized queries and input validation",
                                    evidence={
                                        'payload': payload,
                                        'error_indicator': error,
                                        'response_snippet': response.text[:500]
                                    }
                                )
                                break
                                
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.error(f"SQL injection check failed for {base_url}: {e}")
    
    def _check_xss_vulnerability(self, base_url: str):
        """Basic XSS vulnerability detection"""
        try:
            # Simple XSS payloads
            payloads = [
                "<script>alert('XSS')</script>",
                "<img src=x onerror=alert('XSS')>",
                "javascript:alert('XSS')"
            ]
            
            # Test reflection in common parameters
            test_params = ['q', 'search', 'name', 'message']
            
            for param in test_params:
                for payload in payloads:
                    test_url = f"{base_url}?{param}={payload}"
                    
                    try:
                        response = self.session.get(test_url)
                        
                        if payload in response.text:
                            self.add_finding(
                                scan_type=ScanType.WEB_SCAN,
                                severity=SeverityLevel.HIGH,
                                title="Potential XSS Vulnerability",
                                description=f"Input reflected without proper encoding",
                                affected_resource=test_url,
                                recommendation="Implement proper input validation and output encoding",
                                evidence={
                                    'payload': payload,
                                    'parameter': param,
                                    'reflected': True
                                }
                            )
                            
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.error(f"XSS check failed for {base_url}: {e}")
    
    def _check_directory_traversal(self, base_url: str):
        """Check for directory traversal vulnerabilities"""
        try:
            # Directory traversal payloads
            payloads = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
                "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
            ]
            
            for payload in payloads:
                test_url = f"{base_url}/download?file={payload}"
                
                try:
                    response = self.session.get(test_url)
                    
                    # Look for system file indicators
                    if ('root:x:0:0' in response.text or  # Unix /etc/passwd
                        '127.0.0.1' in response.text):    # hosts file
                        
                        self.add_finding(
                            scan_type=ScanType.WEB_SCAN,
                            severity=SeverityLevel.CRITICAL,
                            title="Directory Traversal Vulnerability",
                            description="Able to access system files",
                            affected_resource=test_url,
                            recommendation="Implement proper input validation and file access controls",
                            evidence={
                                'payload': payload,
                                'response_snippet': response.text[:200]
                            }
                        )
                        
                except Exception:
                    continue
                    
        except Exception as e:
            logger.error(f"Directory traversal check failed for {base_url}: {e}")
    
    def _check_sensitive_files(self, base_url: str):
        """Check for sensitive files and directories"""
        sensitive_paths = [
            '/.env',
            '/config.php',
            '/.git/HEAD',
            '/admin',
            '/backup',
            '/test',
            '/phpinfo.php',
            '/robots.txt',
            '/.htaccess',
            '/web.config'
        ]
        
        for path in sensitive_paths:
            try:
                test_url = urljoin(base_url, path)
                response = self.session.get(test_url)
                
                if response.status_code == 200:
                    severity = SeverityLevel.HIGH if path in ['/.env', '/config.php', '/.git/HEAD'] else SeverityLevel.MEDIUM
                    
                    self.add_finding(
                        scan_type=ScanType.WEB_SCAN,
                        severity=severity,
                        title=f"Sensitive File Accessible: {path}",
                        description=f"Sensitive file or directory is publicly accessible",
                        affected_resource=test_url,
                        recommendation="Restrict access to sensitive files and directories",
                        evidence={
                            'path': path,
                            'status_code': response.status_code,
                            'content_length': len(response.content)
                        }
                    )
                    
            except Exception:
                continue


class SecurityScanManager:
    """Manages security scanning operations"""
    
    def __init__(self):
        self.scanners = {
            ScanType.PORT_SCAN: PortScanner(),
            ScanType.SSL_CHECK: SSLScanner(),
            ScanType.WEB_SCAN: WebScanner()
        }
        self.scan_history: List[Dict[str, Any]] = []
    
    def run_scan(self, scan_type: ScanType, target: str, **kwargs) -> List[SecurityFinding]:
        """Run specific type of scan"""
        scanner = self.scanners.get(scan_type)
        if not scanner:
            logger.error(f"Scanner not available for {scan_type}")
            return []
        
        start_time = datetime.utcnow()
        findings = []
        
        try:
            if scan_type == ScanType.PORT_SCAN:
                findings = scanner.scan_host(target, kwargs.get('port_range', '1-1000'))
            elif scan_type == ScanType.SSL_CHECK:
                findings = scanner.scan_ssl(target, kwargs.get('port', 443))
            elif scan_type == ScanType.WEB_SCAN:
                findings = scanner.scan_website(target)
            
            # Record scan in history
            scan_record = {
                'scan_id': f"{scan_type.value}_{int(start_time.timestamp())}",
                'scan_type': scan_type.value,
                'target': target,
                'start_time': start_time.isoformat(),
                'end_time': datetime.utcnow().isoformat(),
                'findings_count': len(findings),
                'severity_counts': self._count_by_severity(findings)
            }
            
            self.scan_history.append(scan_record)
            logger.info(f"Scan completed: {scan_record['scan_id']} - {len(findings)} findings")
            
            return findings
            
        except Exception as e:
            logger.error(f"Scan failed for {target}: {e}")
            return []
    
    def run_comprehensive_scan(self, target: str) -> Dict[str, List[SecurityFinding]]:
        """Run comprehensive security scan"""
        results = {}
        
        # Parse target to determine available scans
        parsed_url = urlparse(target)
        hostname = parsed_url.hostname or target
        
        # Port scan
        results[ScanType.PORT_SCAN.value] = self.run_scan(ScanType.PORT_SCAN, hostname)
        
        # SSL scan (if HTTPS)
        if parsed_url.scheme == 'https' or ':443' in target:
            results[ScanType.SSL_CHECK.value] = self.run_scan(ScanType.SSL_CHECK, hostname)
        
        # Web scan (if HTTP/HTTPS)
        if parsed_url.scheme in ['http', 'https']:
            results[ScanType.WEB_SCAN.value] = self.run_scan(ScanType.WEB_SCAN, target)
        
        return results
    
    def _count_by_severity(self, findings: List[SecurityFinding]) -> Dict[str, int]:
        """Count findings by severity level"""
        counts = {severity.value: 0 for severity in SeverityLevel}
        
        for finding in findings:
            counts[finding.severity.value] += 1
        
        return counts
    
    def get_scan_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent scan history"""
        return sorted(self.scan_history, key=lambda x: x['start_time'], reverse=True)[:limit]
    
    def generate_report(self, findings: List[SecurityFinding]) -> Dict[str, Any]:
        """Generate security scan report"""
        report = {
            'scan_summary': {
                'total_findings': len(findings),
                'severity_distribution': self._count_by_severity(findings),
                'scan_time': datetime.utcnow().isoformat()
            },
            'critical_findings': [f.to_dict() for f in findings if f.severity == SeverityLevel.CRITICAL],
            'high_findings': [f.to_dict() for f in findings if f.severity == SeverityLevel.HIGH],
            'medium_findings': [f.to_dict() for f in findings if f.severity == SeverityLevel.MEDIUM],
            'low_findings': [f.to_dict() for f in findings if f.severity == SeverityLevel.LOW],
            'recommendations': self._generate_recommendations(findings)
        }
        
        return report
    
    def _generate_recommendations(self, findings: List[SecurityFinding]) -> List[str]:
        """Generate high-level security recommendations"""
        recommendations = []
        
        # Count severity levels
        severity_counts = self._count_by_severity(findings)
        
        if severity_counts['critical'] > 0:
            recommendations.append("Address critical vulnerabilities immediately")
        
        if severity_counts['high'] > 0:
            recommendations.append("Prioritize high-severity vulnerabilities for remediation")
        
        # Specific recommendations based on finding types
        scan_types = [f.scan_type for f in findings]
        
        if ScanType.SSL_CHECK in scan_types:
            recommendations.append("Review SSL/TLS configuration and certificate management")
        
        if ScanType.WEB_SCAN in scan_types:
            recommendations.append("Implement web application security best practices")
        
        if ScanType.PORT_SCAN in scan_types:
            recommendations.append("Review network security and close unnecessary ports")
        
        return recommendations