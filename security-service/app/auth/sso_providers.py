"""
SSO Provider Implementations
Supports SAML 2.0 and OAuth 2.0 integrations for enterprise SSO
"""

import jwt
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from urllib.parse import urlencode
import requests
import logging
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


logger = logging.getLogger(__name__)


class SSOProvider(ABC):
    """Abstract base class for SSO providers"""
    
    @abstractmethod
    def authenticate(self, token: str) -> Dict[str, Any]:
        """Authenticate user with SSO token"""
        pass
    
    @abstractmethod
    def get_user_info(self, token: str) -> Dict[str, Any]:
        """Get user information from SSO provider"""
        pass
    
    @abstractmethod
    def validate_token(self, token: str) -> bool:
        """Validate SSO token"""
        pass


class SAMLProvider(SSOProvider):
    """SAML 2.0 SSO Provider"""
    
    def __init__(self, 
                 entity_id: str,
                 sso_url: str,
                 x509_cert: str,
                 private_key: str,
                 sp_entity_id: str):
        self.entity_id = entity_id
        self.sso_url = sso_url
        self.x509_cert = x509_cert
        self.private_key = private_key
        self.sp_entity_id = sp_entity_id
        
    def generate_saml_request(self, relay_state: Optional[str] = None) -> str:
        """Generate SAML authentication request"""
        request_id = f"_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        issue_instant = datetime.utcnow().isoformat() + "Z"
        
        saml_request = f"""
        <samlp:AuthnRequest 
            xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
            xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
            ID="{request_id}"
            Version="2.0"
            IssueInstant="{issue_instant}"
            Destination="{self.sso_url}"
            ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            AssertionConsumerServiceURL="{self.sp_entity_id}/acs">
            <saml:Issuer>{self.sp_entity_id}</saml:Issuer>
            <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:2.0:nameid-format:emailAddress" AllowCreate="true"/>
        </samlp:AuthnRequest>
        """
        
        return saml_request.strip()
    
    def parse_saml_response(self, saml_response: str) -> Dict[str, Any]:
        """Parse and validate SAML response"""
        try:
            root = ET.fromstring(saml_response)
            
            # Extract assertion
            assertion = root.find('.//{urn:oasis:names:tc:SAML:2.0:assertion}Assertion')
            if assertion is None:
                raise ValueError("No assertion found in SAML response")
            
            # Extract subject
            subject = assertion.find('.//{urn:oasis:names:tc:SAML:2.0:assertion}Subject')
            name_id = subject.find('.//{urn:oasis:names:tc:SAML:2.0:assertion}NameID')
            
            # Extract attributes
            attributes = {}
            attr_statements = assertion.findall('.//{urn:oasis:names:tc:SAML:2.0:assertion}AttributeStatement')
            for attr_statement in attr_statements:
                for attribute in attr_statement.findall('.//{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
                    name = attribute.get('Name')
                    values = [val.text for val in attribute.findall('.//{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue')]
                    attributes[name] = values[0] if len(values) == 1 else values
            
            return {
                'user_id': name_id.text if name_id is not None else None,
                'attributes': attributes,
                'valid': True
            }
            
        except Exception as e:
            logger.error(f"Failed to parse SAML response: {e}")
            return {'valid': False, 'error': str(e)}
    
    def authenticate(self, saml_response: str) -> Dict[str, Any]:
        """Authenticate user with SAML response"""
        parsed_response = self.parse_saml_response(saml_response)
        
        if not parsed_response.get('valid'):
            return {'authenticated': False, 'error': parsed_response.get('error')}
        
        return {
            'authenticated': True,
            'user_id': parsed_response['user_id'],
            'attributes': parsed_response['attributes']
        }
    
    def get_user_info(self, saml_response: str) -> Dict[str, Any]:
        """Extract user information from SAML response"""
        parsed_response = self.parse_saml_response(saml_response)
        
        if not parsed_response.get('valid'):
            return {}
        
        attributes = parsed_response.get('attributes', {})
        
        return {
            'email': attributes.get('email', attributes.get('emailAddress')),
            'first_name': attributes.get('firstName', attributes.get('givenName')),
            'last_name': attributes.get('lastName', attributes.get('surname')),
            'display_name': attributes.get('displayName'),
            'groups': attributes.get('groups', []),
            'department': attributes.get('department'),
            'title': attributes.get('title')
        }
    
    def validate_token(self, saml_response: str) -> bool:
        """Validate SAML response"""
        parsed_response = self.parse_saml_response(saml_response)
        return parsed_response.get('valid', False)


class OAuth2Provider(SSOProvider):
    """OAuth 2.0 SSO Provider"""
    
    def __init__(self,
                 client_id: str,
                 client_secret: str,
                 authorization_url: str,
                 token_url: str,
                 userinfo_url: str,
                 jwks_url: Optional[str] = None,
                 scopes: List[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_url = authorization_url
        self.token_url = token_url
        self.userinfo_url = userinfo_url
        self.jwks_url = jwks_url
        self.scopes = scopes or ['openid', 'email', 'profile']
        
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Generate OAuth 2.0 authorization URL"""
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'scope': ' '.join(self.scopes),
            'state': state
        }
        
        return f"{self.authorization_url}?{urlencode(params)}"
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        try:
            response = requests.post(self.token_url, data=token_data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            return {'error': str(e)}
    
    def validate_jwt_token(self, token: str) -> Dict[str, Any]:
        """Validate JWT token using JWKS if available"""
        if not self.jwks_url:
            # Simple validation without signature verification
            try:
                decoded = jwt.decode(token, options={"verify_signature": False})
                return {'valid': True, 'payload': decoded}
            except Exception as e:
                return {'valid': False, 'error': str(e)}
        
        try:
            # Fetch JWKS
            jwks_response = requests.get(self.jwks_url)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
            
            # Extract header to get key ID
            header = jwt.get_unverified_header(token)
            kid = header.get('kid')
            
            # Find matching key
            key = None
            for jwk in jwks['keys']:
                if jwk['kid'] == kid:
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
                    break
            
            if not key:
                return {'valid': False, 'error': 'Key not found'}
            
            # Verify and decode token
            decoded = jwt.decode(token, key, algorithms=['RS256'])
            return {'valid': True, 'payload': decoded}
            
        except Exception as e:
            logger.error(f"JWT validation failed: {e}")
            return {'valid': False, 'error': str(e)}
    
    def authenticate(self, access_token: str) -> Dict[str, Any]:
        """Authenticate user with OAuth 2.0 access token"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(self.userinfo_url, headers=headers)
            response.raise_for_status()
            
            user_info = response.json()
            return {
                'authenticated': True,
                'user_info': user_info
            }
            
        except Exception as e:
            logger.error(f"OAuth authentication failed: {e}")
            return {'authenticated': False, 'error': str(e)}
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information using access token"""
        auth_result = self.authenticate(access_token)
        
        if not auth_result.get('authenticated'):
            return {}
        
        user_info = auth_result.get('user_info', {})
        
        return {
            'email': user_info.get('email'),
            'first_name': user_info.get('given_name'),
            'last_name': user_info.get('family_name'),
            'display_name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'locale': user_info.get('locale'),
            'verified': user_info.get('email_verified', False)
        }
    
    def validate_token(self, access_token: str) -> bool:
        """Validate OAuth 2.0 access token"""
        auth_result = self.authenticate(access_token)
        return auth_result.get('authenticated', False)


class OpenIDConnectProvider(OAuth2Provider):
    """OpenID Connect Provider (extends OAuth 2.0)"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'openid' not in self.scopes:
            self.scopes.insert(0, 'openid')
    
    def validate_id_token(self, id_token: str) -> Dict[str, Any]:
        """Validate OpenID Connect ID token"""
        return self.validate_jwt_token(id_token)


class SSOProviderFactory:
    """Factory for creating SSO providers"""
    
    @staticmethod
    def create_saml_provider(config: Dict[str, Any]) -> SAMLProvider:
        """Create SAML provider from configuration"""
        return SAMLProvider(
            entity_id=config['entity_id'],
            sso_url=config['sso_url'],
            x509_cert=config['x509_cert'],
            private_key=config['private_key'],
            sp_entity_id=config['sp_entity_id']
        )
    
    @staticmethod
    def create_oauth2_provider(config: Dict[str, Any]) -> OAuth2Provider:
        """Create OAuth 2.0 provider from configuration"""
        return OAuth2Provider(
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            authorization_url=config['authorization_url'],
            token_url=config['token_url'],
            userinfo_url=config['userinfo_url'],
            jwks_url=config.get('jwks_url'),
            scopes=config.get('scopes')
        )
    
    @staticmethod
    def create_oidc_provider(config: Dict[str, Any]) -> OpenIDConnectProvider:
        """Create OpenID Connect provider from configuration"""
        return OpenIDConnectProvider(
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            authorization_url=config['authorization_url'],
            token_url=config['token_url'],
            userinfo_url=config['userinfo_url'],
            jwks_url=config.get('jwks_url'),
            scopes=config.get('scopes')
        )


class SSOManager:
    """Manages multiple SSO providers"""
    
    def __init__(self):
        self.providers: Dict[str, SSOProvider] = {}
    
    def register_provider(self, name: str, provider: SSOProvider):
        """Register an SSO provider"""
        self.providers[name] = provider
        logger.info(f"Registered SSO provider: {name}")
    
    def get_provider(self, name: str) -> Optional[SSOProvider]:
        """Get SSO provider by name"""
        return self.providers.get(name)
    
    def authenticate(self, provider_name: str, token: str) -> Dict[str, Any]:
        """Authenticate using specified provider"""
        provider = self.get_provider(provider_name)
        if not provider:
            return {'authenticated': False, 'error': 'Provider not found'}
        
        return provider.authenticate(token)
    
    def get_user_info(self, provider_name: str, token: str) -> Dict[str, Any]:
        """Get user info using specified provider"""
        provider = self.get_provider(provider_name)
        if not provider:
            return {}
        
        return provider.get_user_info(token)
    
    def list_providers(self) -> List[str]:
        """List available SSO providers"""
        return list(self.providers.keys())


# Predefined provider configurations for common services
COMMON_PROVIDERS = {
    'google': {
        'type': 'oidc',
        'authorization_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'userinfo_url': 'https://www.googleapis.com/oauth2/v2/userinfo',
        'jwks_url': 'https://www.googleapis.com/oauth2/v3/certs'
    },
    'microsoft': {
        'type': 'oidc',
        'authorization_url': 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize',
        'token_url': 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token',
        'userinfo_url': 'https://graph.microsoft.com/v1.0/me',
        'jwks_url': 'https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys'
    },
    'okta': {
        'type': 'oidc',
        'authorization_url': 'https://{domain}/oauth2/default/v1/authorize',
        'token_url': 'https://{domain}/oauth2/default/v1/token',
        'userinfo_url': 'https://{domain}/oauth2/default/v1/userinfo',
        'jwks_url': 'https://{domain}/oauth2/default/v1/keys'
    }
}