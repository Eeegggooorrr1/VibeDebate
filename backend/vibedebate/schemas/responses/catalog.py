from uuid import UUID
from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    parent_id: UUID | None
    name: str
    slug: str
    description: str


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    category_id: UUID
    title: str
    description: str
    topic_type: str
    default_positions: list[str]
    tags: list[str]
    is_available_in_basic_mode: bool


class PersonaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    key: str
    name: str
    description: str
    available_difficulties: list[int]
