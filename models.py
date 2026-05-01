from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(50), unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    creator_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[str] = mapped_column(String(40), default="creator", nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Content(Base):
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), default="manga", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tags: Mapped[str | None] = mapped_column(String(300), nullable=True)
    language: Mapped[str | None] = mapped_column(String(40), default="English", nullable=True)
    age_rating: Mapped[str | None] = mapped_column(String(20), default="13+", nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), index=True, nullable=False)
    number: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_lang: Mapped[str] = mapped_column(String(20), default="ja", nullable=False)
    target_lang: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="published", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True, nullable=False)
    page_order: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReadingProgress(Base):
    __tablename__ = "reading_progress"
    __table_args__ = (UniqueConstraint("user_id", "chapter_id", name="uq_user_chapter_progress"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
