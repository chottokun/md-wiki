import pytest
from unittest.mock import MagicMock, patch, call
import sys
import os
from pathlib import Path
from auto_rebuild import auto_rebuild

@pytest.fixture
def mock_deps():
    # We use a standard MagicMock for Path and configure it to behave like a Path
    with patch('auto_rebuild.subprocess.run') as mock_run, \
         patch('auto_rebuild.Path') as mock_path, \
         patch('auto_rebuild.os.getenv') as mock_getenv, \
         patch('auto_rebuild.print'):
        yield mock_run, mock_path, mock_getenv

def test_auto_rebuild_flow(mock_deps):
    mock_run, mock_path, mock_getenv = mock_deps

    mock_getenv.return_value = "local"

    # Setup directories
    mock_raw_dir = MagicMock()
    mock_wiki_dir = MagicMock()
    mock_raw_md_dir = MagicMock()
    mock_sources_dir = MagicMock()
    mock_git_dir = MagicMock()

    def path_side_effect(path_str):
        path_str = str(path_str)
        if path_str == '_raw':
            return mock_raw_dir
        if path_str == 'wiki':
            return mock_wiki_dir
        m = MagicMock()
        m.__str__.return_value = path_str
        return m

    mock_path.side_effect = path_side_effect

    # Configure PDFs in _raw
    # To make sorted() work, we need to implement __lt__
    pdf1 = MagicMock()
    pdf1.name = "1_first.pdf"
    pdf1.__str__.return_value = "_raw/1_first.pdf"
    pdf1.__lt__.side_effect = lambda other: pdf1.name < other.name

    pdf2 = MagicMock()
    pdf2.name = "2_second.pdf"
    pdf2.__str__.return_value = "_raw/2_second.pdf"
    pdf2.__lt__.side_effect = lambda other: pdf2.name < other.name

    # Return them in reverse order to test sorting
    mock_raw_dir.glob.return_value = [pdf2, pdf1]

    # Configure wiki pages for deletion
    page1 = MagicMock()
    page1.name = "Page1.md"
    page1.__str__.return_value = "wiki/Page1.md"

    home_md = MagicMock()
    home_md.name = "Home.md"
    home_md.__str__.return_value = "wiki/Home.md"

    log_md = MagicMock()
    log_md.name = "log.md"
    log_md.__str__.return_value = "wiki/log.md"

    raw_md_file = MagicMock()
    raw_md_file.name = "extra.md"
    raw_md_file.__str__.return_value = "wiki/raw_markdown/extra.md"

    mock_wiki_dir.rglob.return_value = [page1, home_md, log_md, raw_md_file]

    # Configure subdirectories and their contents
    mock_wiki_dir.__truediv__.side_effect = lambda x: {
        "raw_markdown": mock_raw_md_dir,
        "sources": mock_sources_dir,
        ".git": mock_git_dir
    }.get(x, MagicMock())

    mock_raw_md_dir.exists.return_value = True
    mock_raw_md_dir.glob.return_value = [raw_md_file]

    mock_sources_dir.exists.return_value = True
    source_file = MagicMock()
    source_file.is_file.return_value = True
    source_file.name = "source_a.pdf"
    mock_sources_dir.glob.return_value = [source_file]

    mock_git_dir.exists.return_value = True # Git already exists

    # Execute
    auto_rebuild()

    # VERIFICATIONS

    # 1. Qdrant reset
    mock_run.assert_any_call([
        sys.executable, "-c",
        "from retrieval.qdrant_store import QdrantHybridStore; store=QdrantHybridStore(); store.delete_collection(); store.close()"
    ], check=True)

    # 2. Wiki cleanup
    page1.unlink.assert_called_once()
    home_md.unlink.assert_not_called()
    log_md.unlink.assert_not_called()
    # raw_md_file should NOT be unlinked in rglob loop due to "raw_markdown" in str(p)

    # 3. raw_markdown and sources cleanup
    raw_md_file.unlink.assert_called_once()
    source_file.unlink.assert_called_once()

    # 4. Ollama restart (mode is local)
    mock_run.assert_any_call(["docker", "restart", "ollama"], check=True, capture_output=True)

    # 5. Ingest calls should be sorted
    # pdf1 ("1_first.pdf") should be called before pdf2 ("2_second.pdf")
    calls = [
        call(["uv", "run", "python", "main.py", str(pdf1), "--yes"], check=True),
        call(["uv", "run", "python", "main.py", str(pdf2), "--yes"], check=True)
    ]
    mock_run.assert_has_calls(calls, any_order=False)

    # 6. Final sync and lint
    mock_run.assert_any_call(["uv", "run", "python", "main.py", "--sync", "--force"], check=True)
    mock_run.assert_any_call([sys.executable, "main.py", "--lint", "--yes"], check=True)

def test_auto_rebuild_git_init(mock_deps):
    mock_run, mock_path, mock_getenv = mock_deps

    mock_getenv.return_value = "local"

    mock_raw_dir = MagicMock()
    mock_raw_dir.glob.return_value = []
    mock_wiki_dir = MagicMock()
    mock_wiki_dir.rglob.return_value = []
    mock_wiki_dir.exists.return_value = False

    mock_git_dir = MagicMock()
    mock_git_dir.exists.return_value = False # Git DOES NOT exist

    def path_side_effect(path_str):
        path_str = str(path_str)
        if path_str == '_raw': return mock_raw_dir
        if path_str == 'wiki': return mock_wiki_dir
        m = MagicMock()
        m.__str__.return_value = path_str
        return m

    mock_path.side_effect = path_side_effect

    # Make sure wiki_dir / ".git" returns mock_git_dir
    mock_wiki_dir.__truediv__.side_effect = lambda x: mock_git_dir if x == ".git" else MagicMock()

    # Execute
    auto_rebuild()

    # Verify Git initialization
    mock_run.assert_any_call(["git", "init", str(mock_wiki_dir)], check=True)
    mock_run.assert_any_call(["git", "-C", str(mock_wiki_dir), "add", ".gitkeep"], check=True)
    mock_run.assert_any_call(["git", "-C", str(mock_wiki_dir), "commit", "-m", "Initial commit"], check=True)

def test_auto_rebuild_cloud_mode(mock_deps):
    mock_run, mock_path, mock_getenv = mock_deps

    mock_getenv.return_value = "cloud" # Cloud mode

    mock_raw_dir = MagicMock()
    mock_raw_dir.glob.return_value = []
    mock_wiki_dir = MagicMock()
    mock_wiki_dir.rglob.return_value = []
    mock_git_dir = MagicMock()
    mock_git_dir.exists.return_value = True

    def path_side_effect(path_str):
        path_str = str(path_str)
        if path_str == '_raw': return mock_raw_dir
        if path_str == 'wiki': return mock_wiki_dir
        return MagicMock()

    mock_path.side_effect = path_side_effect
    mock_wiki_dir.__truediv__.side_effect = lambda x: mock_git_dir if x == ".git" else MagicMock()

    # Execute
    auto_rebuild()

    # Verify Ollama restart is NOT called in cloud mode
    ollama_restart_call = call(["docker", "restart", "ollama"], check=True, capture_output=True)
    assert ollama_restart_call not in mock_run.call_args_list
