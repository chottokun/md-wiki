import pytest
import requests
import os

def check_ollama():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=1)
        return response.status_code == 200
    except:
        return False

@pytest.fixture(scope="session", autouse=True)
def force_memory_qdrant():
    os.environ["QDRANT_MODE"] = "memory"
    os.environ["SKIP_SPARSE_EMBEDDINGS"] = "true"
    yield

def pytest_configure(config):
    config.addinivalue_line("markers", "ollama: mark test as requiring ollama service")

def pytest_runtest_setup(item):
    if any(item.iter_markers(name="ollama")):
        if not check_ollama():
            pytest.skip("ollama service is not available")
