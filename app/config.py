"""
Application configuration constants.
Change APP_NAME here to update the name across the entire application.
"""

from pathlib import Path

# The public name of the application (easy to change in this single place)
APP_NAME: str = "RENTX"
APP_TAGLINE: str = "Campus-first equipment borrowing with verifiable item identity and reputation"

# Base directories
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATABASE_PATH: str = str(BASE_DIR / "rentall.db")
UPLOADS_DIR: Path = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Application Config
DEMO_MODE: bool = True
MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp"}

# Upload limits & Demo mode
DEMO_MODE: bool = True
MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp"}

# Standard categories supported in the marketplace
CATEGORIES: list[str] = [
    "tools",
    "camera gear",
    "camping",
    "projector",
    "ladder",
    "electronics",
    "sports",
    "other",
]

# Per-category condition checklist templates
# When listing an item, the owner grades each required part: good / fair / poor
CATEGORY_CHECKLISTS: dict[str, list[str]] = {
    "camera gear": ["lens", "body", "battery", "memory card"],
    "tools": ["chuck", "battery", "bits", "casing"],
    "projector": ["lamp", "remote", "cables", "lens"],
    "camping": ["fabric/zippers", "poles/stakes", "accessories", "cleanliness"],
    "ladder": ["rungs", "locking mechanism", "feet/grips", "hinges"],
    "electronics": ["screen/body", "power cable", "ports", "buttons"],
    "sports": ["frame/structure", "straps/grips", "accessories", "wear"],
    "other": ["body", "accessories", "power/cables", "general wear"],
}

# Need-based matching dictionary (Need label -> List of item tags needed)
# Normalized user queries will be matched against these keys/synonyms
NEED_DICTIONARY: dict[str, dict] = {
    "camping": {
        "title": "Weekend Camping Trip",
        "keywords": ["camp", "camping", "tent", "hike", "hiking", "outdoors", "woods"],
        "required_tags": ["tent", "stove", "lantern", "sleeping bag"],
    },
    "put up shelves": {
        "title": "Hang Shelves & Wall Mounting",
        "keywords": ["shelf", "shelves", "hang", "wall mount", "stud finder", "drill", "mounting"],
        "required_tags": ["drill", "level", "ladder", "stud finder"],
    },
    "movie night": {
        "title": "Outdoor / Dorm Movie Night",
        "keywords": ["movie", "cinema", "watch party", "projector", "film", "screening"],
        "required_tags": ["projector", "speaker", "extension cord"],
    },
    "photoshoot": {
        "title": "Campus / Portrait Photoshoot",
        "keywords": ["photo", "photoshoot", "photography", "portrait", "camera", "headshot"],
        "required_tags": ["camera", "tripod", "lighting"],
    },
}
