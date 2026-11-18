import logging
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from vibedebate.core.config.cache import CacheSettings
from vibedebate.repositories.cache import CacheRepository, CacheWrite

logger = logging.getLogger(__name__)

# Initialization, comparison and publication are atomic across workers. Random
# generations avoid reusing old keys even if Redis evicts a generation key.
GENERATIONS = """
local result = {}
for i, key in ipairs(KEYS) do
    redis.call('SET', key, ARGV[i], 'NX', 'EX', ARGV[#KEYS + 1])
    result[i] = redis.call('GET', key)
end
return result
"""
PUBLISH = """
for i = 1, #KEYS - 1 do
    if redis.call('GET', KEYS[i]) ~= ARGV[i] then return 0 end
end
redis.call('SET', KEYS[#KEYS], ARGV[#KEYS], 'EX', ARGV[#KEYS + 1])
return 1
"""


class RedisCacheRepository(CacheRepository):
    def __init__(self, client: Redis, settings: CacheSettings):
        self.client, self.settings = client, settings
        self.generation_ttl = (
            max(
                settings.cache_catalog_ttl,
                settings.cache_view_ttl,
                settings.cache_history_ttl,
                settings.cache_analysis_ttl,
                settings.cache_status_ttl,
            )
            * 2
        )

    def _key(self, key: str) -> str:
        return f"{self.settings.cache_namespace}:{key}"

    async def generations(self, tags):
        if not tags:
            return []

        try:
            values = await self.client.eval(
                GENERATIONS,
                len(tags),
                *[self._key(f"generation:{tag}") for tag in tags],
                *[uuid4().hex for _ in tags],
                self.generation_ttl,
            )
            return [value.decode() for value in values]
        except (RedisError, OSError):
            logger.warning("Redis unavailable; reading PostgreSQL", exc_info=False)
            return None

    async def get_many(self, keys):
        if not keys:
            return []

        try:
            return await self.client.mget([self._key(key) for key in keys])
        except (RedisError, OSError):
            return [None] * len(keys)

    async def put(self, key, value, ttl, tags, generations):
        await self.put_many([CacheWrite(key, value, ttl, tags, generations)])

    async def put_many(self, entries):
        entries = [
            entry
            for entry in entries
            if len(entry.value) <= self.settings.cache_max_entry_bytes
        ]
        if not entries:
            return

        try:
            async with self.client.pipeline(transaction=False) as pipe:
                for entry in entries:
                    pipe.eval(
                        PUBLISH,
                        len(entry.tags) + 1,
                        *[self._key(f"generation:{tag}") for tag in entry.tags],
                        self._key(entry.key),
                        *entry.generations,
                        entry.value,
                        entry.ttl,
                    )
                await pipe.execute()
        except (RedisError, OSError):
            pass

    async def invalidate(self, tags):
        if not tags:
            return

        try:
            async with self.client.pipeline(transaction=True) as pipe:
                for tag in tags:
                    pipe.set(
                        self._key(f"generation:{tag}"),
                        uuid4().hex,
                        ex=self.generation_ttl,
                    )
                await pipe.execute()
        except (RedisError, OSError):
            # The database commit remains successful. TTL bounds stale views;
            # authorization and every command still use PostgreSQL.
            logger.warning("Cache invalidation unavailable; TTL will expire views")
