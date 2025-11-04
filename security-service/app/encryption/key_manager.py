"""
Encryption Key Manager
Manages encryption keys with rotation, versioning, and secure storage
"""

import os
import json
import base64
import secrets
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend


logger = logging.getLogger(__name__)


class KeyType(Enum):
    """Types of encryption keys"""
    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"
    SIGNING = "signing"
    MASTER = "master"


class KeyStatus(Enum):
    """Key status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"
    COMPROMISED = "compromised"


@dataclass
class KeyMetadata:
    """Key metadata"""
    key_id: str
    key_type: KeyType
    algorithm: str
    key_size: int
    created_at: datetime
    expires_at: Optional[datetime]
    status: KeyStatus
    usage_count: int
    last_used: Optional[datetime]
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['key_type'] = self.key_type.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        if self.last_used:
            data['last_used'] = self.last_used.isoformat()
        return data


class KeyGenerator:
    """Generates encryption keys"""
    
    @staticmethod
    def generate_symmetric_key(algorithm: str = "AES-256") -> bytes:
        """Generate symmetric encryption key"""
        if algorithm == "AES-256":
            return secrets.token_bytes(32)  # 256 bits
        elif algorithm == "AES-128":
            return secrets.token_bytes(16)  # 128 bits
        elif algorithm == "Fernet":
            return Fernet.generate_key()
        else:
            raise ValueError(f"Unsupported symmetric algorithm: {algorithm}")
    
    @staticmethod
    def generate_asymmetric_keypair(algorithm: str = "RSA-2048") -> Tuple[bytes, bytes]:
        """Generate asymmetric key pair (private_key, public_key)"""
        if algorithm.startswith("RSA"):
            key_size = int(algorithm.split("-")[1])
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            return private_pem, public_pem
        else:
            raise ValueError(f"Unsupported asymmetric algorithm: {algorithm}")
    
    @staticmethod
    def derive_key_from_password(password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
        """Derive encryption key from password using PBKDF2"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode())
        return key, salt


