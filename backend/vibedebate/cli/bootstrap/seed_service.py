import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from vibedebate.core.config import SeedSettings


@dataclass
class SeedService:
    session: AsyncSession
    settings: SeedSettings

    async def load_data(self) -> None:
        directory = Path(self.settings.seed_dir)
        if not directory.is_dir():
            raise ValueError(f"Seed directory not found: {directory}")
        files = sorted(directory.glob("*.json"))
        if not files:
            raise ValueError(f"No JSON seed files found: {directory}")

        for file_path in files:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError(f"Seed file must contain a list: {file_path}")
            for item in payload:
                await self._upsert_item(item)

    @staticmethod
    def _import_string(path: str) -> type[Any]:
        module_path, attr_name = path.rsplit(".", 1)
        return getattr(import_module(module_path), attr_name)

    async def _upsert_item(self, item: dict[str, Any]) -> None:
        model = self._import_string(item["model"])
        mapper = inspect(model)
        values = dict(item.get("fields", {}))
        if "id" in item:
            values["id"] = item["id"]

        # Convert JSON UUID strings using model metadata, without domain-specific fields.
        for field, value in values.items():
            column = mapper.column_attrs[field].columns[0]
            if value is not None and isinstance(value, str):
                try:
                    python_type = column.type.python_type
                except NotImplementedError:
                    continue
                if python_type is UUID:
                    values[field] = UUID(value)

        lookup_fields = item.get("lookup", [])
        if lookup_fields:
            obj = await self._find_by_lookup(model, values, lookup_fields)
            if obj is None:
                self.session.add(model(**values))
            else:
                primary_keys = {
                    mapper.get_property_by_column(column).key
                    for column in mapper.primary_key
                }
                # Natural-key matches keep their user and existing references.
                for field, value in values.items():
                    if field not in primary_keys:
                        setattr(obj, field, value)
        else:
            await self.session.merge(model(**values))

        # Later records may reference entities loaded earlier in the same transaction.
        await self.session.flush()

    async def _find_by_lookup(
        self,
        model: type[Any],
        values: dict[str, Any],
        lookup_fields: list[str],
    ) -> Any | None:
        conditions = []
        for field in lookup_fields:
            if field not in values:
                raise ValueError(f"Lookup field is missing in seed item: {field}")
            conditions.append(getattr(model, field) == values[field])
        return (
            await self.session.execute(select(model).where(*conditions))
        ).scalar_one_or_none()
