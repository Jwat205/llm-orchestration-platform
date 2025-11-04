# django-service/apps/security/encryption.py
import os
import base64
import hashlib
import secrets
from typing import Dict, Optional, Tuple, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class EncryptionManager:
    """Centralized encryption management for data at rest and in transit"""
    
    def __init__(self):
        self.master_key = self._get_master_key()
        self.fernet = Fernet(self.master_key)
        
    def _get_master_key(self) -> bytes:
        """Get or generate master encryption key"""
        key_env = getattr(settings, 'ENCRYPTION_MASTER_KEY', None)
        
        if key_env:
            try:
                return base64.urlsafe_b64decode(key_env.encode())
            except Exception as e:
                logger.error(f"Invalid master key in settings: {e}")
                
        # Generate new key (for development only)
        if settings.DEBUG:
            logger.warning("Generating new master key for development")
            return Fernet.generate_key()
        else:
            raise ValueError("ENCRYPTION_MASTER_KEY must be set in production")
    
    def encrypt_sensitive_data(self, data: str, context: str = '') -> str:
        """Encrypt sensitive data with context"""
        try:
            # Add context to data for additional security
            contextual_data = f"{context}:{data}" if context else data
            encrypted = self.fernet.encrypt(contextual_data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt_sensitive_data(self, encrypted_data: str, context: str = '') -> str:
        """Decrypt sensitive data with context validation"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(encrypted_bytes).decode()
            
            # Validate context
            if context:
                if not decrypted.startswith(f"{context}:"):
                    raise ValueError("Invalid context for decryption")
                return decrypted[len(context) + 1:]
            
            return decrypted
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def generate_field_key(self, field_name: str, record_id: str) -> bytes:
        """Generate field-specific encryption key"""
        # Derive key from master key + field info
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=f"{field_name}:{record_id}".encode(),
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self.master_key))
    
    def encrypt_field(self, data: str, field_name: str, record_id: str) -> str:
        """Encrypt individual database field"""
        field_key = self.generate_field_key(field_name, record_id)
        field_fernet = Fernet(field_key)
        encrypted = field_fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_field(self, encrypted_data: str, field_name: str, record_id: str) -> str:
        """Decrypt individual database field"""
        field_key = self.generate_field_key(field_name, record_id)
        field_fernet = Fernet(field_key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
        return field_fernet.decrypt(encrypted_bytes).decode()

class APIKeyEncryption:
    """Specialized encryption for API keys"""
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Create secure hash of API key for storage"""
        salt = os.urandom(32)
        key_hash = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt, 100000)
        return base64.urlsafe_b64encode(salt + key_hash).decode()
    
    @staticmethod
    def verify_api_key(api_key: str, stored_hash: str) -> bool:
        """Verify API key against stored hash"""
        try:
            decoded = base64.urlsafe_b64decode(stored_hash.encode())
            salt = decoded[:32]
            stored_key_hash = decoded[32:]
            
            key_hash = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt, 100000)
            return secrets.compare_digest(key_hash, stored_key_hash)
        except Exception:
            return False
    
    @staticmethod
    def generate_secure_api_key(length: int = 32) -> str:
        """Generate cryptographically secure API key"""
        # Generate random bytes and encode
        random_bytes = secrets.token_bytes(length)
        api_key = base64.urlsafe_b64encode(random_bytes).decode().rstrip('=')
        return f"sk-{api_key}"

class TokenEncryption:
    """JWT and session token encryption"""
    
    def __init__(self):
        self.token_key = self._get_token_key()
    
    def _get_token_key(self) -> bytes:
        """Get token encryption key"""
        key_env = getattr(settings, 'TOKEN_ENCRYPTION_KEY', None)
        if key_env:
            return base64.urlsafe_b64decode(key_env.encode())
        
        if settings.DEBUG:
            return Fernet.generate_key()
        else:
            raise ValueError("TOKEN_ENCRYPTION_KEY must be set in production")
    
    def encrypt_token_payload(self, payload: Dict) -> str:
        """Encrypt JWT payload"""
        fernet = Fernet(self.token_key)
        import json
        payload_json = json.dumps(payload, sort_keys=True)
        encrypted = fernet.encrypt(payload_json.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_token_payload(self, encrypted_payload: str) -> Dict:
        """Decrypt JWT payload"""
        fernet = Fernet(self.token_key)
        import json
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_payload.encode())
        decrypted = fernet.decrypt(encrypted_bytes).decode()
        return json.loads(decrypted)

