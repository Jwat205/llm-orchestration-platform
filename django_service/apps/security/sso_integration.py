# django-service/apps/security/sso_integration.py
import xml.etree.ElementTree as ET
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.cache import cache
from typing import Dict, Optional, Tuple
import base64
import hashlib
import hmac
import json
import logging
import requests
import secrets
import time
from urllib.parse import urlencode, parse_qs
from datetime import timedelta

from .models import Organization, SecurityUser, AuditLog
from .rbac import RBACManager

logger = logging.getLogger(__name__)

class SSOProvider:
    """Base SSO provider class"""
    
    def __init__(self, organization: Organization):
        self.organization = organization
        self.config = organization.sso_metadata
        
    def initiate_login(self, request) -> HttpResponse:
        """Initiate SSO login process"""
        raise NotImplementedError
        
    def handle_callback(self, request) -> Tuple[bool, Optional[SecurityUser], str]:
        """Handle SSO callback and return (success, user, error_message)"""
        raise NotImplementedError
        
    def get_user_info(self, token: str) -> Dict:
        """Get user information from SSO provider"""
        raise NotImplementedError

class SAMLProvider(SSOProvider):
    """SAML 2.0 SSO Provider"""
    
    def __init__(self, organization: Organization):
        super().__init__(organization)
        self.entity_id = self.config.get('entity_id')
        self.sso_url = self.config.get('sso_url')
        self.x509_cert = self.config.get('x509_cert')
        self.private_key = self.config.get('private_key')
        
    def initiate_login(self, request) -> HttpResponse:
        """Initiate SAML login"""
        try:
            # Generate SAML request
            request_id = f"_{secrets.token_hex(16)}"
            timestamp = timezone.now().isoformat()
            
            saml_request = f"""
            <samlp:AuthnRequest
                xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="{request_id}"
                Version="2.0"
                IssueInstant="{timestamp}"
                Destination="{self.sso_url}"
                AssertionConsumerServiceURL="{settings.SITE_URL}/auth/saml/callback/">
                <saml:Issuer>{self.entity_id}</saml:Issuer>
                <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:2.0:nameid-format:emailAddress" AllowCreate="true"/>
            </samlp:AuthnRequest>
            """
            
            # Encode and compress SAML request
            compressed_request = base64.b64encode(saml_request.encode()).decode()
            
            # Cache request for validation
            cache.set(f"saml_request_{request_id}", {
                'organization_id': self.organization.id,
                'timestamp': timestamp
            }, 600)  # 10 minutes
            
            # Redirect to SSO provider
            params = {
                'SAMLRequest': compressed_request,
                'RelayState': str(self.organization.id)
            }
            
            redirect_url = f"{self.sso_url}?{urlencode(params)}"
            return HttpResponseRedirect(redirect_url)
            
        except Exception as e:
            logger.error(f"SAML login initiation failed: {e}")
            raise
    
    def handle_callback(self, request) -> Tuple[bool, Optional[SecurityUser], str]:
        """Handle SAML callback"""
        try:
            saml_response = request.POST.get('SAMLResponse')
            relay_state = request.POST.get('RelayState')
            
            if not saml_response:
                return False, None, "Missing SAML response"
            
            # Decode SAML response
            decoded_response = base64.b64decode(saml_response).decode()
            
            # Parse XML
            root = ET.fromstring(decoded_response)
            
            # Validate signature (simplified - use proper SAML library in production)
            if not self._validate_saml_signature(root):
                return False, None, "Invalid SAML signature"
            
            # Extract user information
            user_info = self._extract_user_info(root)
            
            if not user_info.get('email'):
                return False, None, "Email not found in SAML response"
            
            # Find or create user
            user = self._get_or_create_user(user_info)
            
            # Audit log
            AuditLog.objects.create(
                organization=self.organization,
                user=user,
                action='login',
                severity='low',
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={
                    'sso_provider': 'saml',
                    'login_method': 'sso'
                }
            )
            
            return True, user, ""
            
        except Exception as e:
            logger.error(f"SAML callback handling failed: {e}")
            return False, None, str(e)
    
    def _validate_saml_signature(self, root: ET.Element) -> bool:
        """Validate SAML signature (simplified implementation)"""
        # In production, use proper SAML library like python3-saml
        # This is a placeholder for signature validation
        return True
    
    def _extract_user_info(self, root: ET.Element) -> Dict:
        """Extract user information from SAML response"""
        user_info = {}
        
        # Find assertion
        assertion = root.find('.//{urn:oasis:names:tc:SAML:2.0:assertion}Assertion')
        if assertion is None:
            return user_info
        
        # Extract attributes
        attributes = assertion.findall('.//{urn:oasis:names:tc:SAML:2.0:assertion}Attribute')
        
        for attr in attributes:
            name = attr.get('Name')
            value_elem = attr.find('{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue')
            
            if value_elem is not None:
                if name == 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress':
                    user_info['email'] = value_elem.text
                elif name == 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname':
                    user_info['first_name'] = value_elem.text
                elif name == 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname':
                    user_info['last_name'] = value_elem.text
                elif name == 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name':
                    user_info['username'] = value_elem.text
        
        return user_info
    
    def _get_or_create_user(self, user_info: Dict) -> SecurityUser:
        """Get or create user from SSO information"""
        email = user_info['email']
        
        try:
            user = SecurityUser.objects.get(email=email, organization=self.organization)
            # Update user info
            user.first_name = user_info.get('first_name', user.first_name)
            user.last_name = user_info.get('last_name', user.last_name)
            user.last_activity = timezone.now()
            user.save()
            
        except SecurityUser.DoesNotExist:
            # Create new user
            user = SecurityUser.objects.create(
                username=user_info.get('username', email),
                email=email,
                first_name=user_info.get('first_name', ''),
                last_name=user_info.get('last_name', ''),
                organization=self.organization,
                sso_user_id=user_info.get('user_id', ''),
                is_active=True,
                last_activity=timezone.now()
            )
            
            # Assign default viewer role
            rbac = RBACManager()
            default_roles = rbac.create_default_roles(self.organization)
            if 'viewer' in default_roles:
                rbac.assign_role(user, default_roles['viewer'])
        
        return user

