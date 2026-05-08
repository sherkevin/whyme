"""Legacy `agent_os.search` compatibility package.

The canonical search implementation now lives under
``agent_os.search_engine``. This package only exists so old test modules
(``tests/integration/api/test_search_api*.py``) can be collected without
import errors during ``pytest --collect-only``.

The submodules (`keyword_search`, `hybrid_search`) expose stub classes that
raise ``NotImplementedError`` at runtime. New code must use
``agent_os.search_engine`` instead.
"""

from __future__ import annotations

__all__ = ["keyword_search", "hybrid_search"]