class DatabaseEncryption:
    """Database field encryption utilities"""
    
    def __init__(self):
        self.encryption_manager = EncryptionManager()
    
    def encrypt_pii_field(self, data: str, table_name: str, field_name: str, record_id: str) -> str:
        """Encrypt PII field for database storage"""
        return self.encryption_manager.encrypt_field(data, f"{table_name}.{field_name}", record_id)
    
    def decrypt_pii_field(self, encrypted_data: str, table_name: str, field_name: str, record_id: str) -> str:
        """Decrypt PII field from database"""
        return self.encryption_manager.decrypt_field(encrypted_data, f"{table_name}.{field_name}", record_id)
    
    def bulk_encrypt_fields(self, records: list, field_mappings: Dict[str, str], table_name: str) -> list:
        """Encrypt multiple fields in bulk"""
        encrypted_records = []
        
        for record in records:
            encrypted_record = record.copy()
            record_id = str(record.get('id', ''))
            
            for field_name, field_value in field_mappings.items():
                if field_name in record and record[field_name]:
                    encrypted_record[field_name] = self.encrypt_pii_field(
                        str(record[field_name]), table_name, field_name, record_id
                    )
                    
            encrypted_records.append(encrypted_record)
            
        return encrypted_records

class FileEncryption:
    """File and document encryption"""
    
    def __init__(self):
        self.file_key = self._get_file_key()
        
    def _get_file_key(self) -> bytes:
        """Get file encryption key"""
        key_env = getattr(settings, 'FILE_ENCRYPTION_KEY', None)
        if key_env:
            return base64.urlsafe_b64decode(key_env.encode())
        
        if settings.DEBUG:
            return Fernet.generate_key()
        else:
            raise ValueError("FILE_ENCRYPTION_KEY must be set in production")
    
    def encrypt_file(self, file_path: str, output_path: Optional[str] = None) -> str:
        """Encrypt file on disk"""
        fernet = Fernet(self.file_key)
        
        if not output_path:
            output_path = f"{file_path}.encrypted"
        
        try:
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            encrypted_data = fernet.encrypt(file_data)
            
            with open(output_path, 'wb') as encrypted_file:
                encrypted_file.write(encrypted_data)
            
            # Secure delete original file
            self._secure_delete(file_path)
            
            return output_path
            
        except Exception as e:
            logger.error(f"File encryption failed: {e}")
            raise
    
    def decrypt_file(self, encrypted_file_path: str, output_path: Optional[str] = None) -> str:
        """Decrypt file from disk"""
        fernet = Fernet(self.file_key)
        
        if not output_path:
            output_path = encrypted_file_path.replace('.encrypted', '')
        
        try:
            with open(encrypted_file_path, 'rb') as encrypted_file:
                encrypted_data = encrypted_file.read()
            
            decrypted_data = fernet.decrypt(encrypted_data)
            
            with open(output_path, 'wb') as file:
                file.write(decrypted_data)
            
            return output_path
            
        except Exception as e:
            logger.error(f"File decryption failed: {e}")
            raise
    
    def _secure_delete(self, file_path: str) -> None:
        """Securely delete file by overwriting"""
        try:
            with open(file_path, 'r+b') as file:
                file_size = os.path.getsize(file_path)
                
                # Overwrite with random data multiple times
                for _ in range(3):
                    file.seek(0)
                    file.write(os.urandom(file_size))
                    file.flush()
                    os.fsync(file.fileno())
            
            os.remove(file_path)
            
        except Exception as e:
            logger.error(f"Secure file deletion failed: {e}")

