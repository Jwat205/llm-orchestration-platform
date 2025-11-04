"""
Version Manager
Manages API versioning, routing, and compatibility
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging
from packaging import version
import semver

logger = logging.getLogger(__name__)


class VersionStatus(Enum):
    """API version status"""
    DEVELOPMENT = "development"
    ALPHA = "alpha"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"


class VersionType(Enum):
    """Type of version change"""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


@dataclass
class APIVersion:
    """API version metadata"""
    version: str
    status: VersionStatus
    release_date: datetime
    sunset_date: Optional[datetime]
    description: str
    breaking_changes: List[str]
    deprecations: List[str]
    new_features: List[str]
    bug_fixes: List[str]
    migration_guide_url: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        data['release_date'] = self.release_date.isoformat()
        if self.sunset_date:
            data['sunset_date'] = self.sunset_date.isoformat()
        return data
    
    @property
    def semantic_version(self) -> version.Version:
        """Get semantic version object"""
        return version.parse(self.version)
    
    @property
    def is_active(self) -> bool:
        """Check if version is active (not sunset)"""
        return self.status != VersionStatus.SUNSET
    
    @property
    def is_supported(self) -> bool:
        """Check if version is still supported"""
        if self.sunset_date:
            return datetime.utcnow() < self.sunset_date
        return self.status in [VersionStatus.STABLE, VersionStatus.BETA, VersionStatus.DEPRECATED]


class VersionParser:
    """Parse and validate version strings"""
    
    @staticmethod
    def parse_version_header(header_value: str) -> Optional[str]:
        """Parse version from Accept header"""
        # Accept: application/vnd.api+json;version=1.0
        version_pattern = r'version=([0-9]+\.[0-9]+(?:\.[0-9]+)?)'
        match = re.search(version_pattern, header_value)
        return match.group(1) if match else None
    
    @staticmethod
    def parse_version_path(path: str) -> Optional[str]:
        """Parse version from URL path"""
        # /v1/endpoint or /api/v2.1/endpoint
        version_pattern = r'/v?([0-9]+(?:\.[0-9]+)?(?:\.[0-9]+)?)'
        match = re.search(version_pattern, path)
        return match.group(1) if match else None
    
    @staticmethod
    def parse_version_query(query_params: Dict[str, str]) -> Optional[str]:
        """Parse version from query parameters"""
        return query_params.get('version') or query_params.get('api_version')
    
    @staticmethod
    def normalize_version(version_str: str) -> str:
        """Normalize version string to semantic version"""
        # Convert "1" to "1.0.0", "1.1" to "1.1.0"
        parts = version_str.split('.')
        while len(parts) < 3:
            parts.append('0')
        return '.'.join(parts[:3])
    
    @staticmethod
    def is_valid_version(version_str: str) -> bool:
        """Validate version string format"""
        try:
            semver.VersionInfo.parse(VersionParser.normalize_version(version_str))
            return True
        except ValueError:
            return False


class VersionMatcher:
    """Match requested versions to available versions"""
    
    def __init__(self, available_versions: List[APIVersion]):
        self.available_versions = sorted(
            available_versions, 
            key=lambda v: v.semantic_version, 
            reverse=True
        )
    
    def find_best_match(self, requested_version: str, include_deprecated: bool = True) -> Optional[APIVersion]:
        """Find best matching version"""
        try:
            requested = version.parse(VersionParser.normalize_version(requested_version))
        except Exception:
            return None
        
        # Filter by support status
        candidates = [
            v for v in self.available_versions 
            if v.is_supported and (include_deprecated or v.status != VersionStatus.DEPRECATED)
        ]
        
        # Exact match first
        for api_version in candidates:
            if api_version.semantic_version == requested:
                return api_version
        
        # Compatible minor version match (same major version)
        for api_version in candidates:
            if (api_version.semantic_version.major == requested.major and 
                api_version.semantic_version >= requested):
                return api_version
        
        # Fallback to latest stable version of same major
        for api_version in candidates:
            if (api_version.semantic_version.major == requested.major and 
                api_version.status == VersionStatus.STABLE):
                return api_version
        
        return None
    
    def find_latest_stable(self) -> Optional[APIVersion]:
        """Find latest stable version"""
        for api_version in self.available_versions:
            if api_version.status == VersionStatus.STABLE and api_version.is_supported:
                return api_version
        return None
    
    def find_version_by_string(self, version_str: str) -> Optional[APIVersion]:
        """Find exact version by string"""
        for api_version in self.available_versions:
            if api_version.version == version_str:
                return api_version
        return None


class VersionRegistry:
    """Registry of all API versions"""
    
    def __init__(self):
        self.versions: Dict[str, APIVersion] = {}
        self.version_matcher = None
        self._setup_default_versions()
    
    def _setup_default_versions(self):
        """Setup default API versions"""
        # Legacy version (deprecated)
        self.register_version(APIVersion(
            version="0.9.0",
            status=VersionStatus.DEPRECATED,
            release_date=datetime(2023, 1, 1),
            sunset_date=datetime(2024, 12, 31),
            description="Legacy API version with basic functionality",
            breaking_changes=[],
            deprecations=["Old authentication method", "Legacy response format"],
            new_features=[],
            bug_fixes=[],
            migration_guide_url="/docs/migration/v0.9-to-v1.0"
        ))
        
        # Current stable version
        self.register_version(APIVersion(
            version="1.0.0",
            status=VersionStatus.STABLE,
            release_date=datetime(2023, 6, 1),
            sunset_date=None,
            description="Stable API with full LLM capabilities",
            breaking_changes=["Authentication method changed", "Response format updated"],
            deprecations=[],
            new_features=["Streaming responses", "Function calling", "Enhanced embeddings"],
            bug_fixes=["Fixed rate limiting", "Improved error handling"],
            migration_guide_url="/docs/migration/v0.9-to-v1.0"
        ))
        
        # Current stable patch
        self.register_version(APIVersion(
            version="1.1.0",
            status=VersionStatus.STABLE,
            release_date=datetime(2023, 9, 1),
            sunset_date=None,
            description="Enhanced stable API with additional features",
            breaking_changes=[],
            deprecations=["Legacy parameter names"],
            new_features=["Batch processing", "Enhanced monitoring", "New model support"],
            bug_fixes=["Performance improvements", "Memory optimization"],
            migration_guide_url="/docs/migration/v1.0-to-v1.1"
        ))
        
        # Beta version
        self.register_version(APIVersion(
            version="2.0.0-beta.1",
            status=VersionStatus.BETA,
            release_date=datetime(2023, 11, 1),
            sunset_date=None,
            description="Next generation API with advanced features",
            breaking_changes=["New request/response format", "Updated authentication"],
            deprecations=[],
            new_features=["Advanced analytics", "Multi-model support", "Graph capabilities"],
            bug_fixes=[],
            migration_guide_url="/docs/migration/v1.x-to-v2.0"
        ))
    
    def register_version(self, api_version: APIVersion):
        """Register a new API version"""
        self.versions[api_version.version] = api_version
        self._update_matcher()
        logger.info(f"Registered API version: {api_version.version}")
    
    def _update_matcher(self):
        """Update version matcher with current versions"""
        self.version_matcher = VersionMatcher(list(self.versions.values()))
    
    def get_version(self, version_str: str) -> Optional[APIVersion]:
        """Get version by string"""
        return self.versions.get(version_str)
    
    def get_all_versions(self) -> List[APIVersion]:
        """Get all registered versions"""
        return list(self.versions.values())
    
    def get_supported_versions(self) -> List[APIVersion]:
        """Get all supported versions"""
        return [v for v in self.versions.values() if v.is_supported]
    
    def get_deprecated_versions(self) -> List[APIVersion]:
        """Get all deprecated versions"""
        return [v for v in self.versions.values() if v.status == VersionStatus.DEPRECATED]
    
    def deprecate_version(self, version_str: str, sunset_date: datetime):
        """Deprecate a version"""
        if version_str in self.versions:
            self.versions[version_str].status = VersionStatus.DEPRECATED
            self.versions[version_str].sunset_date = sunset_date
            logger.info(f"Deprecated version {version_str}, sunset date: {sunset_date}")
    
    def sunset_version(self, version_str: str):
        """Sunset a version (make it unavailable)"""
        if version_str in self.versions:
            self.versions[version_str].status = VersionStatus.SUNSET
            logger.info(f"Sunset version {version_str}")


class VersionResolver:
    """Resolves version from request context"""
    
    def __init__(self, version_registry: VersionRegistry):
        self.registry = version_registry
        self.parser = VersionParser()
    
    def resolve_version(self, 
                       request_path: str = "",
                       headers: Dict[str, str] = None,
                       query_params: Dict[str, str] = None) -> Tuple[Optional[APIVersion], str]:
        """
        Resolve API version from request
        Returns: (APIVersion, source) where source indicates how version was determined
        """
        headers = headers or {}
        query_params = query_params or {}
        
        # Priority order: query param > header > path > default
        
        # 1. Check query parameters
        version_str = self.parser.parse_version_query(query_params)
        if version_str and self.parser.is_valid_version(version_str):
            normalized = self.parser.normalize_version(version_str)
            version_obj = self.registry.version_matcher.find_best_match(normalized)
            if version_obj:
                return version_obj, "query_parameter"
        
        # 2. Check headers
        accept_header = headers.get('Accept', '')
        version_str = self.parser.parse_version_header(accept_header)
        if version_str and self.parser.is_valid_version(version_str):
            normalized = self.parser.normalize_version(version_str)
            version_obj = self.registry.version_matcher.find_best_match(normalized)
            if version_obj:
                return version_obj, "header"
        
        # 3. Check URL path
        version_str = self.parser.parse_version_path(request_path)
        if version_str and self.parser.is_valid_version(version_str):
            normalized = self.parser.normalize_version(version_str)
            version_obj = self.registry.version_matcher.find_best_match(normalized)
            if version_obj:
                return version_obj, "path"
        
        # 4. Default to latest stable
        default_version = self.registry.version_matcher.find_latest_stable()
        return default_version, "default"
    
    def validate_version_request(self, requested_version: str) -> Dict[str, Any]:
        """Validate a version request and provide feedback"""
        result = {
            "valid": False,
            "version": None,
            "message": "",
            "suggestions": []
        }
        
        if not self.parser.is_valid_version(requested_version):
            result["message"] = f"Invalid version format: {requested_version}"
            result["suggestions"] = [v.version for v in self.registry.get_supported_versions()]
            return result
        
        normalized = self.parser.normalize_version(requested_version)
        matched_version = self.registry.version_matcher.find_best_match(normalized)
        
        if not matched_version:
            result["message"] = f"Version {requested_version} not found"
            result["suggestions"] = [v.version for v in self.registry.get_supported_versions()]
            return result
        
        if not matched_version.is_supported:
            result["message"] = f"Version {requested_version} is no longer supported"
            result["suggestions"] = [v.version for v in self.registry.get_supported_versions()]
            return result
        
        result["valid"] = True
        result["version"] = matched_version
        result["message"] = f"Version {matched_version.version} resolved successfully"
        
        return result


class VersionManager:
    """Main version management system"""
    
    def __init__(self):
        self.registry = VersionRegistry()
        self.resolver = VersionResolver(self.registry)
        self.request_log: List[Dict[str, Any]] = []
    
    def resolve_api_version(self, 
                           request_path: str = "",
                           headers: Dict[str, str] = None,
                           query_params: Dict[str, str] = None) -> APIVersion:
        """Resolve API version for request"""
        resolved_version, source = self.resolver.resolve_version(request_path, headers, query_params)
        
        # Log version resolution
        self._log_version_request(resolved_version, source, request_path)
        
        return resolved_version
    
    def get_version_info(self, version_str: str = None) -> Dict[str, Any]:
        """Get comprehensive version information"""
        if version_str:
            version_obj = self.registry.get_version(version_str)
            if version_obj:
                return version_obj.to_dict()
            else:
                return {"error": f"Version {version_str} not found"}
        
        # Return all versions info
        return {
            "supported_versions": [v.to_dict() for v in self.registry.get_supported_versions()],
            "deprecated_versions": [v.to_dict() for v in self.registry.get_deprecated_versions()],
            "latest_stable": self.registry.version_matcher.find_latest_stable().to_dict() if self.registry.version_matcher.find_latest_stable() else None
        }
    
    def check_version_compatibility(self, client_version: str, server_version: str) -> Dict[str, Any]:
        """Check compatibility between client and server versions"""
        try:
            client_ver = version.parse(VersionParser.normalize_version(client_version))
            server_ver = version.parse(VersionParser.normalize_version(server_version))
            
            compatibility = {
                "compatible": False,
                "level": "incompatible",
                "message": "",
                "recommended_action": ""
            }
            
            if client_ver.major != server_ver.major:
                compatibility.update({
                    "compatible": False,
                    "level": "major_incompatible",
                    "message": "Major version mismatch - breaking changes expected",
                    "recommended_action": "Upgrade client to compatible major version"
                })
            elif client_ver.minor > server_ver.minor:
                compatibility.update({
                    "compatible": False,
                    "level": "minor_incompatible",
                    "message": "Client version newer than server",
                    "recommended_action": "Server upgrade recommended"
                })
            elif client_ver.minor < server_ver.minor:
                compatibility.update({
                    "compatible": True,
                    "level": "backward_compatible",
                    "message": "Backward compatible - some features may be unavailable",
                    "recommended_action": "Consider client upgrade for latest features"
                })
            else:
                compatibility.update({
                    "compatible": True,
                    "level": "fully_compatible",
                    "message": "Versions are fully compatible",
                    "recommended_action": "No action required"
                })
            
            return compatibility
            
        except Exception as e:
            return {
                "compatible": False,
                "level": "error",
                "message": f"Error checking compatibility: {e}",
                "recommended_action": "Verify version format"
            }
    
    def get_version_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get version usage statistics"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_requests = [
            req for req in self.request_log 
            if datetime.fromisoformat(req['timestamp']) > cutoff_date
        ]
        
        version_counts = {}
        source_counts = {}
        
        for request in recent_requests:
            version = request['version']
            source = request['source']
            
            version_counts[version] = version_counts.get(version, 0) + 1
            source_counts[source] = source_counts.get(source, 0) + 1
        
        total_requests = len(recent_requests)
        
        return {
            "period_days": days,
            "total_requests": total_requests,
            "version_distribution": {
                version: {
                    "count": count,
                    "percentage": (count / total_requests * 100) if total_requests > 0 else 0
                }
                for version, count in version_counts.items()
            },
            "resolution_source_distribution": source_counts,
            "deprecated_usage": sum(
                count for version, count in version_counts.items()
                if self.registry.get_version(version) and 
                self.registry.get_version(version).status == VersionStatus.DEPRECATED
            )
        }
    
    def _log_version_request(self, version: APIVersion, source: str, path: str):
        """Log version resolution for analytics"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "version": version.version if version else "unknown",
            "source": source,
            "path": path
        }
        
        self.request_log.append(log_entry)
        
        # Keep only recent entries (last 10000)
        if len(self.request_log) > 10000:
            self.request_log = self.request_log[-10000:]
    
    def add_version(self, 
                   version_str: str,
                   status: VersionStatus,
                   description: str,
                   breaking_changes: List[str] = None,
                   new_features: List[str] = None,
                   sunset_date: datetime = None) -> bool:
        """Add a new API version"""
        try:
            api_version = APIVersion(
                version=version_str,
                status=status,
                release_date=datetime.utcnow(),
                sunset_date=sunset_date,
                description=description,
                breaking_changes=breaking_changes or [],
                deprecations=[],
                new_features=new_features or [],
                bug_fixes=[],
                migration_guide_url=None
            )
            
            self.registry.register_version(api_version)
            return True
            
        except Exception as e:
            logger.error(f"Failed to add version {version_str}: {e}")
            return False
    
    def deprecate_version(self, version_str: str, sunset_months: int = 12) -> bool:
        """Deprecate a version with sunset date"""
        try:
            sunset_date = datetime.utcnow() + timedelta(days=sunset_months * 30)
            self.registry.deprecate_version(version_str, sunset_date)
            return True
        except Exception as e:
            logger.error(f"Failed to deprecate version {version_str}: {e}")
            return False
    
    def cleanup_sunset_versions(self) -> List[str]:
        """Remove sunset versions and return list of removed versions"""
        removed_versions = []
        current_time = datetime.utcnow()
        
        for version_str, version_obj in list(self.registry.versions.items()):
            if (version_obj.sunset_date and 
                current_time > version_obj.sunset_date and 
                version_obj.status == VersionStatus.DEPRECATED):
                
                self.registry.sunset_version(version_str)
                removed_versions.append(version_str)
        
        return removed_versions