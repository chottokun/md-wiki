import pytest
from core.utils import is_safe_url

def test_is_safe_url_safe():
    assert is_safe_url("http://localhost:11434") is True
    assert is_safe_url("http://127.0.0.1:11434") is True
    assert is_safe_url("https://example.com") is True
    assert is_safe_url("http://192.168.1.1") is True  # Typical private IP, safe from link-local SSRF

def test_is_safe_url_unsafe():
    assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False
    assert is_safe_url("http://[fe80::1]") is False
    assert is_safe_url("ftp://localhost") is False
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("http://224.0.0.1") is False  # Multicast
    assert is_safe_url("") is False
    assert is_safe_url(None) is False

def test_is_safe_url_invalid():
    assert is_safe_url("not a url") is False
    assert is_safe_url("http://") is False
