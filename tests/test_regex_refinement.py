import re
from core.utils import WIKI_LINK_RE

def test_wiki_link_re():
    test_cases = [
        ("[[SimpleLink]]", "SimpleLink"),
        ("[[PageWith|Alias]]", "PageWith"),
        ("[[PageWith#Section]]", "PageWith"),
        ("[[PageWith#Section|Alias]]", "PageWith"),
        ("Text with [[Link1]] and [[Link2|Alias2]].", ["Link1", "Link2"]),
    ]
    
    for text, expected in test_cases:
        matches = WIKI_LINK_RE.findall(text)
        if isinstance(expected, list):
            assert matches == expected, f"Failed for {text}: expected {expected}, got {matches}"
        else:
            assert matches[0] == expected, f"Failed for {text}: expected {expected}, got {matches[0]}"
    
    print("SUCCESS: WIKI_LINK_RE passed all tests.")

if __name__ == "__main__":
    test_wiki_link_re()
