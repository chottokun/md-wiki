import logging
import git
from core.config import Config

logger = logging.getLogger("rag-wiki")

def run_git_commit(message: str):
    """
    Wikiディレクトリ（独立リポジトリ）に対して変更をステージングし、コミットする。

    Args:
        message (str): コミットメッセージ。
    """
    try:
        wiki_dir = Config.WIKI_DIR
        repo = git.Repo(wiki_dir, search_parent_directories=True)

        lock_file = wiki_dir / ".git" / "index.lock"
        if lock_file.exists():
            logger.warning(f"Removing stale git lock file: {lock_file}")
            lock_file.unlink(missing_ok=True)

        repo.git.add(all=True)
        if repo.is_dirty() or repo.untracked_files:
            repo.git.commit("-m", message)
            logger.info(f"Git Commit: {message}")
    except Exception as e:
        logger.error(f"Wikiへの自動コミットに失敗しました: {e}", exc_info=True)
