import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Mocking dependencies before any imports
sys.modules["yaml"] = MagicMock()
sys.modules["ruamel"] = MagicMock()
sys.modules["ruamel.yaml"] = MagicMock()
sys.modules["pydantic"] = MagicMock()
sys.modules["langgraph"] = MagicMock()
sys.modules["langgraph.graph"] = MagicMock()
sys.modules["langgraph.checkpoint"] = MagicMock()
sys.modules["langgraph.checkpoint.memory"] = MagicMock()
sys.modules["langchain"] = MagicMock()
sys.modules["langchain_openai"] = MagicMock()
sys.modules["langchain_ollama"] = MagicMock()
sys.modules["langchain_qdrant"] = MagicMock()
sys.modules["langchain_community"] = MagicMock()
sys.modules["git"] = MagicMock()
sys.modules["docling"] = MagicMock()
sys.modules["docling.document_converter"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

# Mock core
mock_core = MagicMock()
sys.modules["core"] = mock_core
mock_utils = MagicMock()
sys.modules["core.utils"] = mock_utils
mock_config = MagicMock()
sys.modules["core.config"] = mock_config
mock_schemas = MagicMock()
sys.modules["core.schemas"] = mock_schemas

import core.utils
import core.config
import core.schemas

def mock_parse_frontmatter(content):
    if "tags: [tag1]" in content:
        return {"tags": ["tag1"]}, "body1"
    if "tags: [tag2]" in content:
        return {"tags": ["tag2"]}, "body2"
    return {}, content

core.utils.parse_frontmatter = mock_parse_frontmatter
core.config.Config.WIKI_DIR = Path("wiki")

# NOW import ObsidianWriter AFTER mocking core.utils
from output.obsidian_writer import ObsidianWriter

class TestObsidianWriterIndexError(unittest.TestCase):
    def setUp(self):
        self.wiki_dir = Path("test_wiki")
        self.wiki_dir.mkdir(exist_ok=True)
        (self.wiki_dir / "page1.md").write_text("---\ntags: [tag1]\n---\nContent 1", encoding="utf-8")
        (self.wiki_dir / "page2.md").write_text("---\ntags: [tag2]\n---\nContent 2", encoding="utf-8")
        (self.wiki_dir / "bad_page.md").write_text("Bad Content", encoding="utf-8")

    def tearDown(self):
        import shutil
        if self.wiki_dir.exists():
            shutil.rmtree(self.wiki_dir)

    def test_update_index_with_read_error(self):
        writer = ObsidianWriter(wiki_dir=str(self.wiki_dir))

        original_read_text = Path.read_text

        def mocked_read_text(path_obj, *args, **kwargs):
            # Convert to string for comparison, but be careful with relative paths
            path_str = str(path_obj)
            if "bad_page.md" in path_str:
                raise PermissionError("Access denied")
            return original_read_text(path_obj, *args, **kwargs)

        with patch.object(Path, 'read_text', autospec=True, side_effect=mocked_read_text):
            # We also need to make sure obsidian_writer is using our mocked parse_frontmatter
            # In output/obsidian_writer.py it is imported as:
            # from core.utils import normalize_term, parse_frontmatter, dump_frontmatter
            with patch('output.obsidian_writer.parse_frontmatter', side_effect=mock_parse_frontmatter):
                writer.update_index()

        home_path = self.wiki_dir / "Home.md"
        self.assertTrue(home_path.exists())
        content = home_path.read_text(encoding="utf-8")

        # Verify page1 and page2 are present
        self.assertIn("[[page1]]", content)
        self.assertIn("[[page2]]", content)
        # Verify bad_page is skipped
        self.assertNotIn("[[bad_page]]", content)

        # Verify tags
        self.assertIn("#tag1 : [[page1]]", content)
        self.assertIn("#tag2 : [[page2]]", content)

if __name__ == "__main__":
    unittest.main()
