import unittest
from unittest.mock import MagicMock
import sys



from agent.state import merge_list

class TestAgentState(unittest.TestCase):
    def test_merge_list_basic(self):
        """Test basic list concatenation."""
        left = [1, 2]
        right = [3, 4]
        expected = [1, 2, 3, 4]
        self.assertEqual(merge_list(left, right), expected)

    def test_merge_list_empty_left(self):
        """Test with empty left list."""
        left = []
        right = [1, 2]
        expected = [1, 2]
        self.assertEqual(merge_list(left, right), expected)

    def test_merge_list_empty_right(self):
        """Test with empty right list."""
        left = [1, 2]
        right = []
        expected = [1, 2]
        self.assertEqual(merge_list(left, right), expected)

    def test_merge_list_both_empty(self):
        """Test with both lists empty."""
        left = []
        right = []
        expected = []
        self.assertEqual(merge_list(left, right), expected)

    def test_merge_list_with_documents(self):
        """Test with mock Document objects (the intended use case)."""
        doc1 = MagicMock()
        doc2 = MagicMock()
        left = [doc1]
        right = [doc2]
        expected = [doc1, doc2]
        self.assertEqual(merge_list(left, right), expected)

if __name__ == "__main__":
    unittest.main()