class OAuthProvider(SSOProvider):
    """OAuth 2.0 SSO Provider (Google, Microsoft, etc.)"""
    
    def __init__(self, organization: Organization):
        super().__init__(organization)
        self.client_id = self.config.get('client_id')
        self.client_secret = self.config.get('client_secret')
        self.authorize_url = self.config.get('authorize_url')
        self.token_url = self.config.get('token_url')
        self.user_info_url = self.config.get('user_info_url')
        self.scopes = self.config.get('scopes', ['openid', 'email', 'profile'])
        
    def initiate_login(self, request) -> HttpResponse:
        """Initiate OAuth login"""
        try:
            # Generate state parameter for CSRF protection
            state = secrets.token_urlsafe(32)
            
            # Cache state
            cache.set(f"oauth_state_{state}", {
                'organization_id': self.organization.id,
                'timestamp': timezone.now().isoformat()
            }, 600)  # 10 minutes
            
            # Build authorization URL
            params = {
                'client_id': self.client_id,
                'response_type': 'code',
                'scope': ' '.join(self.scopes),
                'redirect_uri': f"{settings.SITE_URL}/auth/oauth/callback/",
                'state': state
            }
            
            redirect_url = f"{self.authorize_url}?{urlencode(params)}"
            return HttpResponseRedirect(redirect_url)
            
        except Exception as e:
            logger.error(f"OAuth login initiation failed: {e}")
            raise
    
    def handle_callback(self, request) -> Tuple[bool, Optional[SecurityUser], str]:
        """Handle OAuth callback"""
        try:
            code = request.GET.get('code')
            state = request.GET.get('state')
            error = request.GET.get('error')
            
            if error:
                return False, None, f"OAuth error: {error}"
            
            if not code or not state:
                return False, None, "Missing authorization code or state"
            
            # Validate state
            cached_state = cache.get(f"oauth_state_{state}")
            if not cached_state:
                return False, None, "Invalid or expired state parameter"
            
            # Exchange code for token
            token_data = self._exchange_code_for_token(code)
            if not token_data:
                return False, None, "Failed to exchange code for token"
            
            # Get user info
            user_info = self.get_user_info(token_data['access_token'])
            if not user_info.get('email'):
                return False, None, "Email not found in user info"
            
            # Find or create user
            user = self._get_or_create_user(user_info, token_data)
            
            # Audit log
            AuditLog.objects.create(
                organization=self.organization,
                user=user,
                action='login',
                severity='low',
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={
                    'sso_provider': 'oauth',
                    'login_method': 'sso'
                }
            )
            
            return True, user, ""
            
        except Exception as e:
            logger.error(f"OAuth callback handling failed: {e}")
            return False, None, str(e)
    
    def _exchange_code_for_token(self, code: str) -> Optional[Dict]:
        """Exchange authorization code for access token"""
        try:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': f"{settings.SITE_URL}/auth/oauth/callback/"
            }
            
            response = requests.post(self.token_url, data=data, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            return None
    
    def get_user_info(self, access_token: str) -> Dict:
        """Get user information using access token"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(self.user_info_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return {}
    
    def _get_or_create_user(self, user_info: Dict, token_data: Dict) -> SecurityUser:
        """Get or create user from OAuth information"""
        email = user_info['email']
        
        try:
            user = SecurityUser.objects.get(email=email, organization=self.organization)
            # Update user info
            user.first_name = user_info.get('given_name', user.first_name)
            user.last_name = user_info.get('family_name', user.last_name)
            user.last_activity = timezone.now()
            user.save()
            
        except SecurityUser.DoesNotExist:
            # Create new user
            user = SecurityUser.objects.create(
                username=user_info.get('preferred_username', email),
                email=email,
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
                organization=self.organization,
                sso_user_id=user_info.get('sub', ''),
                is_active=True,
                last_activity=timezone.now()
            )
            
            # Assign default viewer role
            rbac = RBACManager()
            default_roles = rbac.create_default_roles(self.organization)
            if 'viewer' in default_roles:
                rbac.assign_role(user, default_roles['viewer'])
        
        return user

class SSOManager:
    """SSO Manager for handling multiple providers"""
    
    @staticmethod
    def get_provider(organization: Organization) -> Optional[SSOProvider]:
        """Get SSO provider for organization"""
        if not organization.sso_enabled:
            return None
            
        provider_type = organization.sso_provider
        
        if provider_type == 'saml':
            return SAMLProvider(organization)
        elif provider_type in ['google', 'microsoft', 'oauth']:
            return OAuthProvider(organization)
        else:
            logger.warning(f"Unknown SSO provider: {provider_type}")
            return None
    
    @staticmethod
    def validate_sso_config(organization: Organization, config: Dict) -> Tuple[bool, str]:
        """Validate SSO configuration"""
        provider_type = config.get('provider')
        
        if provider_type == 'saml':
            required_fields = ['entity_id', 'sso_url', 'x509_cert']
            for field in required_fields:
                if not config.get(field):
                    return False, f"Missing required field: {field}"
                    
        elif provider_type in ['google', 'microsoft', 'oauth']:
            required_fields = ['client_id', 'client_secret', 'authorize_url', 'token_url', 'user_info_url']
            for field in required_fields:
                if not config.get(field):
                    return False, f"Missing required field: {field}"
        else:
            return False, f"Unsupported provider type: {provider_type}"
        
        return True, ""
    
    @staticmethod
    def test_sso_connection(organization: Organization) -> Tuple[bool, str]:
        """Test SSO connection"""
        try:
            provider = SSOManager.get_provider(organization)
            if not provider:
                return False, "No SSO provider configured"
            
            # For SAML, test metadata endpoint
            if isinstance(provider, SAMLProvider):
                if provider.sso_url:
                    response = requests.get(provider.sso_url, timeout=10)
                    if response.status_code == 200:
                        return True, "SAML connection successful"
                    else:
                        return False, f"SAML endpoint returned {response.status_code}"
                        
            # For OAuth, test well-known endpoint
            elif isinstance(provider, OAuthProvider):
                if provider.authorize_url:
                    # Just test that the URL is reachable
                    response = requests.head(provider.authorize_url, timeout=10)
                    if response.status_code in [200, 405]:  # 405 is OK for HEAD request
                        return True, "OAuth connection successful"
                    else:
                        return False, f"OAuth endpoint returned {response.status_code}"
            
            return False, "Unable to test connection"
            
        except Exception as e:
            return False, f"Connection test failed: {e}"

# Middleware for SSO session management
class SSOSessionMiddleware:
    """Middleware to handle SSO session management"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Check for SSO session timeout
        if request.user.is_authenticated and hasattr(request.user, 'organization'):
            if request.user.organization.sso_enabled:
                session_timeout = request.user.organization.security_settings.get('sso_session_timeout', 8)  # hours
                
                last_activity = request.session.get('last_sso_activity')
                if last_activity:
                    last_activity = timezone.datetime.fromisoformat(last_activity)
                    if timezone.now() - last_activity > timedelta(hours=session_timeout):
                        # Session expired, redirect to SSO login
                        from django.contrib.auth import logout
                        logout(request)
                        
                        # Audit log
                        AuditLog.objects.create(
                            organization=request.user.organization,
                            user=request.user,
                            action='logout',
                            severity='low',
                            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                            details={'reason': 'sso_session_timeout'}
                        )
                
                # Update last activity
                request.session['last_sso_activity'] = timezone.now().isoformat()
        
        response = self.get_response(request)
        return response