class KeyStorage:
    """Secure key storage backend"""
    
    def __init__(self, storage_path: str, master_key: bytes):
        self.storage_path = storage_path
        self.fernet = Fernet(master_key)
        self.keys: Dict[str, bytes] = {}
        self.metadata: Dict[str, KeyMetadata] = {}
        self._load_keys()
    
    def store_key(self, key_id: str, key_data: bytes, metadata: KeyMetadata) -> bool:
        """Store encrypted key"""
        try:
            # Encrypt key data
            encrypted_key = self.fernet.encrypt(key_data)
            
            # Store in memory
            self.keys[key_id] = encrypted_key
            self.metadata[key_id] = metadata
            
            # Persist to disk
            self._save_keys()
            
            logger.info(f"Key stored: {key_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store key {key_id}: {e}")
            return False
    
    def retrieve_key(self, key_id: str) -> Optional[bytes]:
        """Retrieve and decrypt key"""
        try:
            if key_id not in self.keys:
                return None
            
            # Decrypt key data
            encrypted_key = self.keys[key_id]
            key_data = self.fernet.decrypt(encrypted_key)
            
            # Update usage statistics
            if key_id in self.metadata:
                self.metadata[key_id].usage_count += 1
                self.metadata[key_id].last_used = datetime.utcnow()
                self._save_keys()
            
            return key_data
            
        except Exception as e:
            logger.error(f"Failed to retrieve key {key_id}: {e}")
            return None
    
    def delete_key(self, key_id: str) -> bool:
        """Delete key from storage"""
        try:
            if key_id in self.keys:
                del self.keys[key_id]
            if key_id in self.metadata:
                del self.metadata[key_id]
            
            self._save_keys()
            logger.info(f"Key deleted: {key_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete key {key_id}: {e}")
            return False
    
    def list_keys(self) -> List[KeyMetadata]:
        """List all key metadata"""
        return list(self.metadata.values())
    
    def get_key_metadata(self, key_id: str) -> Optional[KeyMetadata]:
        """Get key metadata"""
        return self.metadata.get(key_id)
    
    def _load_keys(self):
        """Load keys from disk"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                
                # Load encrypted keys
                for key_id, encrypted_key_b64 in data.get('keys', {}).items():
                    self.keys[key_id] = base64.b64decode(encrypted_key_b64)
                
                # Load metadata
                for key_id, metadata_dict in data.get('metadata', {}).items():
                    metadata = KeyMetadata(
                        key_id=metadata_dict['key_id'],
                        key_type=KeyType(metadata_dict['key_type']),
                        algorithm=metadata_dict['algorithm'],
                        key_size=metadata_dict['key_size'],
                        created_at=datetime.fromisoformat(metadata_dict['created_at']),
                        expires_at=datetime.fromisoformat(metadata_dict['expires_at']) if metadata_dict.get('expires_at') else None,
                        status=KeyStatus(metadata_dict['status']),
                        usage_count=metadata_dict['usage_count'],
                        last_used=datetime.fromisoformat(metadata_dict['last_used']) if metadata_dict.get('last_used') else None,
                        tags=metadata_dict.get('tags', {})
                    )
                    self.metadata[key_id] = metadata
                
                logger.info(f"Loaded {len(self.keys)} keys from storage")
        
        except Exception as e:
            logger.error(f"Failed to load keys from storage: {e}")
    
    def _save_keys(self):
        """Save keys to disk"""
        try:
            # Prepare data for serialization
            data = {
                'keys': {
                    key_id: base64.b64encode(encrypted_key).decode()
                    for key_id, encrypted_key in self.keys.items()
                },
                'metadata': {
                    key_id: metadata.to_dict()
                    for key_id, metadata in self.metadata.items()
                }
            }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Write to file
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to save keys to storage: {e}")


class KeyRotationManager:
    """Manages key rotation schedules"""
    
    def __init__(self, key_manager):
        self.key_manager = key_manager
        self.rotation_schedules: Dict[str, timedelta] = {
            'default': timedelta(days=90),
            'sensitive': timedelta(days=30),
            'master': timedelta(days=365)
        }
    
    def set_rotation_schedule(self, key_category: str, rotation_period: timedelta):
        """Set rotation schedule for key category"""
        self.rotation_schedules[key_category] = rotation_period
    
    def get_keys_due_for_rotation(self) -> List[str]:
        """Get list of keys due for rotation"""
        due_keys = []
        now = datetime.utcnow()
        
        for key_metadata in self.key_manager.storage.list_keys():
            if key_metadata.status != KeyStatus.ACTIVE:
                continue
            
            # Determine rotation schedule
            key_category = key_metadata.tags.get('category', 'default')
            rotation_period = self.rotation_schedules.get(key_category, self.rotation_schedules['default'])
            
            # Check if rotation is due
            next_rotation = key_metadata.created_at + rotation_period
            if now >= next_rotation:
                due_keys.append(key_metadata.key_id)
        
        return due_keys
    
    def rotate_key(self, old_key_id: str) -> Optional[str]:
        """Rotate a key by generating a new version"""
        old_metadata = self.key_manager.storage.get_key_metadata(old_key_id)
        if not old_metadata:
            logger.error(f"Key not found for rotation: {old_key_id}")
            return None
        
        try:
            # Generate new key with same parameters
            new_key_id = f"{old_key_id}_v{int(datetime.utcnow().timestamp())}"
            
            if old_metadata.key_type == KeyType.SYMMETRIC:
                new_key_data = KeyGenerator.generate_symmetric_key(old_metadata.algorithm)
            elif old_metadata.key_type == KeyType.ASYMMETRIC:
                private_key, public_key = KeyGenerator.generate_asymmetric_keypair(old_metadata.algorithm)
                new_key_data = private_key  # Store private key, public can be derived
            else:
                logger.error(f"Unsupported key type for rotation: {old_metadata.key_type}")
                return None
            
            # Create new metadata
            new_metadata = KeyMetadata(
                key_id=new_key_id,
                key_type=old_metadata.key_type,
                algorithm=old_metadata.algorithm,
                key_size=old_metadata.key_size,
                created_at=datetime.utcnow(),
                expires_at=None,
                status=KeyStatus.ACTIVE,
                usage_count=0,
                last_used=None,
                tags=old_metadata.tags.copy()
            )
            
            # Store new key
            if self.key_manager.storage.store_key(new_key_id, new_key_data, new_metadata):
                # Mark old key as retired
                old_metadata.status = KeyStatus.RETIRED
                self.key_manager.storage.metadata[old_key_id] = old_metadata
                self.key_manager.storage._save_keys()
                
                logger.info(f"Key rotated: {old_key_id} -> {new_key_id}")
                return new_key_id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to rotate key {old_key_id}: {e}")
            return None
    
    def auto_rotate_keys(self) -> Dict[str, str]:
        """Automatically rotate all keys due for rotation"""
        due_keys = self.get_keys_due_for_rotation()
        rotated_keys = {}
        
        for key_id in due_keys:
            new_key_id = self.rotate_key(key_id)
            if new_key_id:
                rotated_keys[key_id] = new_key_id
        
        logger.info(f"Auto-rotated {len(rotated_keys)} keys")
        return rotated_keys


class KeyManager:
    """Main key management system"""
    
    def __init__(self, storage_path: str, master_password: str):
        # Derive master key from password
        master_key, _ = KeyGenerator.derive_key_from_password(master_password)
        master_key_fernet = base64.urlsafe_b64encode(master_key)
        
        self.storage = KeyStorage(storage_path, master_key_fernet)
        self.rotation_manager = KeyRotationManager(self)
        self.generator = KeyGenerator()
    
    def create_key(self, 
                  key_type: KeyType,
                  algorithm: str,
                  key_id: str = None,
                  tags: Dict[str, str] = None,
                  expires_in_days: int = None) -> Optional[str]:
        """Create a new encryption key"""
        
        if key_id is None:
            key_id = f"{key_type.value}_{algorithm}_{int(datetime.utcnow().timestamp())}"
        
        try:
            # Generate key data
            if key_type == KeyType.SYMMETRIC:
                key_data = self.generator.generate_symmetric_key(algorithm)
                key_size = len(key_data) * 8  # bits
            elif key_type == KeyType.ASYMMETRIC:
                private_key, public_key = self.generator.generate_asymmetric_keypair(algorithm)
                key_data = private_key
                key_size = int(algorithm.split("-")[1]) if "-" in algorithm else 2048
            else:
                raise ValueError(f"Unsupported key type: {key_type}")
            
            # Create metadata
            expires_at = None
            if expires_in_days:
                expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            
            metadata = KeyMetadata(
                key_id=key_id,
                key_type=key_type,
                algorithm=algorithm,
                key_size=key_size,
                created_at=datetime.utcnow(),
                expires_at=expires_at,
                status=KeyStatus.ACTIVE,
                usage_count=0,
                last_used=None,
                tags=tags or {}
            )
            
            # Store key
            if self.storage.store_key(key_id, key_data, metadata):
                logger.info(f"Created key: {key_id}")
                return key_id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to create key: {e}")
            return None
    
    def get_key(self, key_id: str) -> Optional[bytes]:
        """Retrieve a key"""
        metadata = self.storage.get_key_metadata(key_id)
        if not metadata:
            return None
        
        if metadata.status != KeyStatus.ACTIVE:
            logger.warning(f"Attempted to use inactive key: {key_id}")
            return None
        
        if metadata.expires_at and datetime.utcnow() > metadata.expires_at:
            logger.warning(f"Attempted to use expired key: {key_id}")
            metadata.status = KeyStatus.INACTIVE
            self.storage._save_keys()
            return None
        
        return self.storage.retrieve_key(key_id)
    
    def list_keys(self, key_type: KeyType = None, status: KeyStatus = None) -> List[KeyMetadata]:
        """List keys with optional filtering"""
        keys = self.storage.list_keys()
        
        if key_type:
            keys = [k for k in keys if k.key_type == key_type]
        
        if status:
            keys = [k for k in keys if k.status == status]
        
        return keys
    
    def revoke_key(self, key_id: str, reason: str = "manual_revocation") -> bool:
        """Revoke a key"""
        metadata = self.storage.get_key_metadata(key_id)
        if not metadata:
            return False
        
        metadata.status = KeyStatus.COMPROMISED if "compromise" in reason.lower() else KeyStatus.RETIRED
        metadata.tags['revocation_reason'] = reason
        metadata.tags['revoked_at'] = datetime.utcnow().isoformat()
        
        self.storage.metadata[key_id] = metadata
        self.storage._save_keys()
        
        logger.info(f"Key revoked: {key_id} (reason: {reason})")
        return True
    
    def cleanup_expired_keys(self) -> int:
        """Remove expired and old retired keys"""
        cleaned_count = 0
        now = datetime.utcnow()
        cutoff_date = now - timedelta(days=365)  # Remove retired keys older than 1 year
        
        keys_to_remove = []
        
        for metadata in self.storage.list_keys():
            # Remove expired keys
            if metadata.expires_at and now > metadata.expires_at:
                keys_to_remove.append(metadata.key_id)
            # Remove old retired keys
            elif (metadata.status in [KeyStatus.RETIRED, KeyStatus.COMPROMISED] and 
                  metadata.created_at < cutoff_date):
                keys_to_remove.append(metadata.key_id)
        
        for key_id in keys_to_remove:
            if self.storage.delete_key(key_id):
                cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} expired/old keys")
        return cleaned_count
    
    def get_key_statistics(self) -> Dict[str, Any]:
        """Get key management statistics"""
        keys = self.storage.list_keys()
        
        stats = {
            'total_keys': len(keys),
            'by_type': {},
            'by_status': {},
            'by_algorithm': {},
            'usage_stats': {
                'most_used': None,
                'least_used': None,
                'total_usage': sum(k.usage_count for k in keys)
            },
            'expiration_summary': {
                'expiring_soon': 0,  # within 30 days
                'expired': 0
            }
        }
        
        now = datetime.utcnow()
        
        for key in keys:
            # Count by type
            key_type = key.key_type.value
            stats['by_type'][key_type] = stats['by_type'].get(key_type, 0) + 1
            
            # Count by status
            status = key.status.value
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
            
            # Count by algorithm
            algorithm = key.algorithm
            stats['by_algorithm'][algorithm] = stats['by_algorithm'].get(algorithm, 0) + 1
            
            # Check expiration
            if key.expires_at:
                if now > key.expires_at:
                    stats['expiration_summary']['expired'] += 1
                elif (key.expires_at - now).days <= 30:
                    stats['expiration_summary']['expiring_soon'] += 1
        
        # Find most/least used keys
        if keys:
            most_used = max(keys, key=lambda k: k.usage_count)
            least_used = min(keys, key=lambda k: k.usage_count)
            
            stats['usage_stats']['most_used'] = {
                'key_id': most_used.key_id,
                'usage_count': most_used.usage_count
            }
            stats['usage_stats']['least_used'] = {
                'key_id': least_used.key_id,
                'usage_count': least_used.usage_count
            }
        
        return stats