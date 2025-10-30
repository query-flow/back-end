"""
Simple in-memory cache with TTL for LLM responses
"""
import time
from typing import Optional, Any
from threading import Lock


class SimpleCache:
    """Cache em memória com TTL"""

    def __init__(self):
        self._cache = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[str]:
        """Busca no cache"""
        with self._lock:
            if key not in self._cache:
                return None

            value, expires_at = self._cache[key]

            # Verifica expiração
            if expires_at and time.time() > expires_at:
                del self._cache[key]
                return None

            return value

    def set(self, key: str, value: str, ttl_seconds: int = 3600):
        """Salva no cache com TTL"""
        with self._lock:
            expires_at = time.time() + ttl_seconds
            self._cache[key] = (value, expires_at)

    def delete(self, key: str):
        """Remove item do cache"""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        """Limpa todo o cache"""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Retorna número de itens no cache (remove expirados)"""
        with self._lock:
            now = time.time()
            expired = [k for k, (_, exp) in self._cache.items() if exp and now > exp]
            for k in expired:
                del self._cache[k]
            return len(self._cache)


# Instância global
_cache = SimpleCache()
