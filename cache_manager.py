import os
import json
import time
import hashlib
from typing import Any, Optional

class CacheManager:
    """Simple file-based cache to store API responses."""
    
    def __init__(self, cache_dir: str = "cache", expiry_seconds: int = 86400): # Default 24 hours
        self.cache_dir = cache_dir
        self.expiry_seconds = expiry_seconds
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, key: str) -> str:
        """Generates a file path based on the hash of the key."""
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hash_key}.json")

    def get(self, key: str) -> Optional[Any]:
        """Retrieves data from cache if it exists and is not expired."""
        path = self._get_cache_path(key)
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check expiry
            if time.time() - data.get("timestamp", 0) > self.expiry_seconds:
                return None
                
            return data.get("value")
        except Exception:
            return None

    def set(self, key: str, value: Any):
        """Stores data in cache with a timestamp."""
        path = self._get_cache_path(key)
        try:
            data = {
                "timestamp": time.time(),
                "value": value,
                "key_metadata": key[:100] # For debugging
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass # Silent failure for cache
