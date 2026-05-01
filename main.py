import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from sqlalchemy import inspect, text

import auth
import catalog
from models import Chapter, Content, Page, User
from session import Base, SessionLocal, engine

load_dotenv()

app = FastAPI(
    title="Soulpage API",
    description="Backend for professional manga/novel platform",
    version="1.0.0"
)


def _cors_origins() -> list[str]:
    raw_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:5501,http://localhost:5501",
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    seed_demo_data()


def ensure_schema():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    user_columns = {
        "username": "VARCHAR(50)",
        "bio": "TEXT",
        "avatar_url": "VARCHAR(500)",
        "website": "VARCHAR(255)",
        "location": "VARCHAR(120)",
        "creator_title": "VARCHAR(120)",
        "role": "VARCHAR(40) DEFAULT 'creator' NOT NULL",
    }

    with engine.begin() as connection:
        for column_name, column_type in user_columns.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))

        users_without_username = connection.execute(
            text("SELECT id, email, name FROM users WHERE username IS NULL OR username = ''")
        ).mappings().all()
        for user in users_without_username:
            base = (user["name"] or user["email"].split("@")[0]).lower()
            username = "".join(char if char.isalnum() else "_" for char in base).strip("_")[:24] or "creator"
            username = f"{username}_{user['id']}"[:30]
            connection.execute(text("UPDATE users SET username = :username WHERE id = :id"), {"username": username, "id": user["id"]})

    if "contents" not in inspector.get_table_names():
        return

    existing_content_columns = {column["name"] for column in inspector.get_columns("contents")}
    content_columns = {
        "genre": "VARCHAR(80)",
        "tags": "VARCHAR(300)",
        "language": "VARCHAR(40) DEFAULT 'English'",
        "age_rating": "VARCHAR(20) DEFAULT '13+'",
        "view_count": "INTEGER DEFAULT 0 NOT NULL",
    }

    with engine.begin() as connection:
        for column_name, column_type in content_columns.items():
            if column_name not in existing_content_columns:
                connection.execute(text(f"ALTER TABLE contents ADD COLUMN {column_name} {column_type}"))


def seed_demo_data():
    from security import hash_password

    database_url = os.getenv("DATABASE_URL", "sqlite:///./soulpage.db")
    should_seed = os.getenv("SEED_DEMO_DATA", "true" if database_url.startswith("sqlite") else "false").lower()
    if should_seed not in {"1", "true", "yes"}:
        return

    db = SessionLocal()
    try:
        demo_user = db.query(User).filter(User.email == "demo@soulpage.local").first()
        if demo_user is None:
            demo_user = User(
                email="demo@soulpage.local",
                username="soulpage_demo",
                name="Soulpage Demo Studio",
                creator_title="Featured Creator",
                bio="A living sample account used to keep the reader, catalog, and studio surfaces populated on a fresh install.",
                avatar_url="/assets/girl.png",
                website="https://soulpage.example",
                location="Cloud District",
                role="admin",
                hashed_password=hash_password("SoulpageDemo123!"),
            )
            db.add(demo_user)
            db.commit()
            db.refresh(demo_user)

        demos = [
            {
                "title": "Chronicles of Solstice",
                "content_type": "manga",
                "description": "A sealed city, an eclipse clock, and two apprentices racing the first sunrise in a thousand years.",
                "cover_url": "/assets/cover1.png",
                "genre": "Fantasy",
                "tags": "magic, adventure, featured",
                "language": "English",
                "age_rating": "13+",
                "pages": ["/assets/cover1.png", "/assets/hero-bg.png", "/assets/cover2.png"],
            },
            {
                "title": "Neon Rain Letters",
                "content_type": "novel",
                "description": "A courier delivers memories through a city where every storm rewrites the map.",
                "cover_url": "/assets/cover2.png",
                "genre": "Sci-Fi",
                "tags": "cyberpunk, mystery, slow burn",
                "language": "English",
                "age_rating": "16+",
                "pages": ["/assets/cover2.png", "/assets/hero-bg-2.png", "/assets/cover3.png"],
            },
            {
                "title": "Kitchen After Midnight",
                "content_type": "manhwa",
                "description": "An after-hours diner serves one impossible dish to every customer who finds the hidden door.",
                "cover_url": "/assets/cover3.png",
                "genre": "Slice of Life",
                "tags": "food, supernatural, cozy",
                "language": "English",
                "age_rating": "All",
                "pages": ["/assets/cover3.png", "/assets/boy.png", "/assets/girl.png"],
            },
        ]

        for item in demos:
            content = db.query(Content).filter(Content.title == item["title"], Content.owner_id == demo_user.id).first()
            if content is None:
                content = Content(
                    owner_id=demo_user.id,
                    title=item["title"],
                    content_type=item["content_type"],
                    description=item["description"],
                    cover_url=item["cover_url"],
                    genre=item["genre"],
                    tags=item["tags"],
                    language=item["language"],
                    age_rating=item["age_rating"],
                    status="published",
                )
                db.add(content)
                db.commit()
                db.refresh(content)

            chapter = db.query(Chapter).filter(Chapter.content_id == content.id, Chapter.number == 1).first()
            if chapter is None:
                chapter = Chapter(
                    content_id=content.id,
                    number=1,
                    title="Opening Frame",
                    source_lang="en",
                    target_lang="en",
                    status="published",
                )
                db.add(chapter)
                db.commit()
                db.refresh(chapter)

            has_pages = db.query(Page).filter(Page.chapter_id == chapter.id).count() > 0
            if not has_pages:
                for index, image_url in enumerate(item["pages"], start=1):
                    db.add(
                        Page(
                            chapter_id=chapter.id,
                            page_order=index,
                            image_url=image_url,
                            caption=f"{item['title']} page {index}",
                        )
                    )
                db.commit()
    finally:
        db.close()


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Soulpage API",
        "version": "1.0.0-monorepo"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(catalog.router, prefix="/api", tags=["Catalog"])

# Include more routers as they are implemented.
# app.include_router(upload.router, prefix="/api/upload", tags=["Storage"])
# app.include_router(analytics.router, prefix="/api/analytics", tags=["Insights"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
