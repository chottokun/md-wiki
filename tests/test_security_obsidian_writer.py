import pytest
import shutil
from pathlib import Path
from output.obsidian_writer import ObsidianWriter
from core.schemas import DraftConfig


@pytest.fixture
def temp_wiki(tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    return wiki_dir


@pytest.fixture
def temp_raw(tmp_path, monkeypatch):
    raw_dir = tmp_path / "_raw"
    raw_dir.mkdir()
    # Mock Path("_raw").resolve() to point to our temp _raw dir
    # Since ObsidianWriter uses Path("_raw").resolve(), we need to ensure it finds ours
    # However, Path("_raw") will look for a directory named _raw in the current working directory.
    # So we change the CWD.
    monkeypatch.chdir(tmp_path)
    return raw_dir


def test_source_path_traversal_blocked(temp_wiki, temp_raw, tmp_path):
    writer = ObsidianWriter(wiki_dir=str(temp_wiki))

    # Create a sensitive file outside _raw
    sensitive_file = tmp_path / "sensitive.txt"
    sensitive_file.write_text("secret")

    # Attempt traversal
    # _get_safe_path will be called with (raw_base, "../../sensitive.txt")
    config = DraftConfig(
        page_name="test",
        proposed_content="content",
        source_filename="stolen.txt",
        source_path="../../sensitive.txt",
    )

    # In my current implementation, _handle_source_file catches ValueError and returns None
    # Let's verify that the file was NOT copied.
    result = writer._handle_source_file("stolen.txt", "../../sensitive.txt")

    assert result is None
    assert not (temp_wiki / "sources" / "stolen.txt").exists()


def test_source_path_safe_copy(temp_wiki, temp_raw):
    writer = ObsidianWriter(wiki_dir=str(temp_wiki))

    # Create a legitimate file in _raw
    safe_file = temp_raw / "safe.txt"
    safe_file.write_text("safe content")

    config = DraftConfig(
        page_name="test",
        proposed_content="content",
        source_filename="safe_copy.txt",
        source_path="safe.txt",
    )

    result = writer._handle_source_file("safe_copy.txt", "safe.txt")

    assert result == "[[sources/safe_copy.txt]]"
    assert (temp_wiki / "sources" / "safe_copy.txt").exists()
    assert (temp_wiki / "sources" / "safe_copy.txt").read_text() == "safe content"


def test_source_path_filename_only(temp_wiki, temp_raw):
    writer = ObsidianWriter(wiki_dir=str(temp_wiki))

    # Create a legitimate file in _raw
    safe_file = temp_raw / "by_name.txt"
    safe_file.write_text("by name content")

    result = writer._handle_source_file("by_name.txt")

    assert result == "[[sources/by_name.txt]]"
    assert (temp_wiki / "sources" / "by_name.txt").exists()
    assert (temp_wiki / "sources" / "by_name.txt").read_text() == "by name content"
