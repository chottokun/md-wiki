import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

if sys.platform == "win32":
    # 標準出力と標準エラーを UTF-8 に強制
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

class Config:
    # Wiki directory, defaults to 'wiki' if not provided in environment variables
    WIKI_DIR: Path = Path(os.getenv("WIKI_DIR", "wiki"))
    
    # Qdrant configuration
    QDRANT_MODE: str = os.getenv("QDRANT_MODE", "local")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    
    # You can add more configurations here in the future
