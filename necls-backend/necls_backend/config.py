from __future__ import annotations
import os, json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    # Try loading from current directory and parent directory
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try parent directory
        parent_env = Path(__file__).parent.parent / '.env'
        if parent_env.exists():
            load_dotenv(parent_env)
        else:
            # Fallback to default behavior
            load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use environment variables only

def _encode_password_in_url(url: str) -> str:
    """URL-encode the password in a database connection string."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            # URL-encode the password
            encoded_password = quote(parsed.password, safe='')
            # Reconstruct URL with encoded password
            netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    except Exception:
        # If parsing fails, return original URL
        pass
    return url

@dataclass
class Settings:
    """Edit defaults here or override via env vars / JSON file."""
    db_url: str = _encode_password_in_url(os.getenv("FEEDCRAWLER_DB", "postgresql+psycopg2://postgres:admin@localhost:5432/neclsdbtest"))
    db2_url: str = _encode_password_in_url(os.getenv("APP_DB", "postgresql+psycopg2://postgres:admin@localhost:5432/appdbtest"))
    data_dir: Path = Path() #Path(os.getenv("DATA_DIR", "data"))
    model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
    crawl_interval_min: int = int(os.getenv("CRAWL_INTERVAL", "15"))
    username:str = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
    password:str = os.getenv("INITIAL_ADMIN_PASSWORD", "admin.password")

    @classmethod
    def from_file(cls, fp: Path | str) -> "Settings":
        data = json.loads(Path(fp).read_text())
        return cls(**data)

# a singleton used across the package
settings = Settings()
# settings.data_dir.mkdir(exist_ok=True)