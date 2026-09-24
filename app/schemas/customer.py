from typing import Literal
from uuid import UUID
from datetime import datetime
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator,
ConfigDict
)
from typing import Self

class CustomerCreate(BaseModel):
    name: str = Field(max_length=255, min_length=1)
    email: EmailStr

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:UUID
    email:EmailStr
    name:str
    created_at:datetime
    organization_id: UUID

class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if value is None:
            raise ValueError("Имя не может быть null")
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if value is None:
            raise ValueError("Email не может быть null")
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def check_has_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Передайте хотя бы одно поле: name или email")
        return self