import asyncio
import hashlib
from inspect import signature
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

from pydantic import TypeAdapter, ValidationError

from vibedebate.core.config.cache import CacheSettings
from vibedebate.repositories.cache import CacheRepository

T = TypeVar("T")


class ReadCache:
    def __init__(self, repository: CacheRepository, settings: CacheSettings):
        self.repository, self.settings = repository, settings
        self.locks = [asyncio.Lock() for _ in range(64)]

    async def load(
        self,
        key: str,
        tags: list[str],
        adapter: TypeAdapter[T],
        loader: Callable[[], Awaitable[T]],
        ttl: int | Callable[[T], int],
    ) -> T:
        digest = hashlib.sha256(key.encode()).hexdigest()
        async with self.locks[int(digest[:8], 16) % len(self.locks)]:
            generations = await self.repository.generations(tags)
            if generations is None:
                return await loader()

            physical = f"read:{digest}:{':'.join(generations)}"
            cached = (await self.repository.get_many([physical]))[0]
            if cached is not None:
                try:
                    return adapter.validate_json(cached)
                except ValidationError:
                    pass

            result = await loader()
            lifetime = ttl(result) if callable(ttl) else ttl
            if lifetime > 0:
                await self.repository.put(
                    physical, adapter.dump_json(result), lifetime, tags, generations
                )
            return result


def cached_read(
    result_type: Any,
    *,
    key: Callable[..., str],
    tags: Callable[..., list[str]],
    ttl: str | Callable,
):
    adapter = TypeAdapter(result_type)

    def decorate(method):
        parameters = signature(method)

        @wraps(method)
        async def wrapped(self, *args, **kwargs):
            bound = parameters.bind(self, *args, **kwargs)
            bound.apply_defaults()
            values = [
                value for name, value in bound.arguments.items() if name != "self"
            ]
            return await self.cache.load(
                key(*values),
                tags(*values),
                adapter,
                lambda: method(self, *args, **kwargs),
                (
                    getattr(self.cache.settings, ttl)
                    if isinstance(ttl, str)
                    else lambda result: ttl(self.cache.settings, result)
                ),
            )

        return wrapped

    return decorate
