import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api import auth
from database.models import User
from database.session import Base, engine

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
