"""
Data Encryption Utilities
Provides encryption/decryption services for various data types
"""

import json
import base64
from typing import Dict, Any, Optional, Union
from datetime import datetime
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import os


logger = logging.getLogger(__name__)


class SymmetricEncryption:
    """Symmetric encryption utilities"""
    
    def __init__(self, key: bytes, algorithm: str = "Fernet"):
        self.algorithm = algorithm
        
        if algorithm == "Fernet":
            self.cipher = Fernet(key)
        elif algorithm == "AES-256-GCM":
            self.key = key
        else:
            raise ValueError(f"Unsupported symmetric algorithm: {algorithm}")
    
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """Encrypt data"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        if self.algorithm == "Fernet":
            return self.cipher.encrypt(data)
        elif self.algorithm == "AES-256-GCM":
            return self._encrypt_aes_gcm(data)
    
    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt data"""
        if self.algorithm == "Fernet":
            return self.cipher.decrypt(encrypted_data)
        elif self.algorithm == "AES-256-GCM":
            return self._decrypt_aes_gcm(encrypted_data)
    
    def encrypt_dict(self, data: Dict[str, Any]) -> bytes:
        """Encrypt dictionary as JSON"""
        json_data = json.dumps(data, default=str)
        return self.encrypt(json_data)
    
    def decrypt_dict(self, encrypted_data: bytes) -> Dict[str, Any]:
        """Decrypt data as dictionary"""
        decrypted_json = self.decrypt(encrypted_data).decode('utf-8')
        return json.loads(decrypted_json)
    
    def _encrypt_aes_gcm(self, data: bytes) -> bytes:
        """Encrypt using AES-256-GCM"""
        iv = os.urandom(12)  # 96-bit IV for GCM
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        # Return IV + auth_tag + ciphertext
        return iv + encryptor.tag + ciphertext
    
    def _decrypt_aes_gcm(self, encrypted_data: bytes) -> bytes:
        """Decrypt using AES-256-GCM"""
        iv = encrypted_data[:12]
        tag = encrypted_data[12:28]
        ciphertext = encrypted_data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()


