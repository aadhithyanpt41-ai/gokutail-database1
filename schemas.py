from datetime import datetime
import re

from pydantic import BaseModel, Field, field_validator

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    username: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return email

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        username = value.strip().lower()
        if not USERNAME_RE.match(username):
            raise ValueError("Username must be 3-30 lowercase letters, numbers, or underscores")
        return username


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserPublic(BaseModel):
    id: int
    email: str
    username: str | None
    name: str
    bio: str | None = None
    avatar_url: str | None = None
    website: str | None = None
    location: str | None = None
    creator_title: str | None = None
    created_at: datetime
    content_count: int = 0
    follower_count: int = 0
    total_views: int = 0

    model_config = {"from_attributes": True}


class CreatorPublic(BaseModel):
    id: int
    username: str | None
    name: str
    bio: str | None = None
    avatar_url: str | None = None
    website: str | None = None
    location: str | None = None
    creator_title: str | None = None
    created_at: datetime
    content_count: int = 0
    follower_count: int = 0
    total_views: int = 0


class UserUpdate(BaseModel):
    username: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    bio: str | None = Field(default=None, max_length=600)
    avatar_url: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=120)
    creator_title: str | None = Field(default=None, max_length=120)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        username = value.strip().lower()
        if not USERNAME_RE.match(username):
            raise ValueError("Username must be 3-30 lowercase letters, numbers, or underscores")
        return username

    @field_validator("name", "bio", "avatar_url", "website", "location", "creator_title")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content_type: str = Field(default="manga", max_length=40)
    description: str | None = Field(default=None, max_length=1000)
    cover_url: str | None = Field(default=None, max_length=500)
    status: str = Field(default="published", max_length=40)

    @field_validator("title", "content_type", "status")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", "cover_url")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ContentPublic(BaseModel):
    id: int
    title: str
    content_type: str
    description: str | None = None
    cover_url: str | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
