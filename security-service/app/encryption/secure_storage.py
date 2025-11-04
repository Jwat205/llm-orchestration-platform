"""
Secure Storage Implementation
Provides secure storage with encryption, integrity checking, and access controls
"""

import os
import json
import hashlib
import hmac
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
import base64


logger = logging.getLogger(__name__)


@dataclass
class StoredItem:
    """Represents an item in secure storage"""
    key: str
    data: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int
    ttl: Optional[int]  # Time to live in seconds
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['accessed_at'] = self.accessed_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StoredItem':
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['accessed_at'] = datetime.fromisoformat(data['accessed_at'])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if item is expired"""
        if not self.ttl:
            return False
        
        expiry_time = self.created_at + timedelta(seconds=self.ttl)
        return datetime.utcnow() > expiry_time


class IntegrityChecker:
    """Checks data integrity using HMAC"""
    
    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key
    
    def generate_signature(self, data: bytes) -> str:
        """Generate HMAC signature for data"""
        signature = hmac.new(self.secret_key, data, hashlib.sha256).hexdigest()
        return signature
    
    def verify_signature(self, data: bytes, signature: str) -> bool:
        """Verify HMAC signature"""
        expected_signature = self.generate_signature(data)
        return hmac.compare_digest(expected_signature, signature)


class EncryptedStorage:
    """Encrypted storage backend"""
    
    def __init__(self, storage_path: str, encryption_key: bytes, integrity_key: bytes):
        self.storage_path = storage_path
        self.fernet = Fernet(encryption_key)
        self.integrity_checker = IntegrityChecker(integrity_key)
        self._ensure_storage_directory()
    
    def _ensure_storage_directory(self):
        """Ensure storage directory exists"""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
    
    def _get_file_path(self, key: str) -> str:
        """Get file path for storage key"""
        # Hash the key to create a safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return os.path.join(self.storage_path, f"{key_hash}.enc")
    
    def store(self, key: str, data: bytes) -> bool:
        """Store encrypted data with integrity check"""
        try:
            # Encrypt data
            encrypted_data = self.fernet.encrypt(data)
            
            # Generate integrity signature
            signature = self.integrity_checker.generate_signature(encrypted_data)
            
            # Create storage package
            storage_package = {
                'encrypted_data': base64.b64encode(encrypted_data).decode('utf-8'),
                'signature': signature,
                'stored_at': datetime.utcnow().isoformat()
            }
            
            # Write to file
            file_path = self._get_file_path(key)
            with open(file_path, 'w') as f:
                json.dump(storage_package, f)
            
            logger.debug(f"Stored encrypted data for key: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store data for key {key}: {e}")
            return False
    
    def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieve and decrypt data with integrity check"""
        try:
            file_path = self._get_file_path(key)
            
            if not os.path.exists(file_path):
                return None
            
            # Read storage package
            with open(file_path, 'r') as f:
                storage_package = json.load(f)
            
            # Extract components
            encrypted_data = base64.b64decode(storage_package['encrypted_data'])
            signature = storage_package['signature']
            
            # Verify integrity
            if not self.integrity_checker.verify_signature(encrypted_data, signature):
                logger.error(f"Integrity check failed for key: {key}")
                return None
            
            # Decrypt data
            decrypted_data = self.fernet.decrypt(encrypted_data)
            
            logger.debug(f"Retrieved and decrypted data for key: {key}")
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Failed to retrieve data for key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete stored data"""
        try:
            file_path = self._get_file_path(key)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Deleted data for key: {key}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete data for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in storage"""
        file_path = self._get_file_path(key)
        return os.path.exists(file_path)
    
    def list_keys(self) -> List[str]:
        """List all stored keys"""
        try:
            if not os.path.exists(self.storage_path):
                return []
            
            # This is a simplified implementation
            # In practice, you'd maintain an index of keys
            files = os.listdir(self.storage_path)
            return [f.replace('.enc', '') for f in files if f.endswith('.enc')]
            
        except Exception as e:
            logger.error(f"Failed to list keys: {e}")
            return []