class AsymmetricEncryption:
    """Asymmetric encryption utilities"""
    
    def __init__(self, private_key_pem: bytes = None, public_key_pem: bytes = None):
        self.private_key = None
        self.public_key = None
        
        if private_key_pem:
            self.private_key = serialization.load_pem_private_key(
                private_key_pem, password=None, backend=default_backend()
            )
            # Derive public key from private key if not provided
            if not public_key_pem:
                self.public_key = self.private_key.public_key()
        
        if public_key_pem:
            self.public_key = serialization.load_pem_public_key(
                public_key_pem, backend=default_backend()
            )
    
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """Encrypt data with public key"""
        if not self.public_key:
            raise ValueError("Public key not available for encryption")
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # RSA can only encrypt data smaller than key size
        # For larger data, use hybrid encryption
        max_chunk_size = (self.public_key.key_size // 8) - 42  # OAEP overhead
        
        if len(data) <= max_chunk_size:
            return self.public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        else:
            # Use hybrid encryption for large data
            return self._hybrid_encrypt(data)
    
    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt data with private key"""
        if not self.private_key:
            raise ValueError("Private key not available for decryption")
        
        # Check if this is hybrid encrypted data
        if len(encrypted_data) > self.private_key.key_size // 8:
            return self._hybrid_decrypt(encrypted_data)
        else:
            return self.private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
    
    def sign(self, data: Union[str, bytes]) -> bytes:
        """Sign data with private key"""
        if not self.private_key:
            raise ValueError("Private key not available for signing")
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        signature = self.private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature
    
    def verify(self, data: Union[str, bytes], signature: bytes) -> bool:
        """Verify signature with public key"""
        if not self.public_key:
            raise ValueError("Public key not available for verification")
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        try:
            self.public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
    
    def _hybrid_encrypt(self, data: bytes) -> bytes:
        """Hybrid encryption: RSA + AES"""
        # Generate random AES key
        aes_key = os.urandom(32)
        
        # Encrypt data with AES
        symmetric_cipher = SymmetricEncryption(aes_key, "AES-256-GCM")
        encrypted_data = symmetric_cipher.encrypt(data)
        
        # Encrypt AES key with RSA
        encrypted_key = self.public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Return encrypted_key_length + encrypted_key + encrypted_data
        key_length = len(encrypted_key).to_bytes(4, 'big')
        return key_length + encrypted_key + encrypted_data
    
    def _hybrid_decrypt(self, encrypted_data: bytes) -> bytes:
        """Hybrid decryption: RSA + AES"""
        # Extract encrypted key length
        key_length = int.from_bytes(encrypted_data[:4], 'big')
        
        # Extract encrypted AES key and data
        encrypted_key = encrypted_data[4:4+key_length]
        encrypted_payload = encrypted_data[4+key_length:]
        
        # Decrypt AES key with RSA
        aes_key = self.private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Decrypt data with AES
        symmetric_cipher = SymmetricEncryption(aes_key, "AES-256-GCM")
        return symmetric_cipher.decrypt(encrypted_payload)


class FieldLevelEncryption:
    """Field-level encryption for databases"""
    
    def __init__(self, encryption_keys: Dict[str, bytes]):
        self.encryption_keys = encryption_keys
        self.ciphers = {
            field: SymmetricEncryption(key) 
            for field, key in encryption_keys.items()
        }
    
    def encrypt_fields(self, data: Dict[str, Any], fields_to_encrypt: list) -> Dict[str, Any]:
        """Encrypt specified fields in a dictionary"""
        encrypted_data = data.copy()
        
        for field in fields_to_encrypt:
            if field in data and field in self.ciphers:
                field_value = str(data[field])
                encrypted_value = self.ciphers[field].encrypt(field_value)
                encrypted_data[field] = base64.b64encode(encrypted_value).decode('utf-8')
                encrypted_data[f"{field}_encrypted"] = True
        
        return encrypted_data
    
    def decrypt_fields(self, data: Dict[str, Any], fields_to_decrypt: list) -> Dict[str, Any]:
        """Decrypt specified fields in a dictionary"""
        decrypted_data = data.copy()
        
        for field in fields_to_decrypt:
            if (field in data and 
                data.get(f"{field}_encrypted") and 
                field in self.ciphers):
                
                encrypted_value = base64.b64decode(data[field])
                decrypted_value = self.ciphers[field].decrypt(encrypted_value).decode('utf-8')
                decrypted_data[field] = decrypted_value
                del decrypted_data[f"{field}_encrypted"]
        
        return decrypted_data


class TokenEncryption:
    """Encryption for tokens and sensitive strings"""
    
    def __init__(self, key: bytes):
        self.cipher = SymmetricEncryption(key)
    
    def encrypt_token(self, token: str, metadata: Dict[str, Any] = None) -> str:
        """Encrypt token with optional metadata"""
        token_data = {
            'token': token,
            'encrypted_at': datetime.utcnow().isoformat(),
            'metadata': metadata or {}
        }
        
        encrypted_data = self.cipher.encrypt_dict(token_data)
        return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
    
    def decrypt_token(self, encrypted_token: str) -> Dict[str, Any]:
        """Decrypt token and return with metadata"""
        try:
            encrypted_data = base64.urlsafe_b64decode(encrypted_token)
            token_data = self.cipher.decrypt_dict(encrypted_data)
            return token_data
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            return None
    
    def create_secure_token(self, payload: Dict[str, Any], ttl_hours: int = 24) -> str:
        """Create encrypted token with expiration"""
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        token_data = {
            'payload': payload,
            'expires_at': expires_at.isoformat(),
            'issued_at': datetime.utcnow().isoformat()
        }
        
        return self.encrypt_token(json.dumps(token_data, default=str))
    
    def validate_secure_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate and extract payload from secure token"""
        decrypted_data = self.decrypt_token(token)
        if not decrypted_data:
            return None
        
        try:
            token_content = json.loads(decrypted_data['token'])
            
            # Check expiration
            expires_at = datetime.fromisoformat(token_content['expires_at'])
            if datetime.utcnow() > expires_at:
                logger.warning("Token has expired")
                return None
            
            return token_content['payload']
            
        except Exception as e:
            logger.error(f"Invalid token format: {e}")
            return None


class DataEncryptionService:
    """Main data encryption service"""
    
    def __init__(self, key_manager):
        self.key_manager = key_manager
        self._encryption_cache = {}
    
    def get_field_encryptor(self, field_name: str) -> Optional[SymmetricEncryption]:
        """Get encryptor for specific field"""
        if field_name in self._encryption_cache:
            return self._encryption_cache[field_name]
        
        # Try to get field-specific key
        key_id = f"field_{field_name}"
        key_data = self.key_manager.get_key(key_id)
        
        if not key_data:
            # Fall back to default field encryption key
            key_data = self.key_manager.get_key("field_encryption_default")
        
        if key_data:
            encryptor = SymmetricEncryption(key_data)
            self._encryption_cache[field_name] = encryptor
            return encryptor
        
        return None
    
    def encrypt_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt personally identifiable information"""
        pii_fields = ['email', 'phone', 'ssn', 'address', 'name', 'credit_card']
        
        encrypted_data = data.copy()
        
        for field in pii_fields:
            if field in data:
                encryptor = self.get_field_encryptor(field)
                if encryptor:
                    field_value = str(data[field])
                    encrypted_value = encryptor.encrypt(field_value)
                    encrypted_data[field] = base64.b64encode(encrypted_value).decode('utf-8')
                    encrypted_data[f"{field}_encrypted"] = True
        
        return encrypted_data
    
    def decrypt_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt personally identifiable information"""
        decrypted_data = data.copy()
        
        for key, value in data.items():
            if key.endswith('_encrypted') and value:
                field_name = key.replace('_encrypted', '')
                
                if field_name in data:
                    encryptor = self.get_field_encryptor(field_name)
                    if encryptor:
                        try:
                            encrypted_value = base64.b64decode(data[field_name])
                            decrypted_value = encryptor.decrypt(encrypted_value).decode('utf-8')
                            decrypted_data[field_name] = decrypted_value
                            del decrypted_data[key]
                        except Exception as e:
                            logger.error(f"Failed to decrypt field {field_name}: {e}")
        
        return decrypted_data
    
    def encrypt_file(self, file_data: bytes, key_id: str = None) -> bytes:
        """Encrypt file data"""
        if not key_id:
            key_id = "file_encryption_default"
        
        key_data = self.key_manager.get_key(key_id)
        if not key_data:
            raise ValueError(f"Encryption key not found: {key_id}")
        
        encryptor = SymmetricEncryption(key_data, "AES-256-GCM")
        return encryptor.encrypt(file_data)
    
    def decrypt_file(self, encrypted_data: bytes, key_id: str = None) -> bytes:
        """Decrypt file data"""
        if not key_id:
            key_id = "file_encryption_default"
        
        key_data = self.key_manager.get_key(key_id)
        if not key_data:
            raise ValueError(f"Decryption key not found: {key_id}")
        
        encryptor = SymmetricEncryption(key_data, "AES-256-GCM")
        return encryptor.decrypt(encrypted_data)
    
    def create_encrypted_backup(self, data: Dict[str, Any]) -> str:
        """Create encrypted backup of data"""
        backup_data = {
            'data': data,
            'created_at': datetime.utcnow().isoformat(),
            'version': '1.0'
        }
        
        # Get backup encryption key
        key_data = self.key_manager.get_key("backup_encryption")
        if not key_data:
            raise ValueError("Backup encryption key not found")
        
        encryptor = SymmetricEncryption(key_data)
        encrypted_backup = encryptor.encrypt_dict(backup_data)
        
        return base64.b64encode(encrypted_backup).decode('utf-8')
    
    def restore_encrypted_backup(self, encrypted_backup: str) -> Dict[str, Any]:
        """Restore data from encrypted backup"""
        # Get backup encryption key
        key_data = self.key_manager.get_key("backup_encryption")
        if not key_data:
            raise ValueError("Backup encryption key not found")
        
        encryptor = SymmetricEncryption(key_data)
        encrypted_data = base64.b64decode(encrypted_backup)
        backup_data = encryptor.decrypt_dict(encrypted_data)
        
        return backup_data.get('data', {})

from datetime import timedelta