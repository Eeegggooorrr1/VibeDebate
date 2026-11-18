
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CacheWrite:
    key: str
    value: bytes
    ttl: int
    tags: list[str]
    generations: list[str]


class CacheRepository(ABC):
    @abstractmethod
    async def generations(self, tags: list[str]) -> list[str] | None: ...

    @abstractmethod
    async def get_many(self, keys: list[str]) -> list[bytes | None]: ...

    @abstractmethod
    async def put(
        self, key: str, value: bytes, ttl: int, tags: list[str], generations: list[str]
    ) -> None:
        ...
    @abstractmethod
    async def invalidate(self, tags: set[str]) -> None: ...

    async def put_many(self, entries: list[CacheWrite]) -> None:
        for entry in entries:
            await self.put(
                entry.key, entry.value, entry.ttl, entry.tags, entry.generations
            )


class NullCacheRepository(CacheRepository):
    async def generations(self, tags):
        return None

    async def get_many(self, keys):
        return [None] * len(keys)

    async def put(self, key, value, ttl, tags, generations):
        pass

    async def invalidate(self, tags):
        pass