class CommunicationEncryption:
    """Encryption for communications and transit"""
    
    def __init__(self):
        self.private_key, self.public_key = self._get_or_generate_keypair()
    
    def _get_or_generate_keypair(self) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
        """Get or generate RSA keypair"""
        private_key_pem = getattr(settings, 'RSA_PRIVATE_KEY', None)
        
        if private_key_pem:
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(),
                password=None
            )
            public_key = private_key.public_key()
        else:
            # Generate new keypair (development only)
            if settings.DEBUG:
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048
                )
                public_key = private_key.public_key()
                logger.warning("Generated new RSA keypair for development")
            else:
                raise ValueError("RSA_PRIVATE_KEY must be set in production")
        
        return private_key, public_key
    
    def encrypt_for_transit(self, data: str, recipient_public_key: Optional[rsa.RSAPublicKey] = None) -> str:
        """Encrypt data for secure transit"""
        public_key = recipient_public_key or self.public_key
        
        # For large data, use hybrid encryption (RSA + AES)
        if len(data) > 190:  # RSA 2048 can encrypt max ~190 bytes
            return self._hybrid_encrypt(data, public_key)
        else:
            encrypted = public_key.encrypt(
                data.encode(),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_from_transit(self, encrypted_data: str, sender_public_key: Optional[rsa.RSAPublicKey] = None) -> str:
        """Decrypt data from secure transit"""
        try:
            # Check if this is hybrid encryption
            if encrypted_data.startswith('hybrid:'):
                return self._hybrid_decrypt(encrypted_data[7:])  # Remove 'hybrid:' prefix
            else:
                encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
                decrypted = self.private_key.decrypt(
                    encrypted_bytes,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                return decrypted.decode()
        except Exception as e:
            logger.error(f"Transit decryption failed: {e}")
            raise
    
    def _hybrid_encrypt(self, data: str, public_key: rsa.RSAPublicKey) -> str:
        """Hybrid encryption for large data (RSA + AES)"""
        # Generate AES key
        aes_key = os.urandom(32)  # 256-bit key
        iv = os.urandom(16)  # 128-bit IV
        
        # Encrypt data with AES
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        
        # Pad data to multiple of 16 bytes
        padded_data = self._pad_data(data.encode())
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Encrypt AES key with RSA
        encrypted_aes_key = public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Combine encrypted key + IV + encrypted data
        combined = encrypted_aes_key + iv + encrypted_data
        return 'hybrid:' + base64.urlsafe_b64encode(combined).decode()
    
    def _hybrid_decrypt(self, encrypted_data: str) -> str:
        """Hybrid decryption for large data"""
        combined = base64.urlsafe_b64decode(encrypted_data.encode())
        
        # Extract components
        encrypted_aes_key = combined[:256]  # RSA 2048 = 256 bytes
        iv = combined[256:272]  # 16 bytes IV
        encrypted_data = combined[272:]
        
        # Decrypt AES key with RSA
        aes_key = self.private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Decrypt data with AES
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # Remove padding
        data = self._unpad_data(padded_data)
        return data.decode()
    
    def _pad_data(self, data: bytes) -> bytes:
        """PKCS#7 padding"""
        pad_length = 16 - (len(data) % 16)
        return data + bytes([pad_length] * pad_length)
    
    def _unpad_data(self, padded_data: bytes) -> bytes:
        """Remove PKCS#7 padding"""
        pad_length = padded_data[-1]
        return padded_data[:-pad_length]
    
    def sign_data(self, data: str) -> str:
        """Sign data for integrity verification"""
        signature = self.private_key.sign(
            data.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.urlsafe_b64encode(signature).decode()
    
    def verify_signature(self, data: str, signature: str, sender_public_key: Optional[rsa.RSAPublicKey] = None) -> bool:
        """Verify data signature"""
        try:
            public_key = sender_public_key or self.public_key
            signature_bytes = base64.urlsafe_b64decode(signature.encode())
            
            public_key.verify(
                signature_bytes,
                data.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

class KeyRotationManager:
    """Manage encryption key rotation"""
    
    def __init__(self):
        self.encryption_manager = EncryptionManager()
        
    def rotate_master_key(self) -> Dict[str, str]:
        """Rotate master encryption key"""
        logger.info("Starting master key rotation")
        
        try:
            # Generate new key
            new_key = Fernet.generate_key()
            old_key = self.encryption_manager.master_key
            
            # Update key in cache for immediate use
            cache.set('new_master_key', new_key, 3600)  # 1 hour
            
            # Return both keys for gradual migration
            return {
                'old_key': base64.urlsafe_b64encode(old_key).decode(),
                'new_key': base64.urlsafe_b64encode(new_key).decode(),
                'rotation_started': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Master key rotation failed: {e}")
            raise
    
    def migrate_encrypted_data(self, table_name: str, field_name: str, 
                             old_key: bytes, new_key: bytes) -> int:
        """Migrate encrypted data to new key"""
        from django.db import connection
        
        migrated_count = 0
        old_fernet = Fernet(old_key)
        new_fernet = Fernet(new_key)
        
        try:
            with connection.cursor() as cursor:
                # Get all encrypted records
                cursor.execute(
                    f"SELECT id, {field_name} FROM {table_name} WHERE {field_name} IS NOT NULL"
                )
                
                for record_id, encrypted_value in cursor.fetchall():
                    try:
                        # Decrypt with old key
                        decrypted = old_fernet.decrypt(
                            base64.urlsafe_b64decode(encrypted_value.encode())
                        )
                        
                        # Encrypt with new key
                        new_encrypted = base64.urlsafe_b64encode(
                            new_fernet.encrypt(decrypted)
                        ).decode()
                        
                        # Update record
                        cursor.execute(
                            f"UPDATE {table_name} SET {field_name} = %s WHERE id = %s",
                            [new_encrypted, record_id]
                        )
                        
                        migrated_count += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to migrate record {record_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            raise
            
        logger.info(f"Migrated {migrated_count} records for {table_name}.{field_name}")
        return migrated_count
    
    def rotate_api_keys(self, organization_id: str) -> Dict:
        """Rotate all API keys for an organization"""
        from .models import APIKey, Organization
        
        try:
            organization = Organization.objects.get(id=organization_id)
            api_keys = APIKey.objects.filter(user__organization=organization, is_active=True)
            
            rotation_results = []
            
            for api_key in api_keys:
                # Generate new key
                new_key, new_prefix, new_hash = APIKey.generate_key()
                
                # Update API key
                old_prefix = api_key.prefix
                api_key.key_hash = new_hash
                api_key.prefix = new_prefix
                api_key.save()
                
                rotation_results.append({
                    'api_key_id': str(api_key.id),
                    'old_prefix': old_prefix,
                    'new_prefix': new_prefix,
                    'new_key': new_key,  # Only return once, store securely
                    'rotated_at': timezone.now().isoformat()
                })
                
                # Log rotation
                from .audit_logger import audit_logger
                audit_logger.log_sync(
                    organization=organization,
                    user=api_key.user,
                    action='api_key_rotated',
                    resource_type='api_key',
                    resource_id=str(api_key.id),
                    severity='medium',
                    details={'old_prefix': old_prefix, 'new_prefix': new_prefix}
                )
            
            return {
                'organization_id': organization_id,
                'keys_rotated': len(rotation_results),
                'rotation_details': rotation_results,
                'rotation_completed': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"API key rotation failed: {e}")
            raise

class EncryptedField:
    """Custom field descriptor for automatic encryption/decryption"""
    
    def __init__(self, field_name: str):
        self.field_name = field_name
        self.private_name = f'_encrypted_{field_name}'
        self.encryption_manager = EncryptionManager()
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
            
        encrypted_value = getattr(obj, self.private_name, None)
        if encrypted_value is None:
            return None
            
        try:
            return self.encryption_manager.decrypt_field(
                encrypted_value, 
                obj.__class__.__name__.lower(), 
                str(obj.id)
            )
        except Exception as e:
            logger.error(f"Field decryption failed for {self.field_name}: {e}")
            return None
    
    def __set__(self, obj, value):
        if value is None:
            setattr(obj, self.private_name, None)
            return
            
        try:
            encrypted_value = self.encryption_manager.encrypt_field(
                str(value), 
                obj.__class__.__name__.lower(), 
                str(obj.id) if hasattr(obj, 'id') else 'new'
            )
            setattr(obj, self.private_name, encrypted_value)
        except Exception as e:
            logger.error(f"Field encryption failed for {self.field_name}: {e}")
            raise

# Utility functions
def hash_password_secure(password: str, salt: Optional[bytes] = None) -> Tuple[str, bytes]:
    """Create secure password hash"""
    if salt is None:
        salt = os.urandom(32)
    
    # Use PBKDF2 with high iteration count
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    
    # Combine salt and hash
    combined = base64.urlsafe_b64encode(salt + password_hash).decode()
    return combined, salt

def verify_password_secure(password: str, stored_hash: str) -> bool:
    """Verify password against secure hash"""
    try:
        combined = base64.urlsafe_b64decode(stored_hash.encode())
        salt = combined[:32]
        stored_password_hash = combined[32:]
        
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return secrets.compare_digest(password_hash, stored_password_hash)
    except Exception:
        return False

def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure token"""
    return secrets.token_urlsafe(length)

def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks"""
    return secrets.compare_digest(a.encode(), b.encode())

# Global instances
encryption_manager = EncryptionManager()
api_key_encryption = APIKeyEncryption()
token_encryption = TokenEncryption()
database_encryption = DatabaseEncryption()
file_encryption = FileEncryption()
communication_encryption = CommunicationEncryption()
key_rotation_manager = KeyRotationManager()

# Django model mixin for automatic field encryption
class EncryptedModelMixin:
    """Mixin to add encryption capabilities to Django models"""
    
    encrypted_fields = []  # Define in subclass
    
    def save(self, *args, **kwargs):
        # Encrypt fields before saving
        for field_name in self.encrypted_fields:
            value = getattr(self, field_name, None)
            if value is not None:
                encrypted_value = encryption_manager.encrypt_field(
                    str(value),
                    self.__class__.__name__.lower(),
                    str(self.id) if hasattr(self, 'id') and self.id else 'new'
                )
                setattr(self, f'_encrypted_{field_name}', encrypted_value)
        
        super().save(*args, **kwargs)
    
    def decrypt_field(self, field_name: str) -> Optional[str]:
        """Decrypt specific field"""
        if field_name not in self.encrypted_fields:
            return getattr(self, field_name, None)
            
        encrypted_value = getattr(self, f'_encrypted_{field_name}', None)
        if encrypted_value is None:
            return None
            
        return encryption_manager.decrypt_field(
            encrypted_value,
            self.__class__.__name__.lower(),
            str(self.id)
        )