class SecureStorage:
    """Main secure storage implementation"""
    
    def __init__(self, storage_path: str, encryption_key: bytes, integrity_key: bytes):
        self.encrypted_storage = EncryptedStorage(storage_path, encryption_key, integrity_key)
        self.items: Dict[str, StoredItem] = {}
        self.access_log: List[Dict[str, Any]] = []
        self._load_metadata()
    
    def store(self, 
             key: str,
             data: Any,
             ttl: Optional[int] = None,
             tags: Dict[str, str] = None) -> bool:
        """Store data securely"""
        try:
            # Serialize data
            if isinstance(data, (dict, list)):
                serialized_data = json.dumps(data, default=str).encode('utf-8')
            elif isinstance(data, str):
                serialized_data = data.encode('utf-8')
            elif isinstance(data, bytes):
                serialized_data = data
            else:
                serialized_data = str(data).encode('utf-8')
            
            # Store encrypted data
            if not self.encrypted_storage.store(key, serialized_data):
                return False
            
            # Create metadata
            now = datetime.utcnow()
            item = StoredItem(
                key=key,
                data=type(data).__name__,  # Store type info only
                created_at=now,
                accessed_at=now,
                access_count=0,
                ttl=ttl,
                tags=tags or {}
            )
            
            self.items[key] = item
            self._save_metadata()
            
            # Log access
            self._log_access(key, 'store')
            
            logger.info(f"Stored data securely for key: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store data for key {key}: {e}")
            return False
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve data securely"""
        try:
            # Check if key exists in metadata
            if key not in self.items:
                return None
            
            item = self.items[key]
            
            # Check if expired
            if item.is_expired():
                logger.info(f"Item expired, removing: {key}")
                self.delete(key)
                return None
            
            # Retrieve encrypted data
            serialized_data = self.encrypted_storage.retrieve(key)
            if serialized_data is None:
                return None
            
            # Deserialize based on original type
            try:
                # Try JSON first
                data = json.loads(serialized_data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fall back to string/bytes
                try:
                    data = serialized_data.decode('utf-8')
                except UnicodeDecodeError:
                    data = serialized_data
            
            # Update access metadata
            item.accessed_at = datetime.utcnow()
            item.access_count += 1
            self._save_metadata()
            
            # Log access
            self._log_access(key, 'retrieve')
            
            logger.debug(f"Retrieved data for key: {key}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to retrieve data for key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete data securely"""
        try:
            # Delete from encrypted storage
            if not self.encrypted_storage.delete(key):
                return False
            
            # Remove from metadata
            if key in self.items:
                del self.items[key]
                self._save_metadata()
            
            # Log access
            self._log_access(key, 'delete')
            
            logger.info(f"Deleted data for key: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete data for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        if key not in self.items:
            return False
        
        item = self.items[key]
        if item.is_expired():
            self.delete(key)
            return False
        
        return self.encrypted_storage.exists(key)
    
    def list_keys(self, tags: Dict[str, str] = None) -> List[str]:
        """List all non-expired keys, optionally filtered by tags"""
        keys = []
        
        for key, item in self.items.items():
            # Skip expired items
            if item.is_expired():
                continue
            
            # Filter by tags if provided
            if tags:
                if not all(item.tags.get(tag_key) == tag_value for tag_key, tag_value in tags.items()):
                    continue
            
            keys.append(key)
        
        return keys
    
    def get_metadata(self, key: str) -> Optional[StoredItem]:
        """Get metadata for a stored item"""
        return self.items.get(key)
    
    def update_tags(self, key: str, tags: Dict[str, str]) -> bool:
        """Update tags for a stored item"""
        if key not in self.items:
            return False
        
        self.items[key].tags.update(tags)
        self._save_metadata()
        
        return True
    
    def cleanup_expired(self) -> int:
        """Remove all expired items"""
        expired_keys = []
        
        for key, item in self.items.items():
            if item.is_expired():
                expired_keys.append(key)
        
        cleaned_count = 0
        for key in expired_keys:
            if self.delete(key):
                cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} expired items")
        return cleaned_count
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get storage statistics"""
        total_items = len(self.items)
        expired_items = sum(1 for item in self.items.values() if item.is_expired())
        
        # Calculate total access count
        total_accesses = sum(item.access_count for item in self.items.values())
        
        # Find most/least accessed items
        most_accessed = None
        least_accessed = None
        
        if self.items:
            most_accessed_item = max(self.items.values(), key=lambda x: x.access_count)
            least_accessed_item = min(self.items.values(), key=lambda x: x.access_count)
            
            most_accessed = {
                'key': most_accessed_item.key,
                'access_count': most_accessed_item.access_count
            }
            least_accessed = {
                'key': least_accessed_item.key,
                'access_count': least_accessed_item.access_count
            }
        
        # Group by tags
        tag_distribution = {}
        for item in self.items.values():
            for tag_key, tag_value in item.tags.items():
                tag_key_dist = tag_distribution.setdefault(tag_key, {})
                tag_key_dist[tag_value] = tag_key_dist.get(tag_value, 0) + 1
        
        return {
            'total_items': total_items,
            'active_items': total_items - expired_items,
            'expired_items': expired_items,
            'total_accesses': total_accesses,
            'most_accessed': most_accessed,
            'least_accessed': least_accessed,
            'tag_distribution': tag_distribution,
            'access_log_entries': len(self.access_log)
        }
    
    def get_access_log(self, key: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get access log entries"""
        if key:
            filtered_log = [entry for entry in self.access_log if entry['key'] == key]
        else:
            filtered_log = self.access_log
        
        # Return most recent entries
        return sorted(filtered_log, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    def _log_access(self, key: str, operation: str):
        """Log access operation"""
        log_entry = {
            'key': key,
            'operation': operation,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.access_log.append(log_entry)
        
        # Keep only recent log entries (last 1000)
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-1000:]
    
    def _load_metadata(self):
        """Load metadata from storage"""
        try:
            metadata_data = self.encrypted_storage.retrieve('__metadata__')
            if metadata_data:
                metadata_dict = json.loads(metadata_data.decode('utf-8'))
                
                # Load items
                for key, item_dict in metadata_dict.get('items', {}).items():
                    self.items[key] = StoredItem.from_dict(item_dict)
                
                # Load access log
                self.access_log = metadata_dict.get('access_log', [])
                
                logger.debug(f"Loaded metadata for {len(self.items)} items")
        
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
    
    def _save_metadata(self):
        """Save metadata to storage"""
        try:
            metadata_dict = {
                'items': {key: item.to_dict() for key, item in self.items.items()},
                'access_log': self.access_log[-1000:],  # Keep only recent entries
                'saved_at': datetime.utcnow().isoformat()
            }
            
            metadata_data = json.dumps(metadata_dict, default=str).encode('utf-8')
            self.encrypted_storage.store('__metadata__', metadata_data)
            
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")


class SecureCache(SecureStorage):
    """Secure cache implementation with automatic expiration"""
    
    def __init__(self, storage_path: str, encryption_key: bytes, integrity_key: bytes, default_ttl: int = 3600):
        super().__init__(storage_path, encryption_key, integrity_key)
        self.default_ttl = default_ttl
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cache value with TTL"""
        if ttl is None:
            ttl = self.default_ttl
        
        return self.store(key, value, ttl=ttl, tags={'type': 'cache'})
    
    def get(self, key: str) -> Optional[Any]:
        """Get cache value"""
        return self.retrieve(key)
    
    def invalidate(self, key: str) -> bool:
        """Invalidate cache entry"""
        return self.delete(key)
    
    def clear_cache(self) -> int:
        """Clear all cache entries"""
        cache_keys = self.list_keys(tags={'type': 'cache'})
        cleared_count = 0
        
        for key in cache_keys:
            if self.delete(key):
                cleared_count += 1
        
        return cleared_count