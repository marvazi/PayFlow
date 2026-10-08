import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(
        self,
        redis: Redis,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self.redis = redis
        self.cache_ttl_seconds = cache_ttl_seconds

    async def set(self, key: str, value: Any) -> None:
        serialized = json.dumps(value)

        try:
            await self.redis.set(
                key,
                serialized,
                ex=self.cache_ttl_seconds,
            )
        except RedisError:
            logger.warning("Не удалось записать кеш: %s", key, exc_info=True)

    async def get(self, key: str) -> Any:
        try:
            value = await self.redis.get(key)
        except RedisError:
            logger.warning("Не удалось прочитать кеш: %s", key, exc_info=True)
            return None

        if value is None:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Некорректный JSON в кеше: %s", key, exc_info=True)
            return None

    async def delete(self, key: str) -> None:
        try:
            await self.redis.delete(key)
        except RedisError:
            logger.warning("Не удалось удалить кеш: %s", key, exc_info=True)
