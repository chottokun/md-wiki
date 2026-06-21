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
    
    # Sync configuration
    INCLUDE_UNREVIEWED: bool = os.getenv("INCLUDE_UNREVIEWED", "false").lower() == "true"
    INCREMENTAL_SYNC_BATCH_SIZE: int = int(os.getenv("INCREMENTAL_SYNC_BATCH_SIZE", "50"))

    # Models cache directory
    MODELS_CACHE_DIR: Path = Path(os.getenv("MODELS_CACHE_DIR", ".cache"))
    
    # OKF Concept Types
    OKF_CONCEPT_TYPES: list = ["Concept", "Article", "Source", "RawSource", "Reference", "Landscape"]
