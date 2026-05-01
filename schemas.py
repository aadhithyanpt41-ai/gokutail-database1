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
    role: str = "creator"
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


class CreatorSummary(BaseModel):
    id: int
    username: str | None
    name: str
    avatar_url: str | None = None
    creator_title: str | None = None


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content_type: str = Field(default="manga", max_length=40)
    description: str | None = Field(default=None, max_length=1000)
    cover_url: str | None = Field(default=None, max_length=500)
    genre: str | None = Field(default=None, max_length=80)
    tags: str | None = Field(default=None, max_length=300)
    language: str | None = Field(default="English", max_length=40)
    age_rating: str | None = Field(default="13+", max_length=20)
    status: str = Field(default="published", max_length=40)

    @field_validator("title", "content_type", "status")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", "cover_url", "genre", "tags", "language", "age_rating")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    content_type: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=1000)
    cover_url: str | None = Field(default=None, max_length=500)
    genre: str | None = Field(default=None, max_length=80)
    tags: str | None = Field(default=None, max_length=300)
    language: str | None = Field(default=None, max_length=40)
    age_rating: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=40)

    @field_validator("title", "content_type", "description", "cover_url", "genre", "tags", "language", "age_rating", "status")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ContentPublic(BaseModel):
    id: int
    owner_id: int
    title: str
    content_type: str
    description: str | None = None
    cover_url: str | None = None
    genre: str | None = None
    tags: str | None = None
    language: str | None = None
    age_rating: str | None = None
    view_count: int = 0
    status: str
    created_at: datetime
    chapter_count: int = 0
    first_chapter_id: int | None = None
    creator: CreatorSummary | None = None

    model_config = {"from_attributes": True}


class ChapterCreate(BaseModel):
    number: float = Field(gt=0)
    title: str | None = Field(default=None, max_length=160)
    source_lang: str = Field(default="ja", max_length=20)
    target_lang: str = Field(default="en", max_length=20)
    status: str = Field(default="published", max_length=40)
    page_urls: list[str] = Field(default_factory=list, max_length=80)

    @field_validator("title", "source_lang", "target_lang", "status")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("page_urls")
    @classmethod
    def clean_page_urls(cls, value: list[str]) -> list[str]:
        return [url.strip() for url in value if url.strip()]


class ChapterPublic(BaseModel):
    id: int
    content_id: int
    number: float
    title: str | None = None
    source_lang: str
    target_lang: str
    status: str
    created_at: datetime
    page_count: int = 0

    model_config = {"from_attributes": True}


class PagePublic(BaseModel):
    id: int
    order: int
    image_url: str
    caption: str | None = None


class ChapterPagesResponse(BaseModel):
    content: ContentPublic
    chapter: ChapterPublic
    pages: list[PagePublic]
    next_chapter_id: int | None = None
    previous_chapter_id: int | None = None


class ProgressUpdate(BaseModel):
    page_number: int = Field(ge=0)
    completed: bool = False


class ProgressPublic(BaseModel):
    chapter_id: int
    page_number: int
    completed: bool
    updated_at: datetime


class AdminOverview(BaseModel):
    users: int
    published_works: int
    draft_works: int
    chapters: int
    pages: int
    total_views: int
    recent_users: list[UserPublic]
    recent_content: list[ContentPublic]
