"""
FastAPI Application Entrypoint.
Initializes database tables, mounts static asset directories, registers API routers,
and sets up CORS & application metadata.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import APP_NAME, APP_TAGLINE, UPLOADS_DIR, BASE_DIR
from app.database import init_db
from app.routers import users, items, rentals, matching, demo, reviews, rental_extras

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager that ensures SQLite schema is initialized on startup.
    """
    init_db()
    # Ensure static and uploads directories exist
    static_dir = BASE_DIR / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=APP_NAME,
    description=APP_TAGLINE,
    version="1.0.0",
    lifespan=lifespan,
)

# Allow local development and frontend cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(users.router)
app.include_router(items.router)
app.include_router(rentals.router)
app.include_router(matching.router)
app.include_router(demo.router)
app.include_router(reviews.router)
app.include_router(rental_extras.router)


@app.get("/api/info")
def get_app_info():
    """
    Returns application configuration and branding metadata.
    """
    return {
        "app_name": APP_NAME,
        "app_tagline": APP_TAGLINE,
        "version": "1.0.0",
        "demo_mode": True,
        "storage": "sqlite3",
        "escrow_mode": "simulated_state_machine",
        "identity_mode": "sha256_hash_chain",
    }
    
@app.get("/health")
def health_check():
    return {"status": "healthy", "app": APP_NAME, "version": "1.0.0"}


# Static directory setup
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount /static and /uploads
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/")
def root_redirect():
    """
    Redirects root URL to the single page application served at /static/index.html.
    """
    return RedirectResponse(url="/static/index.html")
