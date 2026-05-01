from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def workspace_tmp_path(request) -> Path:
    root = Path(".tmp") / "tests" / f"{request.node.name}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    return root
