import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from sqlalchemy import inspect, text

import auth
from models import Content, User
from session import Base, engine

load_dotenv()

app = FastAPI(
    title="Soulpage API",
    description="Backend for professional manga/novel platform",
    version="1.0.0"
)


def _cors_origins() -> list[str]:
    raw_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500,http://localhost:5500",
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

# Include more routers as they are implemented.
# app.include_router(upload.router, prefix="/api/upload", tags=["Storage"])
# app.include_router(analytics.router, prefix="/api/analytics", tags=["Insights"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
