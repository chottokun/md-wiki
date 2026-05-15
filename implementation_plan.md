# Implementation Plan: Wiki Knowledge Pipeline Stabilization (Completed)

## Status: Merged into `main`

The following improvements have been implemented and verified through a full system rebuild.

### 1. Automatic Link Restoration (Auto-linking)
- **Problem**: LLMs often fail to consistently add `[[Wiki Links]]` to generated content.
- **Solution**: Implemented `auto_link_concepts` in `core/utils.py`. This function programmatically scans the generated body text for terms found in the metadata's `concepts` list and wraps them in wiki links.
- **Verification**: Verified via `tests/test_all.py` and visual inspection of rebuilt wiki pages.

### 2. Robust Linting & Concept Generation
- **Problem**: `lint_node` was too strict, only creating concept pages when high-confidence evidence was found in Qdrant.
- **Solution**: Relaxed conditions in `lint_node`. If no evidence is found, the system falls back to using the LLM's internal knowledge to generate a "stub" page.
- **Verification**: Confirmed that `wiki/concepts/` is now populated with relevant technical terms after running `main.py --lint`.

### 3. Human-In-The-Loop (HITL) & Staging
- **Problem**: AI was directly updating wiki pages, which could lead to accidental data loss or quality issues.
- **Solution**: Implemented a formal staging and approval process.
    - New content is created with a `#未審査` (unreviewed) tag.
    - `main.py --sync` skips unreviewed pages by default.
    - Added `approve_update` to `ObsidianWriter` for safe merging.
    - Added `--yes` flag for automated environments.

### 4. Security Enhancements
- **Problem**: Risk of prompt injection from untrusted input documents.
- **Solution**: Refactored all LLM prompts in `core/prompts.py` to use XML-style delimiters and explicit system-level security instructions to treat tagged content strictly as data.

### 5. Infrastructure & CI/CD Stability
- **Problem**: Flaky CI/CD due to resource locking (Qdrant) and service dependencies.
- **Solution**: 
    - Implemented lazy initialization (Factory pattern) in `agent/graph.py` to avoid side effects during module import.
    - Forced in-memory Qdrant and disabled sparse embeddings in test environments.
    - Added `@pytest.mark.ollama` to isolate and skip service-dependent tests in CI.
    - Optimized model caching by setting `HF_HOME` and `FASTEMBED_CACHE_PATH`.

## Final Result
The system now consistently builds a high-density knowledge network, maintains a clean and secure code base, and has a reliable CI/CD pipeline.
