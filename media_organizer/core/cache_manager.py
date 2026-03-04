"""Cache manager for storing and retrieving analysis results."""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of analysis results keyed by file hash."""
    
    def __init__(self, cache_path: Path = Path("cache/cache.json")):
        """
        Initialize the cache manager.
        
        Args:
            cache_path: Path to the cache file
        """
        self.cache_path = cache_path
        self._cache: dict = {}
        self._ensure_cache_dir()
        self.load()
    
    def _ensure_cache_dir(self):
        """Ensure the cache directory exists."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> dict:
        """Load cache from disk."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} cached entries from {self.cache_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cache: {e}, starting fresh")
                self._cache = {}
        else:
            self._cache = {}
        return self._cache
    
    def save(self):
        """Save cache to disk."""
        try:
            self._ensure_cache_dir()
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(self._cache)} entries to cache")
        except IOError as e:
            logger.error(f"Failed to save cache: {e}")
    
    def get(self, file_hash: str) -> dict | None:
        """
        Get cached result for a file hash.
        
        Args:
            file_hash: The hash of the file
            
        Returns:
            Cached result dict or None if not found
        """
        return self._cache.get(file_hash)
    
    def set(self, file_hash: str, result: dict):
        """
        Cache a result.
        
        Args:
            file_hash: The hash of the file
            result: The result dict to cache
        """
        self._cache[file_hash] = result
        self.save()
    
    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()
        if self.cache_path.exists():
            try:
                self.cache_path.unlink()
                logger.info("Cache cleared")
            except IOError as e:
                logger.error(f"Failed to delete cache file: {e}")
    
    def __len__(self) -> int:
        """Return number of cached entries."""
        return len(self._cache)
