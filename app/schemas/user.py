from typing import Literal
from uuid import UUID
from datetime import datetime

import jwt
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator


class UserCreate(BaseModel):
    name:str = Field(max_length=255, min_length=1)
    email: EmailStr
    password:str = Field(max_length=128, min_length=8)
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

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:UUID
    email:EmailStr
    name:str
    created_at:datetime

class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = Field(default="bearer")
