"""
Dynamic Version Router
Handles API version routing, compatibility transformations, and request forwarding
"""

import asyncio
import json
from typing import Dict, Any, Optional, Tuple
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
import logging

from ..shared.versioning.version_manager import VersionManager
from ..shared.versioning.compatibility import CompatibilityManager
from ..shared.versioning.deprecation import DeprecationManager
from .common.middleware import VersionMiddleware, DeprecationMiddleware

logger = logging.getLogger(__name__)


class VersionRouter:
    """Dynamic router that handles version resolution and compatibility"""
    
    def __init__(self):
        self.version_manager = VersionManager()
        self.compatibility_manager = CompatibilityManager()
        self.deprecation_manager = DeprecationManager()
        self.router = APIRouter()
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup dynamic routing for all API versions"""
        
        # Version discovery endpoint
        @self.router.get("/versions")
        async def get_api_versions():
            """Get information about all available API versions"""
            return self.version_manager.get_version_info()
        
        # Version compatibility check
        @self.router.get("/versions/compatibility")
        async def check_version_compatibility(
            client_version: str,
            server_version: str = None
        ):
            """Check compatibility between client and server versions"""
            if not server_version:
                latest = self.version_manager.registry.version_matcher.find_latest_stable()
                server_version = latest.version if latest else "1.0.0"
            
            return self.version_manager.check_version_compatibility(client_version, server_version)
        
        # Migration guide endpoint
        @self.router.get("/versions/migration")
        async def get_migration_guide(
            from_version: str,
            to_version: str,
            format: str = "markdown"
        ):
            """Get migration guide between versions"""
            from ..shared.versioning.migration_tools import MigrationToolkit
            
            toolkit = MigrationToolkit()
            guide = toolkit.create_migration_guide(from_version, to_version, format=format)
            
            if format.lower() == "json":
                return JSONResponse(content=json.loads(guide))
            else:
                return Response(content=guide, media_type="text/markdown")
        
        # Dynamic version routing catchall
        @self.router.api_route("/{version:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        async def route_versioned_request(
            version: str,
            request: Request
        ):
            """Route requests to appropriate version handlers with compatibility"""
            return await self._handle_versioned_request(version, request)
    
    async def _handle_versioned_request(self, version_path: str, request: Request) -> Response:
        """Handle versioned API requests with compatibility transformations"""
        
        try:
            # Parse version and endpoint from path
            path_parts = version_path.split("/", 1)
            if not path_parts[0].startswith("v"):
                raise HTTPException(status_code=404, detail="Invalid version path")
            
            requested_version = path_parts[0][1:]  # Remove 'v' prefix
            endpoint_path = "/" + path_parts[1] if len(path_parts) > 1 else "/"
            
            # Resolve actual API version
            api_version = self.version_manager.resolve_api_version(
                request_path=f"/v{requested_version}{endpoint_path}",
                headers=dict(request.headers),
                query_params=dict(request.query_params)
            )
            
            if not api_version:
                raise HTTPException(status_code=404, detail="API version not found")
            
            # Check if version is supported
            if not api_version.is_supported:
                raise HTTPException(
                    status_code=410,
                    detail=f"API version {api_version.version} is no longer supported"
                )
            
            # Get request data
            request_data = await self._extract_request_data(request)
            
            # Check for deprecation warnings
            deprecation_warnings = self.deprecation_manager.get_deprecation_warnings(
                api_version=api_version.version,
                endpoint=endpoint_path
            )
            
            # Record deprecation usage
            for warning in deprecation_warnings:
                self.deprecation_manager.record_deprecation_usage(
                    warning.notice_id,
                    client_id=self._get_client_id(request),
                    endpoint=endpoint_path
                )
            
            # Transform request if needed for compatibility
            target_version = self._get_target_handler_version(api_version.version)
            transformed_request, transform_warnings = await self._transform_request(
                request_data, api_version.version, target_version
            )
            
            # Route to appropriate handler
            response_data = await self._route_to_handler(
                target_version, endpoint_path, request.method, transformed_request, request
            )
            
            # Transform response back if needed
            final_response, response_warnings = await self._transform_response(
                response_data, target_version, api_version.version
            )
            
            # Create response with headers
            response = JSONResponse(content=final_response)
            
            # Add version headers
            response.headers["X-API-Version"] = api_version.version
            response.headers["X-API-Version-Resolved"] = target_version
            
            # Add deprecation headers
            if deprecation_warnings:
                headers = self.deprecation_manager.get_deprecation_headers(deprecation_warnings)
                for key, value in headers.items():
                    response.headers[key] = value
            
            # Add compatibility warnings
            all_warnings = transform_warnings + response_warnings
            if all_warnings:
                response.headers["X-Compatibility-Warnings"] = json.dumps(all_warnings)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error handling versioned request: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _extract_request_data(self, request: Request) -> Dict[str, Any]:
        """Extract request data for processing"""
        request_data = {
            "method": request.method,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "path_params": getattr(request, "path_params", {}),
            "body": None
        }
        
        # Get request body if present
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    content_type = request.headers.get("content-type", "")
                    if "application/json" in content_type:
                        request_data["body"] = json.loads(body.decode())
                    else:
                        request_data["body"] = body.decode()
            except Exception as e:
                logger.warning(f"Failed to parse request body: {e}")
        
        return request_data
    
    async def _transform_request(self, request_data: Dict[str, Any], 
                               from_version: str, to_version: str) -> Tuple[Dict[str, Any], List[str]]:
        """Transform request between versions"""
        if from_version == to_version:
            return request_data, []
        
        try:
            # Transform request body if present
            if request_data.get("body"):
                transformed_body, warnings = self.compatibility_manager.transform_data(
                    request_data["body"], from_version, to_version, "request"
                )
                request_data["body"] = transformed_body
                return request_data, warnings
            
            return request_data, []
            
        except Exception as e:
            logger.error(f"Request transformation error: {e}")
            return request_data, [f"Request transformation failed: {e}"]
    
    async def _transform_response(self, response_data: Any, 
                                from_version: str, to_version: str) -> Tuple[Any, List[str]]:
        """Transform response between versions"""
        if from_version == to_version:
            return response_data, []
        
        try:
            transformed_response, warnings = self.compatibility_manager.transform_data(
                response_data, from_version, to_version, "response"
            )
            return transformed_response, warnings
            
        except Exception as e:
            logger.error(f"Response transformation error: {e}")
            return response_data, [f"Response transformation failed: {e}"]
    
    async def _route_to_handler(self, version: str, endpoint: str, method: str, 
                              request_data: Dict[str, Any], original_request: Request) -> Any:
        """Route request to appropriate version handler"""
        
        # This is a simplified mock implementation
        # In production, you would route to actual version-specific handlers
        
        if version.startswith("1."):
            return await self._handle_v1_request(endpoint, method, request_data, original_request)
        elif version.startswith("2."):
            return await self._handle_v2_request(endpoint, method, request_data, original_request)
        elif version.startswith("0.9"):
            return await self._handle_legacy_request(endpoint, method, request_data, original_request)
        else:
            raise HTTPException(status_code=404, detail="Handler not found for version")
    
    async def _handle_v1_request(self, endpoint: str, method: str, 
                               request_data: Dict[str, Any], request: Request) -> Any:
        """Handle v1 API requests"""
        # Mock v1 response
        return {
            "version": "1.0",
            "endpoint": endpoint,
            "method": method,
            "message": "Handled by v1 API",
            "data": request_data.get("body", {})
        }
    
    async def _handle_v2_request(self, endpoint: str, method: str, 
                               request_data: Dict[str, Any], request: Request) -> Any:
        """Handle v2 API requests"""
        # Mock v2 response with enhanced features
        return {
            "version": "2.0",
            "endpoint": endpoint,
            "method": method,
            "message": "Handled by v2 API with enhanced features",
            "data": request_data.get("body", {}),
            "metadata": {
                "processing_time_ms": 42.5,
                "features": ["enhanced_responses", "function_calling"]
            }
        }
    
    async def _handle_legacy_request(self, endpoint: str, method: str, 
                                   request_data: Dict[str, Any], request: Request) -> Any:
        """Handle legacy API requests"""
        # Mock legacy response
        return {
            "status": "ok",
            "message": "Legacy API response",
            "data": request_data.get("body", {}),
            "deprecated": True,
            "migration_url": "/docs/migration/v0.9-to-v1.0"
        }
    
    def _get_target_handler_version(self, requested_version: str) -> str:
        """Determine which handler version to use for a requested version"""
        # Map requested versions to actual handler versions
        if requested_version.startswith("1."):
            return "1.1.0"  # Route to latest v1
        elif requested_version.startswith("2."):
            return "2.0.0"  # Route to v2
        elif requested_version.startswith("0.9"):
            return "0.9.0"  # Route to legacy
        else:
            return "1.1.0"  # Default to latest stable
    
    def _get_client_id(self, request: Request) -> str:
        """Extract client ID from request"""
        client_id = request.headers.get("X-Client-ID")
        if not client_id and request.client:
            client_id = request.client.host
        return client_id or "anonymous"


# Create global version router instance
version_router = VersionRouter()
router = version_router.router

# Export router for inclusion in main app
__all__ = ["router", "version_router"]