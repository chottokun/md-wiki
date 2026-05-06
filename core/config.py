import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Wiki directory, defaults to 'wiki' if not provided in environment variables
    WIKI_DIR: Path = Path(os.getenv("WIKI_DIR", "wiki"))
    
    # Qdrant configuration
    QDRANT_MODE: str = os.getenv("QDRANT_MODE", "local")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    
    # You can add more configurations here in the future
